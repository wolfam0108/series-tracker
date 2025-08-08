import threading
import time
import os
import json
from flask import Flask
from db import Database
from logger import Logger
from filename_formatter import FilenameFormatter
from logic.metadata_processor import build_final_metadata
from auth import AuthManager
from qbittorrent import QBittorrentClient
from rule_engine import RuleEngine

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
        """Пробуждает агент для проверки очереди задач."""
        self.trigger_event.set()

    def recover_tasks(self):
        """Восстанавливает прерванные задачи при старте агента."""
        with self.app.app_context():
            requeued_count = self.db.requeue_stuck_renaming_tasks()
            if requeued_count > 0:
                self.logger.info("renaming_agent", f"Возвращено в очередь {requeued_count} 'зависших' задач.")
                self.trigger()

    def run(self):
        """Основной цикл работы агента."""
        self.logger.info(f"{self.name} запущен.")
        time.sleep(15)
        self.recover_tasks()

        while not self.shutdown_flag.is_set():
            self.trigger_event.wait()
            if self.shutdown_flag.is_set():
                break

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

    def _process_task(self, task):
        """Главный метод-диспетчер."""
        task_id = task['id']
        task_type = task.get('task_type', 'single_vk')

        self.logger.info("renaming_agent", f"Обработка задачи ID {task_id}, тип: {task_type}")
        self.db.update_renaming_task(task_id, {'status': 'in_progress'})

        try:
            if task_type == 'mass_torrent_reprocess':
                self._process_mass_torrent_task(task)
            elif task_type == 'mass_vk_reprocess':
                self._process_mass_vk_task(task)
            
            self.db.delete_renaming_task(task_id)
            self.logger.info("renaming_agent", f"Задача ID {task_id} успешно завершена.")

        except Exception as e:
            self.logger.error("renaming_agent", f"Ошибка при обработке задачи ID {task_id}: {e}", exc_info=True)
            self.db.update_renaming_task(task_id, {'status': 'error', 'error_message': str(e)})

    def _process_mass_vk_task(self, task):
        """Обрабатывает пакетную задачу для VK-файлов с расширенным логированием."""
        series_id = task['series_id']
        with self.app.app_context():
            series = self.db.get_series(series_id)
            if not series or not series.get('parser_profile_id'):
                self.logger.warning("renaming_agent", f"Пропуск mass_vk_reprocess для series_id {series_id}: сериал или профиль не найден.")
                return

            engine = RuleEngine(self.db, self.logger)
            formatter = FilenameFormatter(self.logger)
            profile_id = series['parser_profile_id']
            base_path = series['save_path']

            media_items = self.db.get_media_items_for_series(series_id)
            media_items_map = {item['unique_id']: item for item in media_items}

            self.logger.info("renaming_agent", f"Начало переименования для {len(media_items)} медиа-элементов...")
            for item in media_items:
                is_downloaded = item.get('status') == 'completed' and item.get('final_filename')
                if not is_downloaded:
                    continue
                
                old_relative_path = item['final_filename']
                source_title = item.get('source_title')
                if not source_title: continue

                processed = engine.process_videos(profile_id, [{'title': source_title}])[0]
                rule_data = processed.get('result', {}).get('extracted', {})
                final_metadata = build_final_metadata(series, item, rule_data)
                new_relative_path = formatter.format_filename(series, final_metadata, old_relative_path)

                if old_relative_path != new_relative_path:
                    old_abs_path = os.path.join(base_path, old_relative_path)
                    new_abs_path = os.path.join(base_path, new_relative_path)
                    
                    self.logger.debug("renaming_agent", f"--- Проверка Media Item (UID: {item['unique_id']}) ---")
                    self.logger.debug("renaming_agent", f"Старый путь: {old_abs_path}")
                    self.logger.debug("renaming_agent", f"Новый путь:  {new_abs_path}")

                    if os.path.exists(new_abs_path):
                        self.logger.warning("renaming_agent", "-> Файл с новым именем уже существует. Пропуск.")
                    elif not os.path.exists(old_abs_path):
                        self.logger.error("renaming_agent", f"-> Исходный файл НЕ НАЙДЕН по пути {old_abs_path}. Пропуск.")
                    else:
                        try:
                            os.rename(old_abs_path, new_abs_path)
                            self.logger.info("renaming_agent", f"-> УСПЕХ: Файл переименован.")
                        except OSError as e:
                            self.logger.error("renaming_agent", f"-> ОШИБКА OS.RENAME: {e}")
                    
                    self.db.update_media_item_filename(item['unique_id'], new_relative_path)

            sliced_files = self.db.get_all_sliced_files_for_series(series_id)
            if sliced_files:
                self.logger.info("renaming_agent", f"Начало переименования для {len(sliced_files)} нарезанных файлов...")
            for child in sliced_files:
                parent = media_items_map.get(child['source_media_item_unique_id'])
                if not parent: continue

                child_old_relative_path = child['file_path']
                
                parent_source_title = parent.get('source_title')
                parent_rule_data = {}
                if parent_source_title:
                    parent_processed = engine.process_videos(profile_id, [{'title': parent_source_title}])[0]
                    parent_rule_data = parent_processed.get('result', {}).get('extracted', {})
                
                parent_metadata = build_final_metadata(series, parent, parent_rule_data)
                child_metadata = parent_metadata.copy()
                child_metadata['episode'] = child['episode_number']
                
                child_new_relative_path = formatter.format_filename(series, child_metadata, child_old_relative_path)

                if child_old_relative_path != child_new_relative_path:
                    child_old_abs_path = os.path.join(base_path, child_old_relative_path)
                    child_new_abs_path = os.path.join(base_path, child_new_relative_path)

                    self.logger.debug("renaming_agent", f"--- Проверка Sliced File (ID: {child['id']}) ---")
                    self.logger.debug("renaming_agent", f"Старый путь: {child_old_abs_path}")
                    self.logger.debug("renaming_agent", f"Новый путь:  {child_new_abs_path}")

                    if os.path.exists(child_new_abs_path):
                        self.logger.warning("renaming_agent", "-> Файл с новым именем уже существует.")
                    elif not os.path.exists(child_old_abs_path):
                        self.logger.error("renaming_agent", f"-> Исходный нарезанный файл НЕ НАЙДЕН по пути {child_old_abs_path}.")
                    else:
                        try:
                            os.rename(child_old_abs_path, child_new_abs_path)
                            self.logger.info("renaming_agent", "-> УСПЕХ: Нарезанный файл переименован.")
                        except OSError as e:
                            self.logger.error("renaming_agent", f"-> ОШИБКА OS.RENAME для нарезанного файла: {e}")

                    self.db.update_sliced_file_path(child['id'], child_new_relative_path)

    def _process_mass_torrent_task(self, task):
        """
        Обрабатывает пакетную задачу на переобработку и переименование
        всех файлов торрент-сериала.
        """
        series_id = task['series_id']
        with self.app.app_context():
            series = self.db.get_series(series_id)
            if not series or not series.get('parser_profile_id'):
                self.logger.warning("renaming_agent", f"Пропуск mass_torrent_reprocess для series_id {series_id}: сериал или профиль не найден.")
                return

            self.logger.info("renaming_agent", f"Запуск переобработки файлов для series_id: {series_id}")
            
            engine = RuleEngine(self.db, self.logger)
            formatter = FilenameFormatter(self.logger)
            auth_manager = AuthManager(self.db, self.logger)
            qb_client = QBittorrentClient(auth_manager, self.db, self.logger)
            profile_id = series.get('parser_profile_id')

            active_torrents = self.db.get_torrents(series_id, is_active=True)
            for torrent_db_entry in active_torrents:
                qb_hash = torrent_db_entry.get('qb_hash')
                if not qb_hash: continue

                self.logger.info("renaming_agent", f"Обработка торрента {qb_hash[:8]}...")
                
                files_in_qbit = qb_client.get_torrent_files_by_hash(qb_hash)
                if not files_in_qbit: continue
                
                files_in_db_map = {f['original_path']: f for f in self.db.get_torrent_files_for_torrent(torrent_db_entry['id'])}

                files_to_update_in_db = []
                video_extensions = ['.mkv', '.avi', '.mp4', '.mov', '.wmv', '.webm']

                for current_path in files_in_qbit:
                    if not any(current_path.lower().endswith(ext) for ext in video_extensions):
                        continue

                    db_record = next((r for r in files_in_db_map.values() if (r.get('renamed_path') or r['original_path']) == current_path), None)
                    original_path = db_record['original_path'] if db_record else current_path
                    
                    basename_for_rules = os.path.basename(original_path)
                    processed_result = engine.process_videos(profile_id, [{'title': basename_for_rules}])[0]
                    extracted_data = processed_result.get('result', {}).get('extracted', {})

                    final_renamed_path = None
                    file_status = 'skipped'

                    has_episode = extracted_data.get('episode') is not None or extracted_data.get('start') is not None
                    if has_episode:
                        target_new_path = formatter.format_filename(series, extracted_data, original_path)
                        
                        if current_path == target_new_path:
                            file_status = 'renamed'
                            final_renamed_path = current_path
                        else:
                            success = qb_client.rename_file(qb_hash, current_path, target_new_path)
                            if success:
                                file_status = 'renamed'
                                final_renamed_path = target_new_path
                            else:
                                file_status = 'rename_error'
                    
                    files_to_update_in_db.append({
                        "original_path": original_path,
                        "renamed_path": final_renamed_path,
                        "status": file_status,
                        "extracted_metadata": json.dumps(extracted_data)
                    })

                if files_to_update_in_db:
                    self.db.add_or_update_torrent_files(torrent_db_entry['id'], files_to_update_in_db)