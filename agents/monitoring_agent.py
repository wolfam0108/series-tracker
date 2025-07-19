import threading
import time
import json
import os
from datetime import datetime, timedelta, timezone
from flask import Flask, current_app as app
from db import Database
from logger import Logger
from scanner import perform_series_scan
from sse import ServerSentEvent
from auth import AuthManager
from qbittorrent import QBittorrentClient

def _broadcast_series_update(series_id):
    """Вспомогательная функция для трансляции обновлений сериала через SSE."""
    series_data = app.db.get_series(series_id)
    if series_data:
        if series_data.get('last_scan_time'):
            series_data['last_scan_time'] = series_data['last_scan_time'].isoformat()
        app.sse_broadcaster.broadcast('series_updated', series_data)

class MonitoringAgent(threading.Thread):
    def __init__(self, app: Flask, logger: Logger, db: Database, broadcaster: ServerSentEvent):
        super().__init__(daemon=True)
        self.name = "MonitoringAgent"
        self.app = app
        self.logger = logger
        self.db = db
        self.broadcaster = broadcaster
        self.shutdown_flag = threading.Event()
        self.scan_in_progress_flag = threading.Event()
        self.awaiting_tasks_flag = threading.Event()
        self.CHECK_INTERVAL = 10 
        self.STATUS_UPDATE_INTERVAL = 5
        self.FILE_VERIFY_INTERVAL = 60 # Проверять файлы раз в минуту
        self.last_status_update_time = time.time()
        self.last_file_verify_time = time.time()
        self.qb_client = None

    def _broadcast_scanner_status(self):
        with self.app.app_context():
            status = self.get_status()
            self.broadcaster.broadcast('scanner_status_update', status)

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
        
    def _verify_downloaded_files(self):
        """
        Проверяет наличие файлов на диске и обновляет статусы в БД.
        Также агрегирует статусы для главной карточки сериала.
        """
        all_series = self.db.get_all_series()
        series_to_broadcast = set()

        for series in all_series:
            series_id = series['id']
            if series['source_type'] != 'vk_video':
                continue

            media_items_to_check = self.db.get_media_items_with_filename(series_id)
            changed = False
            for item in media_items_to_check:
                if not os.path.exists(item['final_filename']):
                    self.logger.warning("monitoring_agent", f"Файл {item['final_filename']} для UID {item['unique_id']} не найден на диске. Сброс статуса.")
                    self.db.reset_media_item_download_state(item['unique_id'])
                    changed = True

            # Агрегация статусов для главной карточки
            download_statuses = self.db.get_series_download_statuses(series_id)
            
            new_state = {}
            idx = 0
            if download_statuses.get('downloading', 0) > 0:
                new_state[str(idx)] = 'downloading'
                idx += 1
            
            # Статус "Готов" показываем, если есть завершенные и нет ожидающих/ошибочных/скачивающихся
            if download_statuses.get('completed', 0) > 0 and \
               download_statuses.get('downloading', 0) == 0 and \
               download_statuses.get('pending', 0) == 0 and \
               download_statuses.get('error', 0) == 0:
                new_state[str(idx)] = 'ready'
                idx += 1
            
            # Если ничего не происходит, но есть ожидающие, ставим "Ожидание"
            if not new_state and download_statuses.get('pending', 0) > 0:
                new_state[str(idx)] = 'waiting'
                idx += 1
            
            # Если нет задач, статус по умолчанию - ожидание
            if not new_state and not download_statuses:
                 new_state[str(idx)] = 'waiting'
                 idx += 1

            new_state_str = json.dumps(new_state) if new_state else 'waiting'

            # Обновляем, только если состояние изменилось
            if series['state'] != new_state_str:
                self.db.set_series_state(series_id, new_state_str)
                changed = True

            if changed:
                series_to_broadcast.add(series_id)

        for sid in series_to_broadcast:
            _broadcast_series_update(sid)

    def _update_active_statuses(self):
        if not self.qb_client:
            self.logger.warning("monitoring_agent", "Клиент qBittorrent еще не инициализирован, пропуск обновления статусов.")
            return

        all_series = self.db.get_all_series()
        if not all_series:
            return

        all_hashes = set()
        series_torrents_map = {}

        for series in all_series:
            torrents = self.db.get_torrents(series['id'], is_active=True)
            series_hashes = {t['qb_hash'] for t in torrents if t.get('qb_hash')}
            if series_hashes:
                series_torrents_map[series['id']] = series_hashes
                all_hashes.update(series_hashes)

        if not all_hashes:
            return

        all_torrents_info = self.qb_client.get_torrents_info(list(all_hashes))
        if all_torrents_info is None:
            self.logger.warning("monitoring_agent", "Не удалось получить информацию о торрентах от qBittorrent.")
            return

        info_map = {info['hash']: info for info in all_torrents_info}

        for series in all_series:
            series_id = series['id']
            current_hashes = series_torrents_map.get(series_id, set())
            old_status_obj = json.loads(series.get('active_status', '{}'))
            
            if not current_hashes and old_status_obj:
                self.db.update_series(series_id, {'active_status': '{}'})
                updated_series_data = self.db.get_series(series_id)
                if updated_series_data.get('last_scan_time'):
                    updated_series_data['last_scan_time'] = updated_series_data['last_scan_time'].isoformat()
                self.broadcaster.broadcast('series_updated', updated_series_data)
                continue
            
            if not current_hashes:
                continue

            new_active_status = {}
            for h in current_hashes:
                if h in info_map:
                    info = info_map[h]
                    new_active_status[h] = {
                        'state': info.get('state'),
                        'progress': info.get('progress'),
                        'dlspeed': info.get('dlspeed'),
                        'upspeed': info.get('upspeed'),
                        'eta': info.get('eta'),
                    }
            
            try:
                if old_status_obj != new_active_status:
                    self.db.update_series(series_id, {'active_status': new_active_status})
                    updated_series_data = self.db.get_series(series_id)
                    if updated_series_data.get('last_scan_time'):
                        updated_series_data['last_scan_time'] = updated_series_data['last_scan_time'].isoformat()
                    self.broadcaster.broadcast('series_updated', updated_series_data)
            except Exception as e:
                self.logger.error("monitoring_agent", f"Ошибка обновления active_status для series_id {series_id}: {e}")

    def run(self):
        self.logger.info("monitoring_agent", f"{self.name} запущен.")
        time.sleep(5)

        with self.app.app_context():
            auth_manager = AuthManager(self.db, self.logger)
            self.qb_client = QBittorrentClient(auth_manager, self.db, self.logger)
            
            self.logger.info("monitoring_agent", "Выполнение первоначальной проверки статусов файлов...")
            self._verify_downloaded_files()
            self.logger.info("monitoring_agent", "Первоначальная проверка завершена.")

            self.handle_startup_scan()

        while not self.shutdown_flag.is_set():
            try:
                now = time.time()
                if (now - self.last_status_update_time) >= self.STATUS_UPDATE_INTERVAL:
                    self._update_active_statuses()
                    self.last_status_update_time = now

                if (now - self.last_file_verify_time) >= self.FILE_VERIFY_INTERVAL:
                    with self.app.app_context():
                        self._verify_downloaded_files()
                    self.last_file_verify_time = now

                self._tick()
            except Exception as e:
                self.logger.error("monitoring_agent", f"Критическая ошибка в такте MonitoringAgent: {e}", exc_info=True)
            
            self.shutdown_flag.wait(self.CHECK_INTERVAL)

        self.logger.info("monitoring_agent", f"{self.name} был остановлен.")

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
            try:
                now = time.time()
                if (now - self.last_status_update_time) >= self.STATUS_UPDATE_INTERVAL:
                    self._update_active_statuses()
                    self.last_status_update_time = now
            except Exception as e:
                self.logger.error("monitoring_agent", f"Ошибка при обновлении активных статусов: {e}", exc_info=True)

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
                
                current_series_data = self.db.get_series(series['id'])
                current_state_str = current_series_data.get('state', 'waiting')

                is_busy = False
                try:
                    json.loads(current_state_str)
                    is_busy = True
                except (json.JSONDecodeError, TypeError):
                    if current_state_str.startswith('scanning'):
                        is_busy = True
                
                if is_busy:
                    if app.debug_manager.is_debug_enabled('monitoring_agent'):
                        self.logger.debug("monitoring_agent", f"Пропуск сканирования для '{series['name']}' (ID: {series['id']}) из-за активного статуса: {current_state_str}")
                    continue
                
                if app.debug_manager.is_debug_enabled('monitoring_agent'):
                    self.logger.debug("monitoring_agent", f"Запуск сканирования для '{series['name']}' (ID: {series['id']}).")
                try:
                    perform_series_scan(series['id'], debug_force_replace)
                except Exception as e:
                    self.logger.error("monitoring_agent", f"Ошибка при сканировании сериала {series['id']}: {e}", exc_info=True)
                    self.db.set_series_state(series['id'], 'error')
                    continue
            
            self.logger.info("monitoring_agent", "Полный цикл сканирования завершен. Переход в режим ожидания задач.")
            
            self.scan_in_progress_flag.clear()
            self.awaiting_tasks_flag.set()
            if app.debug_manager.is_debug_enabled('monitoring_agent'):
                self.logger.debug("monitoring_agent", "Снят флаг 'сканирование в процессе', установлен флаг 'ожидание задач'.")
            self._broadcast_scanner_status()

    def shutdown(self):
        self.logger.info("monitoring_agent", "Получен сигнал на остановку.")
        self.shutdown_flag.set()
        self.join()