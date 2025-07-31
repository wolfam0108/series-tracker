import threading
import time
import json
import os
import select
from datetime import datetime, timedelta, timezone
from flask import Flask, current_app as app
from db import Database
from logger import Logger
from scanner import perform_series_scan
from sse import ServerSentEvent
from auth import AuthManager
from qbittorrent import QBittorrentClient
from status_manager import StatusManager
from filename_formatter import FilenameFormatter

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
        # 2. Создаем "канал пробуждения"
        self._shutdown_pipe_r, self._shutdown_pipe_w = os.pipe()

    def _broadcast_scanner_status(self):
        with self.app.app_context():
            status = self.get_status()
            self.broadcaster.broadcast('scanner_status_update', status)

    def verify_sliced_files_for_series(self, series_id: int):
        """
        Проверяет наличие нарезанных файлов на диске для одного сериала.
        - "Усыновляет" файлы для компиляций в статусе 'pending'.
        - Проверяет целостность для компиляций в статусе 'completed'.
        """
        with self.app.app_context():
            # Ищем компиляции, которые либо ожидают нарезки, либо уже (возможно) нарезаны
            source_items = self.db.get_media_items_by_slicing_status(series_id, 'pending')
            source_items.extend(self.db.get_media_items_by_slicing_status(series_id, 'completed'))
            source_items.extend(self.db.get_media_items_by_slicing_status(series_id, 'completed_with_errors'))

            if not source_items:
                return

            formatter = FilenameFormatter(self.logger)
            series = self.db.get_series(series_id)
            if not series: return

            for item in source_items:
                unique_id = item['unique_id']
                source_file = item.get('final_filename')
                chapters_str = item.get('chapters')

                # Пропускаем, если нет данных для работы
                if not (source_file and chapters_str):
                    continue

                chapters = json.loads(chapters_str)
                expected_count = len(chapters)
                existing_files_count = 0

                # Проверяем наличие каждого ожидаемого файла
                for i, chapter in enumerate(chapters):
                    episode_number = item['episode_start'] + i
                    metadata = {'season': item.get('season'), 'episode': episode_number}
                    expected_filename = formatter.format_filename(series, metadata)
                    expected_path = os.path.join(os.path.dirname(source_file), expected_filename)

                    if os.path.exists(expected_path):
                        self.db.add_sliced_file_if_not_exists(series['id'], unique_id, episode_number, expected_path)
                        existing_files_count += 1

                # Принимаем решение о финальном статусе на основе найденных файлов
                current_status = item.get('slicing_status')
                new_status = current_status

                if current_status == 'pending':
                    if existing_files_count == expected_count:
                        new_status = 'completed'
                    elif existing_files_count > 0:
                        new_status = 'completed_with_errors'

                elif current_status in ['completed', 'completed_with_errors']:
                    known_sliced_files = self.db.get_sliced_files_for_source(unique_id)
                    if len(known_sliced_files) != existing_files_count:
                        # Если количество файлов на диске не совпадает с количеством в БД - есть проблема
                        new_status = 'completed_with_errors'
                    elif existing_files_count == expected_count:
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
        """
        Выполняет полную синхронизацию файлов (усыновление + проверка) для ОДНОГО сериала.
        Этот метод можно вызывать извне (например, из API).
        """
        with self.app.app_context():
            series = self.db.get_series(series_id)
            if not series or series.get('source_type') != 'vk_video':
                return

            formatter = FilenameFormatter(self.logger)
            changed = False

            # --- Блок 1: "Усыновление" ожидающих файлов ---
            pending_items = self.db.get_media_items_by_status(series_id, 'pending')
            for item in pending_items:
                if item['plan_status'] not in ['in_plan_single', 'in_plan_compilation']:
                    continue
                
                # Сначала создаем "плоский" словарь с метаданными
                metadata = {
                    'season': item.get('season'), 
                    'voiceover': item.get('voiceover_tag'),
                    'episode': item.get('episode_start') if not item.get('episode_end') else None,
                    'start': item.get('episode_start') if item.get('episode_end') else None,
                    'end': item.get('episode_end')
                }
                # Передаем его напрямую в форматер
                expected_filename = formatter.format_filename(series, metadata)
                expected_path = os.path.join(series['save_path'], expected_filename)
                
                if os.path.exists(expected_path):
                    self.db.register_downloaded_media_item(item['unique_id'], expected_path)
                    self.logger.info("monitoring_agent", f"Усыновлен существующий файл для series_id {series_id}: {expected_filename}")
                    changed = True

            # --- Блок 2: Проверка пропавших файлов ---
            completed_items = self.db.get_media_items_by_status(series_id, 'completed')
            for item in completed_items:
                file_path = item.get('final_filename')
                if file_path and not os.path.exists(file_path):
                    self.db.reset_media_item_download_state(item['unique_id'])
                    self.logger.warning("monitoring_agent", f"Файл для series_id {series_id} пропал: {file_path}. Статус сброшен.")
                    changed = True
            
            # --- Блок 3: Обновление статуса, если были изменения ---
            if changed:
                self.status_manager.sync_vk_statuses(series_id)

    def _periodic_filesystem_sync(self):
        """Периодическая задача, которая запускает синхронизацию для всех VK-сериалов."""
        with self.app.app_context():
            all_series = self.db.get_all_series()
            for series in all_series:
                if series['source_type'] == 'vk_video':
                    # Проверка скачанных файлов (компиляций)
                    self.sync_single_series_filesystem(series['id'])
                    # ---> ДОБАВЬТЕ ЭТУ СТРОКУ <---
                    # Проверка нарезанных файлов (эпизодов)
                    self.verify_sliced_files_for_series(series['id'])

    def _trigger_slicing_recovery(self, unique_id: str):
        self.db.delete_sliced_files_for_source(unique_id)
        self.db.update_media_item_slicing_status(unique_id, 'none')
        self.db.set_media_item_ignored_status_by_uid(unique_id, False)

    def _update_active_statuses(self):
        # --- НОВЫЙ БЛОК: Периодическая синхронизация статусов для VK-сериалов ---
        all_vk_series = [s for s in self.db.get_all_series() if s['source_type'] == 'vk_video']
        for series in all_vk_series:
            self.status_manager.sync_vk_statuses(series['id'])
        # --- КОНЕЦ НОВОГО БЛОКА ---

        # --- Существующая логика для торрентов остаётся без изменений ---
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
            # ... (ваш код инициализации qb_client и recovery)
            auth_manager = AuthManager(self.db, self.logger)
            self.qb_client = QBittorrentClient(auth_manager, self.db, self.logger)
            self.logger.info("monitoring_agent", "Выполнение первоначальной проверки статусов файлов...")
            self._periodic_filesystem_sync()
            self.logger.info("monitoring_agent", "Первоначальная проверка завершена.")
            self.handle_startup_scan()

        while not self.shutdown_flag.is_set():
            # 3. Заменяем shutdown_flag.wait() на select()
            readable, _, _ = select.select([self._shutdown_pipe_r], [], [], self.CHECK_INTERVAL)
            if readable:
                # Нас разбудили через pipe, выходим из цикла
                break

            # Если select завершился по таймауту, выполняем обычную работу
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
        
        # 4. Очищаем ресурсы pipe после выхода из цикла
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
                # --- ИЗМЕНЕНИЕ: Логика определения "занятости" теперь находится в StatusManager ---
                # Вместо чтения state, мы будем использовать более простой механизм
                
                # Пропускаем, если задача уже в обработке StatefulAgent
                if self.db.get_all_agent_tasks_for_series(series_id):
                    if app.debug_manager.is_debug_enabled('monitoring_agent'):
                        self.logger.debug("monitoring_agent", f"Пропуск сканирования для '{series['name']}' (ID: {series_id}): активна задача агента.")
                    continue

                if app.debug_manager.is_debug_enabled('monitoring_agent'):
                    self.logger.debug("monitoring_agent", f"Запуск сканирования для '{series['name']}' (ID: {series['id']}).")
                try:
                    # Передаем status_manager в функцию сканирования
                    perform_series_scan(series['id'], self.status_manager, debug_force_replace)
                except Exception as e:
                    self.logger.error("monitoring_agent", f"Ошибка при сканировании сериала {series['id']}: {e}", exc_info=True)
                    # Используем StatusManager для установки ошибки
                    self.status_manager.set_status(series['id'], 'error', True)
                    continue
            
            self.logger.info("monitoring_agent", "Полный цикл сканирования завершен. Переход в режим ожидания задач.")
            
            self.scan_in_progress_flag.clear()
            self.awaiting_tasks_flag.set()
            if app.debug_manager.is_debug_enabled('monitoring_agent'):
                self.logger.debug("monitoring_agent", "Снят флаг 'сканирование в процессе', установлен флаг 'ожидание задач'.")
            self._broadcast_scanner_status()

    def _check_stale_viewing_statuses(self):
        """Проверяет и сбрасывает зависшие статусы 'Просмотр'."""
        stale_series_ids = self.db.get_stale_viewing_series_ids(timeout_seconds=90)
        for series_id in stale_series_ids:
            self.logger.info("monitoring_agent", f"Обнаружен зависший статус 'Просмотр' для series_id {series_id}. Сброс.")
            # Напрямую вызываем метод БД для установки NULL
            self.db.set_viewing_status(series_id, False)
            # И просим StatusManager просто обновить UI
            self.status_manager._update_and_broadcast(series_id)

    def shutdown(self):
        self.logger.info(f"{self.name}: получен сигнал на остановку.")
        self.shutdown_flag.set()
        try:
            # 5. Пишем в pipe, чтобы мгновенно разбудить поток из select()
            os.write(self._shutdown_pipe_w, b'x')
        except OSError:
            pass # Канал может быть уже закрыт
