# Файл: agents/renaming_agent.py

import threading
import time
import os
from flask import Flask
from db import Database
from logger import Logger
from rule_engine import RuleEngine
from filename_formatter import FilenameFormatter
from logic.metadata_processor import build_final_metadata

class RenamingAgent(threading.Thread):
    def __init__(self, app: Flask, logger: Logger, db: Database):
        super().__init__(daemon=True)
        self.name = "RenamingAgent"
        self.app = app
        self.logger = logger
        self.db = db
        self.shutdown_flag = threading.Event()
        self.trigger_event = threading.Event()

    def trigger(self):
        self.trigger_event.set()

    def recover_tasks(self):
        with self.app.app_context():
            requeued_count = self.db.requeue_stuck_renaming_tasks()
            if requeued_count > 0:
                self.logger.info("renaming_agent", f"Возвращено в очередь {requeued_count} 'зависших' задач.")
                self.trigger()

    def _process_task(self, task):
        task_id = task['id']
        unique_id = task['media_item_unique_id']
        old_path = task['old_path']
        new_path = task['new_path']
        series_id = task['series_id']

        try:
            self.db.update_renaming_task(task_id, {'status': 'in_progress', 'attempts': task['attempts'] + 1})

            media_item = self.db.get_media_item_by_uid(unique_id)
            if not media_item:
                raise FileNotFoundError("Связанный media_item не найден в БД.")
            
            series = self.db.get_series(series_id)
            if not series:
                 raise FileNotFoundError(f"Сериал с ID {series_id} не найден.")

            if media_item.get('slicing_status') == 'slicing':
                raise Exception("Файл используется агентом нарезки. Попытка будет позже.")

            if os.path.exists(old_path):
                os.rename(old_path, new_path)
                self.logger.info("renaming_agent", f"Файл переименован: {os.path.basename(old_path)} -> {os.path.basename(new_path)}")
            elif os.path.exists(new_path):
                 self.logger.info("renaming_agent", f"Файл уже был переименован: {os.path.basename(new_path)}")
            else:
                 self.logger.warning("renaming_agent", f"Исходный файл не найден: {old_path}. Пропускаем, но обработаем дочерние.")
            
            self.db.update_media_item_filename(unique_id, new_path)

            sliced_children = self.db.get_sliced_files_for_source(unique_id)
            if sliced_children:
                self.logger.info("renaming_agent", f"Обнаружено {len(sliced_children)} дочерних файлов. Запуск каскадного переименования.")
                
                engine = RuleEngine(self.db, self.logger)
                formatter = FilenameFormatter(self.logger)
                profile_id = series.get('parser_profile_id')
                source_title = media_item.get('source_title')

                if not (profile_id and source_title):
                    raise Exception("Отсутствует профиль или исходное имя для генерации имен дочерних файлов.")

                processed_result = engine.process_videos(profile_id, [{'title': source_title}])[0]
                rule_engine_data = processed_result.get('result', {}).get('extracted', {})
                parent_metadata = build_final_metadata(series, media_item, rule_engine_data)
                
                for child in sliced_children:
                    child_old_path = child.get('file_path')
                    
                    child_metadata = parent_metadata.copy()
                    child_metadata['episode'] = child.get('episode_number')
                    child_metadata.pop('start', None)
                    child_metadata.pop('end', None)
                    
                    child_new_path = formatter.format_filename(series, child_metadata, child_old_path)

                    if child_old_path != child_new_path:
                        if os.path.exists(child_old_path):
                            os.rename(child_old_path, child_new_path)
                            self.db.update_sliced_file_path(child['id'], child_new_path)
                            self.logger.info("renaming_agent", f"  -> Дочерний файл переименован: {os.path.basename(child_old_path)} -> {os.path.basename(child_new_path)}")
                        elif os.path.exists(child_new_path):
                            self.logger.info("renaming_agent", f"  -> Дочерний файл уже переименован: {os.path.basename(child_new_path)}")
                            if child_old_path != child_new_path:
                                self.db.update_sliced_file_path(child['id'], child_new_path)
                        else:
                            self.logger.warning("renaming_agent", f"  -> Дочерний файл не найден: {os.path.basename(child_old_path)}")
            
            self.db.delete_renaming_task(task_id)

        except Exception as e:
            error_message = str(e)
            self.logger.error("renaming_agent", f"Ошибка при переименовании (задача ID {task_id}): {error_message}", exc_info=True)
            self.db.update_renaming_task(task_id, {'status': 'error', 'error_message': error_message})

    def run(self):
        self.logger.info(f"{self.name} запущен.")
        time.sleep(15)
        self.recover_tasks()

        while not self.shutdown_flag.is_set():
            self.trigger_event.wait(timeout=10.0)
            if not self.trigger_event.is_set():
                continue

            self.logger.info("renaming_agent", "Агент пробудился. Проверка очереди задач...")
            processed_series_ids = set()

            with self.app.app_context():
                while True:
                    task = self.db.get_pending_renaming_task()
                    if not task:
                        break 
                    
                    processed_series_ids.add(task['series_id'])
                    self._process_task(task)
            
            if processed_series_ids:
                with self.app.app_context():
                    for series_id in processed_series_ids:
                        self.logger.info("renaming_agent", f"Отправка сигнала о завершении переименования для series_id: {series_id}")
                        self.app.sse_broadcaster.broadcast('renaming_complete', {'series_id': series_id})
            
            self.trigger_event.clear()
            self.logger.info("renaming_agent", "Очередь обработана. Агент уходит в режим ожидания.")

    def shutdown(self):
        self.logger.info(f"{self.name}: получен сигнал на остановку.")
        self.shutdown_flag.set()
        self.trigger_event.set()