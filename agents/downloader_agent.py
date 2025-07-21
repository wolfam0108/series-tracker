# downloader_agent.py

import threading
import time
import json
from flask import Flask
from db import Database
from logger import Logger
from downloader import Downloader
from concurrent.futures import ThreadPoolExecutor
from sse import ServerSentEvent

class DownloaderAgent(threading.Thread):
    def __init__(self, app: Flask, logger: Logger, db: Database, broadcaster: ServerSentEvent):
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

    def _broadcast_queue_update(self):
        """Собирает активные задачи и транслирует их через SSE."""
        with self.app.app_context():
            active_tasks = self.db.get_active_download_tasks()
            self.broadcaster.broadcast('download_queue_update', active_tasks)

    # ---> ЗАМЕНИТЕ СУЩЕСТВУЮЩИЙ МЕТОД _aggregate_statuses НА ЭТОТ <---
    def _aggregate_statuses(self, statuses: dict) -> str:
        """Агрегирует статусы загрузок в единую JSON-строку для поля state."""
        new_state = {}
        idx = 0
        # ---> ИСПРАВЛЕНИЕ: Здесь имя аргумента 'statuses', поэтому код был корректен,
        # но для единообразия и ясности приведем его к общему виду. <---
        if statuses.get('downloading', 0) > 0:
            new_state[str(idx)] = 'downloading'; idx += 1
        if statuses.get('completed', 0) > 0:
            new_state[str(idx)] = 'ready'; idx += 1
        if statuses.get('error', 0) > 0:
            new_state[str(idx)] = 'error'; idx += 1

        if statuses.get('pending', 0) > 0:
            new_state[str(idx)] = 'waiting'; idx += 1

        if not new_state:
             new_state[str(idx)] = 'waiting'; idx += 1

        return json.dumps(new_state) if new_state else 'waiting'

    def _update_and_broadcast_series_status(self, series_id: int):
        """
        Пересчитывает общий статус сериала на основе всех его медиа-элементов
        и немедленно отправляет обновление на главную страницу.
        """
        with self.app.app_context():
            try:
                download_statuses = self.db.get_series_download_statuses(series_id)
                new_state_str = self._aggregate_statuses(download_statuses)
                self.db.set_series_state(series_id, new_state_str)
                
                series_data = self.db.get_series(series_id)
                if series_data:
                    if series_data.get('last_scan_time'):
                        series_data['last_scan_time'] = series_data['last_scan_time'].isoformat()
                    self.broadcaster.broadcast('series_updated', series_data)
                self.logger.info("downloader_agent", f"Мгновенно обновлен статус для series_id: {series_id}")
            except Exception as e:
                self.logger.error("downloader_agent", f"Ошибка при мгновенном обновлении статуса для series_id {series_id}: {e}", exc_info=True)

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

    def _download_task_worker(self, task_id, video_url, save_path, unique_id, series_id):
        with self.app.app_context():
            try:
                self.logger.info("downloader_agent", f"Воркер начал обработку задачи {task_id}.")
                downloader = Downloader(self.logger)
                success, error_msg = downloader.download_video(video_url, save_path)
                
                if success:
                    self.db.update_media_item_filename(unique_id, save_path)
                    self.db.update_media_item_download_status(unique_id, 'completed')
                    self.db.delete_download_task(task_id)
                else:
                    self.logger.error("downloader_agent", f"Задача {task_id} завершилась с ошибкой. Статус будет обновлен. Ошибка: {error_msg}")
                    self.db.update_download_task_status(task_id, 'error', error_message=error_msg)
                    self.db.update_media_item_download_status(unique_id, 'error')

            except Exception as e:
                self.logger.error("downloader_agent", f"Критическая ошибка в воркере для задачи {task_id}: {e}", exc_info=True)
                self.db.update_download_task_status(task_id, 'error', error_message="Internal worker error")
                self.db.update_media_item_download_status(unique_id, 'error')
            finally:
                self._update_and_broadcast_series_status(series_id)
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
                    # Мы берем series_id из первой задачи, предполагая, что все они из одной пачки
                    series_id_to_update = None
                    for task in pending_tasks:
                        task_id = task['id']
                        unique_id = task['unique_id']
                        series_id = task['series_id']
                        series_id_to_update = series_id
                        
                        self.db.update_download_task_status(task_id, 'downloading')
                        self.db.update_media_item_download_status(unique_id, 'downloading')
                        
                        future = self.executor.submit(
                            self._download_task_worker,
                            task_id, task['video_url'], task['save_path'], unique_id, series_id
                        )
                        future.add_done_callback(self._task_done_callback)
                        
                        with self.lock:
                            self.active_futures[task_id] = future
                        
                        self.logger.info("downloader_agent", f"Задача ID {task_id} отправлена в пул на выполнение.")
                    
                    self._broadcast_queue_update()
                    if series_id_to_update:
                        self._update_and_broadcast_series_status(series_id_to_update)
    
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
            try:
                self._tick()
            except Exception as e:
                self.logger.error("downloader_agent", f"Критическая ошибка в такте: {e}", exc_info=True)
            self.shutdown_flag.wait(self.CHECK_INTERVAL)
        
        if self.executor:
            self.logger.info(f"{self.name}: Ожидание завершения всех активных загрузок...")
            self.executor.shutdown(wait=True)
        self.logger.info(f"{self.name} был остановлен.")

    def shutdown(self):
        self.logger.info(f"{self.name}: получен сигнал на остановку.")
        self.shutdown_flag.set()