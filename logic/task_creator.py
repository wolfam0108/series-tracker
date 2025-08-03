# Файл: logic/task_creator.py

from db import Database
from logger import Logger
from rule_engine import RuleEngine
from filename_formatter import FilenameFormatter
from .metadata_processor import build_final_metadata # <-- Новый импорт

def create_renaming_tasks_for_series(series_id: int, flask_app):
    with flask_app.app_context():
        db: Database = flask_app.db
        logger: Logger = flask_app.logger
        
        if db.is_series_being_downloaded(series_id):
            return
            
        series = db.get_series(series_id)
        if not series or not series.get('parser_profile_id'):
            return

        items_to_check = db.get_media_items_for_series(series_id)
        engine = RuleEngine(db, logger)
        formatter = FilenameFormatter(logger)
        tasks_created = 0

        for item in items_to_check:
            is_downloaded = item.get('status') == 'completed' and item.get('final_filename')
            is_processed_compilation = item.get('slicing_status') in ['completed', 'completed_with_errors']
            if not (is_downloaded or is_processed_compilation):
                continue

            source_title = item.get('source_title')
            if not source_title:
                continue
            
            old_path = item.get('final_filename')

            # --- ИЗМЕНЕНИЕ: Используем центральную функцию ---
            processed_result = engine.process_videos(series.get('parser_profile_id'), [{'title': source_title}])[0]
            rule_engine_data = processed_result.get('result', {}).get('extracted', {})
            final_metadata = build_final_metadata(series, item, rule_engine_data)
            new_path = formatter.format_filename(series, final_metadata, old_path)
            # --- КОНЕЦ ИЗМЕНЕНИЯ ---

            should_create_task = (old_path and old_path != new_path) or (not old_path and is_processed_compilation)
            if should_create_task:
                task_data = {
                    'series_id': series_id,
                    'media_item_unique_id': item['unique_id'],
                    'old_path': old_path or new_path,
                    'new_path': new_path
                }
                if db.create_renaming_task(task_data):
                    tasks_created += 1
        
        if tasks_created > 0:
            logger.info("task_creator", f"Создано {tasks_created} задач на переименование для series_id {series_id}.")
            flask_app.renaming_agent.trigger()