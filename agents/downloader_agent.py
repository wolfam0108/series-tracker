import threading
import time
from flask import Flask
from db import Database
from logger import Logger
from downloader import Downloader
from concurrent.futures import ThreadPoolExecutor

class DownloaderAgent(threading.Thread):
    def __init__(self, app: Flask, logger: Logger, db: Database):
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

    def _download_task_worker(self, task_id, video_url, save_path, unique_id):
        with self.app.app_context():
            try:
                self.logger.info("downloader_agent", f"Воркер начал обработку задачи {task_id}.")
                self.db.update_media_item_download_status(unique_id, 'downloading')
                downloader = Downloader(self.logger)
                success, error_msg = downloader.download_video(video_url, save_path)
                
                if success:
                    self.db.update_media_item_filename(unique_id, save_path)
                    self.db.update_media_item_download_status(unique_id, 'completed')
                    # --- ИЗМЕНЕНИЕ: Удаляем задачу после успеха ---
                    self.db.delete_download_task(task_id)
                else:
                    self.db.update_download_task_status(task_id, 'error', error_message=error_msg)
                    self.db.update_media_item_download_status(unique_id, 'error')

            except Exception as e:
                self.logger.error("downloader_agent", f"Критическая ошибка в воркере для задачи {task_id}: {e}", exc_info=True)
                self.db.update_download_task_status(task_id, 'error', error_message="Internal worker error")
                self.db.update_media_item_download_status(unique_id, 'error')
        return task_id

    def _task_done_callback(self, future):
        try:
            task_id = future.result()
            with self.lock:
                if task_id in self.active_futures:
                    del self.active_futures[task_id]
            self.logger.info("downloader_agent", f"Задача {task_id} завершена и удалена из активного списка.")
        except Exception as e:
            self.logger.error("downloader_agent", f"Ошибка в колбэке завершения задачи: {e}", exc_info=True)

    def _tick(self):
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
                
                for task in pending_tasks:
                    task_id = task['id']
                    self.db.update_download_task_status(task_id, 'downloading')
                    
                    future = self.executor.submit(
                        self._download_task_worker,
                        task_id, task['video_url'], task['save_path'], task['unique_id']
                    )
                    future.add_done_callback(self._task_done_callback)
                    
                    with self.lock:
                        self.active_futures[task_id] = future
                    
                    self.logger.info("downloader_agent", f"Задача ID {task_id} отправлена в пул на выполнение.")

    def recover_tasks(self):
        with self.app.app_context():
            self.logger.info("downloader_agent", "Восстановление задач после перезапуска...")
            requeued_count = self.db.requeue_stuck_downloads()
            self.logger.info("downloader_agent", f"Возвращено в очередь {requeued_count} 'зависших' задач.")

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