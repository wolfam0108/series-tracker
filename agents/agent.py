import threading
import time
import json
import os
from flask import Flask, current_app as app
from db import Database
from logger import Logger
from qbittorrent import QBittorrentClient
from auth import AuthManager
from sse import ServerSentEvent
from scanner import perform_series_scan
from datetime import datetime, timezone
from status_manager import StatusManager
from rule_engine import RuleEngine
from filename_formatter import FilenameFormatter
from logic.renaming_processor import process_and_rename_torrent_files

class Agent(threading.Thread):
    def __init__(self, app: Flask, logger: Logger, db: Database, broadcaster: ServerSentEvent, status_manager: StatusManager):
        super().__init__(daemon=True)
        self.name = "StatefulAgent"
        self.app = app
        self.logger = logger
        self.db = db
        self.broadcaster = broadcaster
        self.status_manager = status_manager
        self.processing_torrents = {}
        self.lock = threading.RLock()
        self.shutdown_flag = threading.Event()
        self.RECONNECT_DELAY = 10 
        self.qb_client = None

        self.POST_RECHECK_TARGET_STATES = {
            'queuedUP', 'queuedDL', 'stalledUP', 'stalledDL', 
            'uploading', 'downloading', 'pausedDL', 'pausedUP'
        }
        self.ACTIVATING_RUNNING_STATES = {
            'uploading', 'stalledUP', 'forcedUP', 'downloading', 
            'stalledDL', 'forcedDL', 'queuedUP', 'queuedDL'
        }
        self.ACTIVATING_PAUSED_STATES = {'pausedUP', 'pausedDL'}
        self.STABLE_PAUSED_STATES = {'pausedUP', 'pausedDL'}
        self.CHECKING_STATES = {'checkingUP', 'checkingDL', 'checkingResumeData'}


    def _broadcast_queue_update(self):
        with self.lock:
            queue_info = self._get_queue_info_unsafe()
            self.broadcaster.broadcast('agent_queue_update', queue_info)
            if app.debug_manager.is_debug_enabled('agent'):
                self.logger.debug("agent", f"Трансляция обновления очереди: {len(queue_info)} задач.")

    def add_task(self, torrent_hash: str, series_id: int, torrent_id: str, old_torrent_id: str, link_type: str):
        with self.lock, self.app.app_context():
            if torrent_hash in self.processing_torrents:
                self.logger.warning("agent", f"Задача для хеша {torrent_hash} уже обрабатывается.")
                return

            initial_stage = 'awaiting_pause_before_rename' if link_type == 'file' else 'awaiting_metadata'

            db_task_data = {
                'torrent_hash': torrent_hash,
                'series_id': series_id,
                'torrent_id': torrent_id,
                'old_torrent_id': old_torrent_id,
                'stage': initial_stage,
            }

            self.processing_torrents[torrent_hash] = {
                **db_task_data,
                'last_info': {},
                'last_logged_str': '',
                'recheck_initiated': False
            }
            self.db.add_or_update_agent_task(db_task_data)
            self.logger.info("agent", f"Новая задача добавлена для хеша {torrent_hash[:8]} на стадии '{initial_stage}'.")
            
            self.status_manager.sync_agent_statuses(series_id)
            self._broadcast_queue_update()

    def get_queue_info(self):
        with self.lock:
            return self._get_queue_info_unsafe()
            
    def _get_queue_info_unsafe(self):
        return [{'hash': h, **d} for h, d in self.processing_torrents.items()]

    def clear_queue(self):
        with self.lock, self.app.app_context():
            self.processing_torrents.clear()
            all_tasks = self.db.get_all_agent_tasks()
            series_ids_to_update = {t['series_id'] for t in all_tasks}

            for task in all_tasks:
                self.db.remove_agent_task(task['torrent_hash'])
            
            for series_id in series_ids_to_update:
                self.status_manager.sync_agent_statuses(series_id)

            self.logger.info("agent", "Очередь обработки агента и таблица в БД были очищены.")
            self._broadcast_queue_update()
    
    def _process_task_update(self, torrent_hash):
        with self.lock:
            task = self.processing_torrents.get(torrent_hash)
            if not task: return
            
            current_info = task.get('last_info', {})
            stage = task.get('stage')
            last_logged_str = task.get('last_logged_str', '')

        current_log_str = f"[{torrent_hash[:8]}] Стадия: {stage}, Статус qBit: {current_info.get('state')}"
        if app.debug_manager.is_debug_enabled('agent') and current_log_str != last_logged_str:
            self.logger.debug("agent", current_log_str)
            with self.lock:
                if self.processing_torrents.get(torrent_hash):
                    self.processing_torrents[torrent_hash]['last_logged_str'] = current_log_str
        
        try:
            next_stage = None
            task_completed = False

            if stage == 'awaiting_metadata':
                self.logger.info("agent", f"[{torrent_hash[:8]}] Снятие с паузы для получения метаданных.")
                self.qb_client.resume_torrents([torrent_hash])
                next_stage = 'polling_for_size'
            
            elif stage == 'polling_for_size':
                if current_info.get('total_size', 0) > 0:
                    self.logger.info("agent", f"[{torrent_hash[:8]}] Метаданные получены. Постановка на паузу.")
                    self.qb_client.pause_torrents([torrent_hash])
                    next_stage = 'awaiting_pause_before_rename'

            elif stage == 'awaiting_pause_before_rename':
                current_state = current_info.get('state')
                if current_state in self.STABLE_PAUSED_STATES:
                    if app.debug_manager.is_debug_enabled('agent'):
                        self.logger.debug("agent", f"[{torrent_hash[:8]}] Торрент в стабильном состоянии паузы. Переход к переименованию.")
                    next_stage = 'renaming'
                elif current_state:
                    self.logger.warning("agent", f"[{torrent_hash[:8]}] Торрент в неожиданном состоянии '{current_state}' вместо паузы. Принудительная остановка.")
                    self.qb_client.pause_torrents([torrent_hash])

            elif stage == 'renaming':
                self.logger.info("agent", f"[{torrent_hash[:8]}] Запуск централизованной функции переименования.")

                # Вызываем нашу новую единую функцию
                process_and_rename_torrent_files(self.app, task['series_id'], torrent_hash)

                self.logger.info("agent", f"[{torrent_hash[:8]}] Переименование завершено. Переход к 'rechecking'.")
                next_stage = 'rechecking'

            elif stage == 'rechecking':
                current_state = current_info.get('state')
                recheck_initiated = task.get('recheck_initiated', False)

                if not recheck_initiated:
                    self.logger.info("agent", f"[{torrent_hash[:8]}] Инициация recheck.")
                    self.qb_client.recheck_torrents([torrent_hash])
                    with self.lock:
                        if self.processing_torrents.get(torrent_hash):
                            self.processing_torrents[torrent_hash]['recheck_initiated'] = True
                    time.sleep(1) 
                
                else:
                    if current_state in self.POST_RECHECK_TARGET_STATES and current_state not in self.CHECKING_STATES:
                        self.logger.info("agent", f"[{torrent_hash[:8]}] Recheck завершен. Переход на 'activating'.")
                        next_stage = 'activating'
                
            elif stage == 'activating':
                state = current_info.get('state')
                if state in self.ACTIVATING_RUNNING_STATES:
                    self.logger.info("agent", f"[{torrent_hash[:8]}] Торрент активен. Задача выполнена.")
                    task_completed = True
                elif state in self.ACTIVATING_PAUSED_STATES:
                    self.logger.info("agent", f"[{torrent_hash[:8]}] Торрент на паузе. Запуск и завершение.")
                    self.qb_client.resume_torrents([torrent_hash])
                    task_completed = True

            with self.lock, self.app.app_context():
                current_task_in_memory = self.processing_torrents.get(torrent_hash)
                if not current_task_in_memory: return

                if next_stage:
                    current_task_in_memory['stage'] = next_stage
                    db_task_data = {k: v for k, v in current_task_in_memory.items() if k in ['torrent_hash', 'series_id', 'torrent_id', 'old_torrent_id', 'stage']}
                    
                    self.db.add_or_update_agent_task(db_task_data)
                    self.status_manager.sync_agent_statuses(task['series_id'])
                    self._broadcast_queue_update()

                if task_completed:
                    del self.processing_torrents[torrent_hash]
                    self.db.remove_agent_task(torrent_hash)
                    
                    self.status_manager.sync_agent_statuses(task['series_id'])
                    self._broadcast_queue_update()
                    
                    self.db.update_series(task['series_id'], {'last_scan_time': datetime.now(timezone.utc)})
                    torrent_entry = self.db.get_torrent_by_hash(torrent_hash)
                    if torrent_entry: self.db.update_torrent_by_id(torrent_entry['id'], {'is_active': True})

        except Exception as e:
            self.logger.error("agent", f"Ошибка при обработке задачи {torrent_hash}: {e}", exc_info=True)
            with self.lock, self.app.app_context():
                if torrent_hash in self.processing_torrents:
                    del self.processing_torrents[torrent_hash]
                    self.db.remove_agent_task(torrent_hash)
                
                self.status_manager.set_status(task['series_id'], 'error', True)
                self.status_manager.sync_agent_statuses(task['series_id'])
                self._broadcast_queue_update()

    def _recover_agent_tasks_from_db(self, qb_client: QBittorrentClient):
        self.logger.info("agent", "Запуск восстановления незавершенных ЗАДАЧ АГЕНТА из БД.")
        restored_tasks = self.db.get_all_agent_tasks()
        
        if not restored_tasks:
            self.logger.info("agent", "Незавершенных задач агента не найдено.")
            return

        self.logger.info("agent", f"Найдено {len(restored_tasks)} незавершенных задач агента. Восстановление...")
        
        with self.lock:
            for task_data in restored_tasks:
                self.processing_torrents[task_data['torrent_hash']] = {
                    **task_data,
                    'last_info': {},
                    'last_logged_str': '',
                    'recheck_initiated': False
                }
        
        hashes_to_check = [task['torrent_hash'] for task in restored_tasks]
        current_infos = qb_client.get_torrents_info(hashes_to_check)
        info_map = {info['hash']: info for info in current_infos} if current_infos else {}

        series_ids_to_sync = set()
        for task_data in restored_tasks:
            h = task_data['torrent_hash']
            series_ids_to_sync.add(task_data['series_id'])
            if h not in info_map:
                self.logger.warning("agent", f"Задача агента для хеша {h} найдена в БД, но торрент отсутствует в qBittorrent. Удаление устаревшей задачи.")
                with self.lock:
                    if h in self.processing_torrents: del self.processing_torrents[h]
                    self.db.remove_agent_task(h)
                continue
            
            with self.lock:
                if self.processing_torrents.get(h): self.processing_torrents[h]['last_info'] = info_map[h]
        
        self.logger.info("agent", "Восстановление задач агента завершено. Синхронизация статусов...")
        with self.app.app_context():
            for series_id in series_ids_to_sync:
                self.status_manager.sync_agent_statuses(series_id)

        self._broadcast_queue_update()

    def _recover_scan_tasks_from_db(self):
        self.logger.info("agent", "Запуск проверки незавершенных ЗАДАЧ СКАНИРОВАНИЯ из БД.")
        incomplete_scans = self.db.get_incomplete_scan_tasks()

        if not incomplete_scans:
            self.logger.info("agent", "Незавершенных задач сканирования не найдено.")
            return

        # --- НОВАЯ ЛОГИКА ---
        # Вместо восстановления, мы просто удаляем устаревшие задачи,
        # чтобы избежать бесконечных циклов при ошибках.
        self.logger.warning("agent", f"Найдено {len(incomplete_scans)} незавершенных (устаревших) задач сканирования. Очистка...")
        for task in incomplete_scans:
            try:
                self.db.delete_scan_task(task['id'])
                self.logger.info("agent", f"Удалена устаревшая задача сканирования ID: {task['id']} для Series ID: {task['series_id']}")
            except Exception as e:
                self.logger.error("agent", f"Не удалось удалить задачу сканирования ID {task['id']}: {e}", exc_info=True)

    def _recover_tasks(self, qb_client):
        self.logger.info("agent", "--- НАЧАЛО ПРОЦЕДУРЫ ВОССТАНОВЛЕНИЯ ---")
        self._recover_scan_tasks_from_db()
        self._recover_agent_tasks_from_db(qb_client)
        self.logger.info("agent", "--- ЗАВЕРШЕНИЕ ПРОЦЕДУРЫ ВОССТАНОВЛЕНИЯ ---")


    def run(self):
        self.logger.info("agent", "Агент запущен.")
        rid = 0
        
        with self.app.app_context():
            auth_manager = AuthManager(self.db, self.logger)
            self.qb_client = QBittorrentClient(auth_manager, self.db, self.logger)
            self._recover_tasks(self.qb_client)

        self.logger.info("agent", "Переход в штатный режим Long-Polling.")
        while not self.shutdown_flag.is_set():
            with self.app.app_context():
                if self.processing_torrents:
                    updates = self.qb_client.sync_main_data(rid)

                    if self.shutdown_flag.is_set(): 
                        break
                    
                    if updates is None:
                        self.logger.warning("agent", "Ошибка или таймаут long-polling, повторная попытка.")
                        time.sleep(self.RECONNECT_DELAY) 
                        rid = 0
                        continue

                    rid = updates.get('server_state', {}).get('rid', rid)
                    
                    # --- НАЧАЛО ИЗМЕНЕНИЯ ---
                    # 1. Сначала обновляем информацию о торрентах, по которым пришли изменения
                    updated_torrents = updates.get('torrents', {})
                    with self.lock:
                        for h, torrent_data in updated_torrents.items():
                            if h in self.processing_torrents:
                                self.processing_torrents[h]['last_info'].update(torrent_data)

                    # 2. Затем проходим по ВСЕМ задачам в очереди и обрабатываем каждую
                    # Создаем копию ключей, чтобы избежать проблем при изменении словаря во время итерации
                    current_tasks_hashes = []
                    with self.lock:
                        current_tasks_hashes = list(self.processing_torrents.keys())

                    for torrent_hash in current_tasks_hashes:
                        self._process_task_update(torrent_hash)
                    # --- КОНЕЦ ИЗМЕНЕНИЯ ---
            
            self.shutdown_flag.wait(1)

        self.logger.info(f"{self.name} был остановлен.")
    
    def add_recheck_task(self, torrent_hash: str, series_id: int, torrent_id: str):
        """
        Добавляет задачу на перепроверку (recheck) для существующего торрента.
        Задача сразу начинается со стадии 'rechecking'.
        """
        with self.lock, self.app.app_context():
            if torrent_hash in self.processing_torrents:
                self.logger.warning("agent", f"Задача на recheck для хеша {torrent_hash} не добавлена, т.к. он уже обрабатывается.")
                return

            initial_stage = 'rechecking'

            db_task_data = {
                'torrent_hash': torrent_hash,
                'series_id': series_id,
                'torrent_id': torrent_id,
                'old_torrent_id': 'None',
                'stage': initial_stage,
            }

            self.processing_torrents[torrent_hash] = {
                **db_task_data,
                'last_info': {},
                'last_logged_str': '',
                'recheck_initiated': False
            }
            self.db.add_or_update_agent_task(db_task_data)
            self.logger.info("agent", f"Новая задача на RECHECK добавлена для хеша {torrent_hash[:8]} на стадии '{initial_stage}'.")
            
            # Обновляем статусы файлов с 'missing' на 'rechecking'
            self.db.update_torrent_files_status_by_hashes([torrent_hash], 'missing', 'rechecking')

            self.status_manager.sync_agent_statuses(series_id)
            self._broadcast_queue_update()

    def shutdown(self):
        self.logger.info("agent", "Получен сигнал на остановку агента.")
        self.shutdown_flag.set()