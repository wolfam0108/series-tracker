import threading
import time
import os
import select
import json
from flask import Flask
from db import Database
from logger import Logger
from downloader import Downloader
from concurrent.futures import ThreadPoolExecutor
from sse import ServerSentEvent
from datetime import datetime, timezone
from status_manager import StatusManager
from functools import partial

class DownloaderAgent(threading.Thread):
    def __init__(self, app: Flask, logger: Logger, db: Database, broadcaster: ServerSentEvent, status_manager: StatusManager):
        super().__init__(daemon=True)
        self.name = "DownloaderAgent"
        self.app = app
        self.logger = logger
        self.db = db
        self.shutdown_flag = threading.Event()
        self.executor = None
        self.active_futures = {}
        self.lock = threading.Lock()
        self.CHECK_INTERVAL = 5
        self.broadcaster = broadcaster
        self.status_manager = status_manager
        self._shutdown_pipe_r, self._shutdown_pipe_w = os.pipe()
        self._last_update_times = {} # {task_id: timestamp}
        self.UPDATE_THROTTLE_SECONDS = 2.0 # Обновляем БД не чаще, чем раз в 2 сек

    def _broadcast_queue_update(self):
        """Собирает активные задачи и транслирует их через SSE."""
        with self.app.app_context():
            active_tasks = self.db.get_active_download_tasks()
            self.broadcaster.broadcast('download_queue_update', active_tasks)

    def _update_executor(self):
        with self.app.app_context():
            try:
                limit = int(self.db.get_setting('max_parallel_downloads', 2))
            except (ValueError, TypeError):
                limit = 2
        
        if self.executor is None or self.executor._max_workers != limit:
            if self.executor:
                self.logger.info("downloader_agent", f"Изменение лимита параллельных загрузок на {limit}. Пересоздание пула.")
                self.executor.shutdown(wait=True)
            self.executor = ThreadPoolExecutor(max_workers=limit, thread_name_prefix='downloader_worker')
            self.logger.info("downloader_agent", f"Пул потоков создан с лимитом {limit} воркеров.")

    def _update_download_progress(self, task_id, progress_data):
        """Коллбэк для обновления прогресса в БД с троттлингом."""
        with self.app.app_context():
            now = time.time()
            last_update = self._last_update_times.get(task_id, 0)
            
            # Проверяем, прошло ли достаточно времени с последнего обновления
            if (now - last_update) > self.UPDATE_THROTTLE_SECONDS or progress_data.get('progress') == 100:
                self.db.update_download_task_progress(task_id, progress_data)
                self._last_update_times[task_id] = now

    def _download_task_worker(self, task_id, video_url, save_path, unique_id, series_id):
        with self.app.app_context():
            try:
                self.status_manager.sync_vk_statuses(series_id)
                
                downloader = Downloader(self.logger)
                progress_callback = partial(self._update_download_progress, task_id)

                # --- НАЧАЛО ИЗМЕНЕНИЙ: Получаем данные сериала для определения относительного пути ---
                series = self.db.get_series(series_id)
                if not series:
                    raise Exception(f"Сериал с ID {series_id} не найден.")
                # --- КОНЕЦ ИЗМЕНЕНИЙ ---

                success, error_msg = downloader.download_video(video_url, save_path, progress_callback)
                
                if success:
                    # --- НАЧАЛО ИЗМЕНЕНИЙ: Сохраняем в БД относительный путь ---
                    relative_path = os.path.relpath(save_path, series['save_path']).replace('\\', '/')
                    self.db.update_media_item_filename(unique_id, relative_path)
                    # --- КОНЕЦ ИЗМЕНЕНИЙ ---
                    self.db.update_media_item_download_status(unique_id, 'completed')
                    self.db.delete_download_task(task_id)
                    self.db.update_series(series_id, {'last_scan_time': datetime.now(timezone.utc)})
                    
                    # Синхронизируем статусы VK-сериала после успешной загрузки
                    self.status_manager.sync_vk_statuses(series_id)
                else:
                    self.db.update_download_task_status(task_id, 'error', error_message=error_msg)
                    self.db.update_media_item_download_status(unique_id, 'error')
                    self.status_manager.sync_vk_statuses(series_id)

            except Exception as e:
                self.logger.error("downloader_agent", f"Критическая ошибка в воркере для задачи {task_id}: {e}", exc_info=True)
                self.db.update_download_task_status(task_id, 'error', error_message="Internal worker error")
                self.db.update_media_item_download_status(unique_id, 'error')
                # И здесь тоже
                self.status_manager.sync_vk_statuses(series_id)
            finally:
                if task_id in self._last_update_times:
                    del self._last_update_times[task_id]
                
                # <<< НАЧАЛО ИЗМЕНЕНИЯ >>>
                # В конце также запускаем полную синхронизацию.
                # Она проверит, остались ли другие загрузки, и примет правильное решение.
                self.status_manager.sync_vk_statuses(series_id)
                # <<< КОНЕЦ ИЗМЕНЕНИЯ >>>
        return task_id

    def _task_done_callback(self, future):
        try:
            task_id = future.result()
            with self.lock:
                if task_id in self.active_futures:
                    del self.active_futures[task_id]
            self.logger.info("downloader_agent", f"Задача {task_id} завершена и удалена из активного списка.")
            self._broadcast_queue_update()
        except Exception as e:
            self.logger.error("downloader_agent", f"Ошибка в колбэке завершения задачи: {e}", exc_info=True)

    def _tick(self):
        self._broadcast_queue_update()
        self.broadcaster.broadcast('agent_heartbeat', {'name': 'downloader'})
        self._update_executor()

        with self.lock:
            current_downloads = len(self.active_futures)
        
        limit = self.executor._max_workers
        if current_downloads >= limit:
            return

        with self.app.app_context():
            tasks_to_start_count = limit - current_downloads
            if tasks_to_start_count > 0:
                pending_tasks = self.db.get_pending_download_tasks(tasks_to_start_count)
                
                if pending_tasks:
                    for task in pending_tasks:
                        task_id = task['id']
                        # Используем правильное имя поля 'task_key'
                        task_key = task['task_key']
                        series_id = task['series_id']
                        
                        self.db.update_download_task_status(task_id, 'downloading')
                        self.db.update_media_item_download_status(task_key, 'downloading')
                        
                        future = self.executor.submit(
                            self._download_task_worker,
                            task_id, task['video_url'], task['save_path'], task_key, series_id
                        )
                        future.add_done_callback(self._task_done_callback)
                        
                        with self.lock:
                            self.active_futures[task_id] = future
                        
                        self.logger.info("downloader_agent", f"Задача ID {task_id} (ключ {task_key}) отправлена в пул на выполнение.")
                    
                    self._broadcast_queue_update()
    
    def recover_tasks(self):
        with self.app.app_context():
            self.logger.info("downloader_agent", "Восстановление задач после перезапуска...")
            requeued_count = self.db.requeue_stuck_downloads()
            self.logger.info("downloader_agent", f"Возвращено в очередь {requeued_count} 'зависших' задач.")
            if requeued_count > 0:
                self._broadcast_queue_update()

    def run(self):
        self.logger.info(f"{self.name} запущен.")
        time.sleep(5)
        self.recover_tasks()

        while not self.shutdown_flag.is_set():
            # 3. Заменяем shutdown_flag.wait() на select()
            readable, _, _ = select.select([self._shutdown_pipe_r], [], [], self.CHECK_INTERVAL)
            if readable:
                break

            try:
                self._tick()
            except Exception as e:
                self.logger.error("downloader_agent", f"Критическая ошибка в такте: {e}", exc_info=True)
        
        if self.executor:
            self.logger.info(f"{self.name}: Ожидание завершения всех активных загрузок...")
            # Принудительная остановка без ожидания, чтобы сервис мог быстро закрыться.
            # Задачи продолжат выполняться, но основной поток не будет заблокирован.
            self.executor.shutdown(wait=False)
            
        # 4. Очищаем ресурсы pipe после выхода из цикла
        os.close(self._shutdown_pipe_r)
        os.close(self._shutdown_pipe_w)
        self.logger.info(f"{self.name} был остановлен.")

    def shutdown(self):
        self.logger.info(f"{self.name}: получен сигнал на остановку.")
        self.shutdown_flag.set()
        try:
            # 5. Пишем в pipe, чтобы мгновенно разбудить поток из select()
            os.write(self._shutdown_pipe_w, b'x')
        except OSError:
            pass
