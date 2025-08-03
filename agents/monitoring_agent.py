# Файл: agents/monitoring_agent.py

import threading
import time
import json
import os
import re
import select
from datetime import datetime, timedelta, timezone
from flask import Flask
from db import Database
from logger import Logger
from scanner import perform_series_scan
from sse import ServerSentEvent
from auth import AuthManager
from qbittorrent import QBittorrentClient
from status_manager import StatusManager
from filename_formatter import FilenameFormatter
from utils.chapter_parser import get_chapters
# --- ИЗМЕНЕНИЕ: Импортируем централизованную функцию ---
from logic.metadata_processor import build_final_metadata

class MonitoringAgent(threading.Thread):
    def __init__(self, app: Flask, logger: Logger, db: Database, broadcaster: ServerSentEvent, status_manager: StatusManager):
        super().__init__(daemon=True)
        self.name = "MonitoringAgent"
        self.app = app
        self.logger = logger
        self.db = db
        self.broadcaster = broadcaster
        self.status_manager = status_manager
        self.shutdown_flag = threading.Event()
        self.scan_in_progress_flag = threading.Event()
        self.awaiting_tasks_flag = threading.Event()
        self.CHECK_INTERVAL = 10 
        self.STATUS_UPDATE_INTERVAL = 5
        self.FILE_VERIFY_INTERVAL = 60
        self.last_status_update_time = time.time()
        self.last_file_verify_time = time.time()
        self.qb_client = None
        self._shutdown_pipe_r, self._shutdown_pipe_w = os.pipe()

    def _broadcast_scanner_status(self):
        with self.app.app_context():
            status = self.get_status()
            self.broadcaster.broadcast('scanner_status_update', status)

    def verify_sliced_files_for_series(self, series_id: int):
        with self.app.app_context():
            source_items = self.db.get_media_items_by_slicing_status(series_id, 'pending')
            source_items.extend(self.db.get_media_items_by_slicing_status(series_id, 'completed'))
            source_items.extend(self.db.get_media_items_by_slicing_status(series_id, 'completed_with_errors'))
            if not source_items:
                return

            series = self.db.get_series(series_id)
            if not series: return

            for item in source_items:
                # --- ИЗМЕНЕНИЕ: Логика проверки теперь использует build_final_metadata для консистентности ---
                # Вместо наследования имени, мы генерируем его по тем же правилам, что и другие модули,
                # чтобы гарантировать совпадение.
                unique_id = item['unique_id']
                chapters_str = item.get('chapters')
                if not chapters_str:
                    continue

                chapters = json.loads(chapters_str)
                expected_count = len(chapters)
                found_on_disk = 0
                
                # Получаем полные метаданные для родителя один раз
                parent_metadata = build_final_metadata(series, item, {})
                formatter = FilenameFormatter(self.logger)

                for i, chapter in enumerate(chapters):
                    episode_number = item['episode_start'] + i
                    
                    # Создаем метаданные для дочернего файла
                    child_metadata = parent_metadata.copy()
                    child_metadata['episode'] = episode_number
                    child_metadata.pop('start', None)
                    child_metadata.pop('end', None)

                    expected_filename = formatter.format_filename(series, child_metadata)
                    expected_path = os.path.join(series['save_path'], expected_filename)
                    
                    if os.path.exists(expected_path):
                        self.db.add_sliced_file_if_not_exists(series['id'], unique_id, episode_number, expected_path)
                        found_on_disk += 1

                # Обновляем статусы на основе проверки
                current_status = item.get('slicing_status')
                new_status = current_status
                known_in_db = self.db.get_sliced_files_for_source(unique_id)

                if len(known_in_db) < expected_count or found_on_disk < expected_count:
                    new_status = 'completed_with_errors'
                elif len(known_in_db) == expected_count and found_on_disk == expected_count:
                    new_status = 'completed'

                if new_status != current_status:
                    self.logger.info("monitoring_agent", f"Статус нарезки для UID {unique_id} обновлен на '{new_status}' после проверки файлов.")
                    self.db.update_media_item_slicing_status_by_uid(unique_id, new_status)

    def get_status(self) -> dict:
        next_scan_timestamp_iso = self.db.get_setting('next_scan_timestamp')
        next_scan_time = None
        if next_scan_timestamp_iso:
            try:
                next_scan_time = datetime.fromisoformat(next_scan_timestamp_iso).replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                next_scan_time = None

        return {
            'scanner_enabled': self.db.get_setting('scanner_agent_enabled', 'false') == 'true',
            'scan_interval': int(self.db.get_setting('scan_interval_minutes', 60)),
            'is_scanning': self.scan_in_progress_flag.is_set(),
            'is_awaiting_tasks': self.awaiting_tasks_flag.is_set(),
            'next_scan_time': next_scan_time.isoformat() if next_scan_time else None,
        }
        
    def sync_single_series_filesystem(self, series_id):
        with self.app.app_context():
            series = self.db.get_series(series_id)
            if not series or series.get('source_type') != 'vk_video':
                return

            formatter = FilenameFormatter(self.logger)
            changed = False
            items_to_check = self.db.get_media_items_for_series(series_id)

            for item in items_to_check:
                if item.get('plan_status') not in ['in_plan_single', 'in_plan_compilation']:
                    continue
                
                if item.get('slicing_status') == 'completed' and item.get('final_filename') is None:
                    continue

                is_new_compilation = (
                    bool(item.get('episode_end')) and
                    item.get('status') == 'pending' and
                    item.get('slicing_status') == 'none' and
                    not item.get('final_filename')
                )

                if is_new_compilation:
                    self.logger.info("monitoring_agent", f"Новая компиляция {item['unique_id']}. Запуск глубокой проверки нарезанных файлов...")
                    try:
                        chapters = get_chapters(item['source_url'])
                        if not chapters:
                            self.logger.warning("monitoring_agent", f"Не удалось получить оглавление для UID {item['unique_id']}.")
                            continue

                        self.db.update_media_item_chapters(item['unique_id'], json.dumps(chapters))
                        
                        expected_children_count = len(chapters)
                        found_children_count = 0
                        
                        compilation_metadata = build_final_metadata(series, item, {})
                        parent_hypothetical_name = formatter.format_filename(series, compilation_metadata)

                        for i, chapter in enumerate(chapters):
                            episode_number = item['episode_start'] + i
                            parent_basename = os.path.basename(parent_hypothetical_name)
                            base_name, extension = os.path.splitext(parent_basename)
                            episode_pattern = r's(\d{2,})e(\d{2,})(-e\d{2,})?'
                            season_number = item.get('season', 1)
                            new_episode_part = f"s{season_number:02d}e{episode_number:02d}"
                            new_base_name = re.sub(episode_pattern, new_episode_part, base_name, flags=re.IGNORECASE)
                            expected_filename = (new_base_name + extension)
                            expected_path = os.path.join(series['save_path'], expected_filename)

                            if os.path.exists(expected_path):
                                self.db.add_sliced_file_if_not_exists(series_id, item['unique_id'], episode_number, expected_path)
                                found_children_count += 1
                        
                        if found_children_count == expected_children_count and expected_children_count > 0:
                            self.logger.info("monitoring_agent", f"УСПЕХ! Все {found_children_count} нарезанных файлов для UID {item['unique_id']} найдены. Усыновляем компиляцию.")
                            self.db.update_media_item_slicing_status(item['unique_id'], 'completed')
                            self.db.set_media_item_ignored_status_by_uid(item['unique_id'], True)
                            self.db.update_media_item_download_status(item['unique_id'], 'completed')
                            self.db.update_media_item_filename(item['unique_id'], None)
                            changed = True
                    
                    except Exception as e:
                        self.logger.error("monitoring_agent", f"Ошибка во время глубокого усыновления для UID {item['unique_id']}: {e}", exc_info=True)

                elif item['status'] == 'pending':
                    metadata = build_final_metadata(series, item, {})
                    expected_filename = formatter.format_filename(series, metadata)
                    expected_path = os.path.join(series['save_path'], expected_filename)
                    
                    if os.path.exists(expected_path):
                        self.db.register_downloaded_media_item(item['unique_id'], expected_path)
                        self.logger.info("monitoring_agent", f"Усыновлен существующий одиночный файл: {expected_filename}")
                        changed = True

            # --- РЕЖИМ 2: СТАНДАРТНАЯ ПРОВЕРКА (ДЛЯ УЖЕ СКАЧАННЫХ ФАЙЛОВ) ---
            completed_items = self.db.get_media_items_by_status(series_id, 'completed')
            for item in completed_items:
                # --- ГЛАВНОЕ ИЗМЕНЕНИЕ ---
                # Пропускаем проверку, если это компиляция, которая была успешно нарезана.
                # Это предотвратит сброс статуса для "архивных" компиляций.
                if item.get('slicing_status') in ['completed', 'completed_with_errors']:
                    continue
                # --- КОНЕЦ ИЗМЕНЕНИЯ ---

                file_path = item.get('final_filename')
                if file_path and not os.path.exists(file_path):
                    self.db.reset_media_item_download_state(item['unique_id'])
                    self.logger.warning("monitoring_agent", f"Файл пропал: {file_path}. Статус сброшен.")
                    changed = True
            
            if changed:
                self.status_manager.sync_vk_statuses(series_id)
    
    def _periodic_filesystem_sync(self):
        with self.app.app_context():
            all_series = self.db.get_all_series()
            for series in all_series:
                if series['source_type'] == 'vk_video':
                    self.sync_single_series_filesystem(series['id'])
                    self.verify_sliced_files_for_series(series['id'])

    def _update_active_statuses(self):
        with self.app.app_context():
            all_vk_series = [s for s in self.db.get_all_series() if s['source_type'] == 'vk_video']
            for series in all_vk_series:
                self.status_manager.sync_vk_statuses(series['id'])

            if not self.qb_client: return

            all_series_for_torrents = [s for s in self.db.get_all_series() if s['source_type'] == 'torrent']
            if not all_series_for_torrents:
                for series in all_series_for_torrents:
                    self.db.remove_stale_torrent_tasks(series['id'], [])
                    self.status_manager.sync_torrent_statuses(series['id'])
                return

            all_hashes = {t['qb_hash'] for s in all_series_for_torrents for t in self.db.get_torrents(s['id'], is_active=True) if t.get('qb_hash')}
            if not all_hashes:
                for series in all_series_for_torrents:
                    self.db.remove_stale_torrent_tasks(series['id'], [])
                    self.status_manager.sync_torrent_statuses(series['id'])
                return

            all_torrents_info = self.qb_client.get_torrents_info(list(all_hashes))
            if all_torrents_info is None:
                self.logger.warning("monitoring_agent", "Не удалось получить информацию о торрентах от qBittorrent.")
                return

            info_map = {info['hash']: info for info in all_torrents_info}
            active_hashes_from_qbit = list(info_map.keys())

            for series in all_series_for_torrents:
                series_id = series['id']
                series_torrents = self.db.get_torrents(series_id, is_active=True)
                active_hashes_in_series = {t['qb_hash'] for t in series_torrents if t.get('qb_hash')}

                for torrent_hash in active_hashes_in_series:
                    if torrent_hash in info_map:
                        self.db.update_or_create_torrent_task(series_id, torrent_hash, info_map[torrent_hash])

                self.db.remove_stale_torrent_tasks(series_id, active_hashes_from_qbit)
                
                self.status_manager.sync_torrent_statuses(series_id)

    def run(self):
        self.logger.info(f"{self.name} запущен.")
        time.sleep(5)

        with self.app.app_context():
            auth_manager = AuthManager(self.db, self.logger)
            self.qb_client = QBittorrentClient(auth_manager, self.db, self.logger)
            self.logger.info("monitoring_agent", "Выполнение первоначальной проверки статусов файлов...")
            self._periodic_filesystem_sync()
            self.logger.info("monitoring_agent", "Первоначальная проверка завершена.")
            self.handle_startup_scan()

        while not self.shutdown_flag.is_set():
            readable, _, _ = select.select([self._shutdown_pipe_r], [], [], self.CHECK_INTERVAL)
            if readable:
                break

            with self.app.app_context():
                try:
                    now = time.time()
                    if (now - self.last_status_update_time) >= self.STATUS_UPDATE_INTERVAL:
                        self._update_active_statuses()
                        self._check_stale_viewing_statuses()
                        self.last_status_update_time = now
                        self.broadcaster.broadcast('agent_heartbeat', {'name': 'monitoring', 'activity': 'qbit_check'})

                    if (now - self.last_file_verify_time) >= self.FILE_VERIFY_INTERVAL:
                        self._periodic_filesystem_sync()
                        self.last_file_verify_time = now
                        self.broadcaster.broadcast('agent_heartbeat', {'name': 'monitoring', 'activity': 'file_verify'})

                    self._tick()
                except Exception as e:
                    self.logger.error("monitoring_agent", f"Критическая ошибка в такте MonitoringAgent: {e}", exc_info=True)
        
        os.close(self._shutdown_pipe_r)
        os.close(self._shutdown_pipe_w)
        self.logger.info(f"{self.name} был остановлен.")

    def handle_startup_scan(self):
        with self.app.app_context():
            status = self.get_status()
            if not status['scanner_enabled']:
                self.logger.info("monitoring_agent", "Автоматическое сканирование отключено, запуск при старте пропущен.")
                return

            next_scan_time_str = status.get('next_scan_time')
            
            if not next_scan_time_str:
                self.logger.info("monitoring_agent", "Время следующего сканирования не назначено. Запускаем сейчас.")
                self.trigger_scan_all()
                return
                
            next_scan_time = datetime.fromisoformat(next_scan_time_str)
            now = datetime.now(timezone.utc)
            
            if now >= next_scan_time:
                self.logger.info("monitoring_agent", "Обнаружено пропущенное время сканирования. Запускаем сейчас.")
                self.trigger_scan_all()
            else:
                self.logger.info("monitoring_agent", f"Следующее сканирование назначено на {next_scan_time}. Ожидание.")
                self._broadcast_scanner_status()

    def _tick(self):
        with self.app.app_context():
            status = self.get_status()

            if self.awaiting_tasks_flag.is_set():
                if len(self.app.agent.processing_torrents) == 0:
                    self.logger.info("monitoring_agent", "Очередь основного агента пуста. Завершение цикла сканирования.")
                    self.awaiting_tasks_flag.clear()
                    
                    interval_minutes = int(self.db.get_setting('scan_interval_minutes', 60))
                    next_scan_time = datetime.now(timezone.utc) + timedelta(minutes=interval_minutes)
                    self.db.set_setting('next_scan_timestamp', next_scan_time.isoformat())
                    self.logger.info("monitoring_agent", f"Следующее сканирование назначено на {next_scan_time.isoformat()}.")
                    self._broadcast_scanner_status()
                return

            if not status['scanner_enabled'] or status['is_scanning']:
                return

            next_scan_time_str = status.get('next_scan_time')
            if not next_scan_time_str:
                return 

            next_scan_time = datetime.fromisoformat(next_scan_time_str)
            now_utc = datetime.now(timezone.utc)

            if now_utc >= next_scan_time:
                self.logger.info("monitoring_agent", "Настало время для планового сканирования.")
                self.trigger_scan_all()

    def trigger_scan_all(self, debug_force_replace: bool = False):
        if self.scan_in_progress_flag.is_set() or self.awaiting_tasks_flag.is_set():
            self.logger.warning("monitoring_agent", "Попытка запустить сканирование, когда оно уже идет или ожидает завершения.")
            return

        self.scan_in_progress_flag.set()
        
        with self.app.app_context():
            if not debug_force_replace:
                final_debug_force_replace = self.db.get_setting('debug_force_replace', 'false') == 'true'
            else:
                final_debug_force_replace = debug_force_replace
        
        self.logger.info("monitoring_agent", f"Установлен флаг 'сканирование в процессе'. Режим отладки: {final_debug_force_replace}")
        self._broadcast_scanner_status()
        
        scan_thread = threading.Thread(target=self._perform_full_scan, args=(final_debug_force_replace,))
        scan_thread.start()

    def _perform_full_scan(self, debug_force_replace: bool):
        with self.app.app_context():
            self.logger.info("monitoring_agent", "Начало полного цикла сканирования.")
            
            series_to_scan = self.db.get_all_series_for_auto_scan()
            if app.debug_manager.is_debug_enabled('monitoring_agent'):
                self.logger.debug("monitoring_agent", f"Найдено {len(series_to_scan)} сериалов для автоматического сканирования.")

            for series in series_to_scan:
                if self.shutdown_flag.is_set():
                    self.logger.warning("monitoring_agent", "Получен сигнал остановки во время цикла сканирования. Прерывание.")
                    break
                
                series_id = series['id']
                
                if self.db.get_all_agent_tasks_for_series(series_id):
                    if app.debug_manager.is_debug_enabled('monitoring_agent'):
                        self.logger.debug("monitoring_agent", f"Пропуск сканирования для '{series['name']}' (ID: {series_id}): активна задача агента.")
                    continue

                if app.debug_manager.is_debug_enabled('monitoring_agent'):
                    self.logger.debug("monitoring_agent", f"Запуск сканирования для '{series['name']}' (ID: {series['id']}).")
                try:
                    perform_series_scan(series['id'], self.status_manager, self.app, debug_force_replace)
                except Exception as e:
                    self.logger.error("monitoring_agent", f"Ошибка при сканировании сериала {series['id']}: {e}", exc_info=True)
                    self.status_manager.set_status(series['id'], 'error', True)
                    continue
            
            self.logger.info("monitoring_agent", "Полный цикл сканирования завершен. Переход в режим ожидания задач.")
            
            self.scan_in_progress_flag.clear()
            self.awaiting_tasks_flag.set()
            if app.debug_manager.is_debug_enabled('monitoring_agent'):
                self.logger.debug("monitoring_agent", "Снят флаг 'сканирование в процессе', установлен флаг 'ожидание задач'.")
            self._broadcast_scanner_status()

    def _check_stale_viewing_statuses(self):
        stale_series_ids = self.db.get_stale_viewing_series_ids(timeout_seconds=90)
        for series_id in stale_series_ids:
            self.logger.info("monitoring_agent", f"Обнаружен зависший статус 'Просмотр' для series_id {series_id}. Сброс.")
            self.db.set_viewing_status(series_id, False)
            self.status_manager._update_and_broadcast(series_id)

    def shutdown(self):
        self.logger.info(f"{self.name}: получен сигнал на остановку.")
        self.shutdown_flag.set()
        try:
            os.write(self._shutdown_pipe_w, b'x')
        except OSError:
            pass