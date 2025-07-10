import threading
import time
import json
from flask import Flask, current_app as app
from db import Database
from logger import Logger
from qbittorrent import QBittorrentClient
from renamer import Renamer
from auth import AuthManager
from sse import ServerSentEvent
from scanner import perform_series_scan

class Agent(threading.Thread):
    def __init__(self, app: Flask, logger: Logger, db: Database, broadcaster: ServerSentEvent):
        super().__init__(daemon=True)
        self.name = "StatefulAgent"
        self.app = app
        self.logger = logger
        self.db = db
        self.broadcaster = broadcaster
        self.processing_torrents = {}
        self.lock = threading.RLock()
        self.shutdown_flag = threading.Event()
        self.RECONNECT_DELAY = 10 

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
        with self.lock:
            if torrent_hash in self.processing_torrents:
                self.logger.warning("agent", f"Задача для хеша {torrent_hash} уже обрабатывается.")
                return

            if link_type == 'file':
                initial_stage = 'awaiting_pause_before_rename'
            else: 
                initial_stage = 'awaiting_metadata'

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
            self._broadcast_queue_update()
            with self.app.app_context():
                self._update_series_state(series_id)

    def get_queue_info(self):
        with self.lock:
            return self._get_queue_info_unsafe()
            
    def _get_queue_info_unsafe(self):
        return [{'hash': h, **d} for h, d in self.processing_torrents.items()]

    def clear_queue(self):
        with self.lock:
            self.processing_torrents.clear()
            all_tasks = self.db.get_all_agent_tasks()
            for task in all_tasks:
                self.db.remove_agent_task(task['torrent_hash'])
            self.logger.info("agent", "Очередь обработки агента и таблица в БД были очищены.")
            self._broadcast_queue_update()

    def _update_series_state(self, series_id):
        active_tasks = {}
        with self.lock:
            for h, t in self.processing_torrents.items():
                if t['series_id'] == series_id:
                    active_tasks[h] = t['stage']

        with self.app.app_context():
            if active_tasks:
                def map_stage_for_ui(stage):
                    if stage in ['awaiting_metadata', 'polling_for_size', 'awaiting_pause_before_rename']:
                        return 'metadata'
                    if stage == 'rechecking':
                        return 'checking'
                    return stage
                final_states = {h: map_stage_for_ui(s) for h, s in active_tasks.items()}
                self.db.set_series_state(series_id, final_states)
            else:
                series_data = self.db.get_series(series_id)
                if not series_data: return
                current_series_state_raw = series_data['state']
                try:
                    if isinstance(json.loads(current_series_state_raw), dict):
                        self.db.set_series_state(series_id, 'waiting')
                except (json.JSONDecodeError, TypeError): pass
            
            updated_series_data = self.db.get_series(series_id)
            if updated_series_data:
                if updated_series_data.get('last_scan_time'):
                    updated_series_data['last_scan_time'] = updated_series_data['last_scan_time'].isoformat()
                self.broadcaster.broadcast('series_updated', updated_series_data)

    def _process_task_update(self, torrent_hash, qb_client, renamer):
        with self.lock:
            task = self.processing_torrents.get(torrent_hash)
            if not task: return
            
            current_info = task['last_info']
            stage = task['stage']
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
                qb_client.resume_torrents([torrent_hash])
                next_stage = 'polling_for_size'
            
            elif stage == 'polling_for_size':
                if current_info.get('total_size', 0) > 0:
                    self.logger.info("agent", f"[{torrent_hash[:8]}] Метаданные получены. Постановка на паузу.")
                    qb_client.pause_torrents([torrent_hash])
                    next_stage = 'awaiting_pause_before_rename'

            elif stage == 'awaiting_pause_before_rename':
                current_state = current_info.get('state')
                if current_state in self.STABLE_PAUSED_STATES:
                    if app.debug_manager.is_debug_enabled('agent'):
                        self.logger.debug("agent", f"[{torrent_hash[:8]}] Торрент в стабильном состоянии паузы. Переход к переименованию.")
                    next_stage = 'renaming'
                elif current_state:
                    self.logger.warning("agent", f"[{torrent_hash[:8]}] Торрент в неожиданном состоянии '{current_state}' вместо паузы. Принудительная остановка.")
                    qb_client.pause_torrents([torrent_hash])

            elif stage == 'renaming':
                self.logger.info("agent", f"[{torrent_hash[:8]}] Запуск переименования.")
                series = self.db.get_series(task['series_id'])
                if not series:
                    raise Exception(f"Сериал с ID {task['series_id']} не найден для задачи переименования.")
                files = qb_client.get_torrent_files_by_hash(torrent_hash)
                if files:
                    preview = renamer.get_rename_preview(files, series)
                    for item in preview:
                        if item.get('renamed') and "Ошибка" not in item.get('renamed') and item.get('original') != item.get('renamed'):
                            qb_client.rename_file(torrent_hash, item['original'], item['renamed'])
                
                time.sleep(1)
                next_stage = 'rechecking'

            elif stage == 'rechecking':
                current_state = current_info.get('state')
                recheck_initiated = task.get('recheck_initiated', False)

                if not recheck_initiated:
                    self.logger.info("agent", f"[{torrent_hash[:8]}] Инициация recheck.")
                    qb_client.recheck_torrents([torrent_hash])
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
                    qb_client.resume_torrents([torrent_hash])
                    task_completed = True

            with self.lock:
                current_task_in_memory = self.processing_torrents.get(torrent_hash)
                if current_task_in_memory:
                    if next_stage:
                        current_task_in_memory['stage'] = next_stage
                        db_task_data = {
                            'torrent_hash': torrent_hash,
                            'series_id': current_task_in_memory['series_id'],
                            'torrent_id': current_task_in_memory['torrent_id'],
                            'old_torrent_id': current_task_in_memory['old_torrent_id'],
                            'stage': current_task_in_memory['stage']
                        }
                        self.db.add_or_update_agent_task(db_task_data)
                        self._broadcast_queue_update()
                    if task_completed:
                        del self.processing_torrents[torrent_hash]
                        self.db.remove_agent_task(torrent_hash)
                        self._broadcast_queue_update()

            if next_stage or task_completed:
                self._update_series_state(task['series_id'])
            
            if task_completed:
                torrent_entry = self.db.get_torrent_by_hash(torrent_hash)
                if torrent_entry: self.db.update_torrent_by_id(torrent_entry['id'], {'is_active': True})

        except Exception as e:
            self.logger.error("agent", f"Ошибка при обработке задачи {torrent_hash}: {e}", exc_info=True)
            self.db.set_series_state(task['series_id'], 'error')
            with self.lock:
                if torrent_hash in self.processing_torrents:
                    del self.processing_torrents[torrent_hash]
                    self.db.remove_agent_task(torrent_hash)
                    self._broadcast_queue_update()
            self._update_series_state(task['series_id'])

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

        for task_data in restored_tasks:
            h = task_data['torrent_hash']
            if h not in info_map:
                self.logger.warning("agent", f"Задача агента для хеша {h} найдена в БД, но торрент отсутствует в qBittorrent. Удаление устаревшей задачи.")
                with self.lock:
                    if h in self.processing_torrents: del self.processing_torrents[h]
                    self.db.remove_agent_task(h)
                continue
            
            with self.lock:
                if self.processing_torrents.get(h): self.processing_torrents[h]['last_info'] = info_map[h]
        
        self.logger.info("agent", "Восстановление задач агента завершено.")
        self._broadcast_queue_update()

    def _recover_scan_tasks_from_db(self):
        """Восстанавливает прерванные задачи сканирования."""
        self.logger.info("agent", "Запуск восстановления незавершенных ЗАДАЧ СКАНИРОВАНИЯ из БД.")
        incomplete_scans = self.db.get_incomplete_scan_tasks()
        if not incomplete_scans:
            self.logger.info("agent", "Незавершенных задач сканирования не найдено.")
            return
        
        self.logger.warning("agent", f"Найдено {len(incomplete_scans)} незавершенных задач сканирования. Запуск восстановления...")
        for task in incomplete_scans:
            try:
                self.logger.info("agent", f"Восстановление ScanTask ID: {task['id']} для Series ID: {task['series_id']}")
                perform_series_scan(
                    series_id=task['series_id'],
                    recovery_mode=True,
                    existing_task=task
                )
            except Exception as e:
                self.logger.error("agent", f"Критическая ошибка при восстановлении ScanTask ID {task['id']}: {e}", exc_info=True)

    def _recover_tasks(self, qb_client):
        """Запускает все процедуры восстановления при старте."""
        self.logger.info("agent", "--- НАЧАЛО ПРОЦЕДУРЫ ВОССТАНОВЛЕНИЯ ---")
        self._recover_scan_tasks_from_db()
        self._recover_agent_tasks_from_db(qb_client)
        self.logger.info("agent", "--- ЗАВЕРШЕНИЕ ПРОЦЕДУРЫ ВОССТАНОВЛЕНИЯ ---")


    def run(self):
        self.logger.info("agent", "Агент запущен.")
        rid = 0
        
        with self.app.app_context():
            auth_manager = AuthManager(self.db, self.logger)
            qb_client = QBittorrentClient(auth_manager, self.db, self.logger)
            renamer = Renamer(self.logger, self.db)
            self._recover_tasks(qb_client)

        self.logger.info("agent", "Переход в штатный режим Long-Polling.")
        while not self.shutdown_flag.is_set():
            # --- ИЗМЕНЕНИЕ: Оборачиваем логику цикла в app_context ---
            with self.app.app_context():
                if not self.processing_torrents:
                    # Выходим из контекста и ждем, если нет работы
                    pass
                else:
                    updates = qb_client.sync_main_data(rid)

                    if self.shutdown_flag.is_set(): break
                    
                    if updates is None:
                        self.logger.warning("agent", "Ошибка или таймаут long-polling, повторная попытка.")
                        time.sleep(self.RECONNECT_DELAY)
                        rid = 0
                        continue

                    rid = updates.get('server_state', {}).get('rid', rid)
                    updated_torrents = updates.get('torrents', {})
                    
                    if updates.get('full_update', False):
                        with self.lock: hashes_to_check = list(self.processing_torrents.keys())
                        for h in hashes_to_check:
                             if h in updated_torrents:
                                with self.lock:
                                    if self.processing_torrents.get(h): self.processing_torrents[h]['last_info'].update(updated_torrents[h])
                                self._process_task_update(h, qb_client, renamer)
                    else:
                        with self.lock: hashes_to_check = [h for h in updated_torrents.keys() if h in self.processing_torrents]
                        for h in hashes_to_check:
                            with self.lock:
                                if self.processing_torrents.get(h): self.processing_torrents[h]['last_info'].update(updated_torrents[h])
                            self._process_task_update(h, qb_client, renamer)
            
            # Ожидание вне контекста
            self.shutdown_flag.wait(1)

        self.logger.info("agent", f"{self.name} был остановлен.")

    def shutdown(self):
        self.logger.info("agent", "Получен сигнал на остановку агента.")
        self.shutdown_flag.set()