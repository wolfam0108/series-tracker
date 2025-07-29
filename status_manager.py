# ЗАМЕНИТЬ ВЕСЬ ФАЙЛ ЭТИМ КОДОМ
import json
from flask import Flask
from db import Database
from sse import ServerSentEvent
from logger import Logger

class StatusManager:
    """
    Централизованный модуль для управления, агрегации и обновления
    статусов сериалов с использованием таблицы флагов.
    """
    STATUS_HIERARCHY = [
        'error', 'scanning', 'checking', 'slicing', 
        'renaming', 'metadata', 'activating',
        'downloading', 'ready', 'viewing', 'waiting'
    ]
    
    FLAG_TO_NAME_MAP = {
        'is_error': 'error',
        'is_scanning': 'scanning',
        'is_checking': 'checking',
        'is_slicing': 'slicing',
        'is_renaming': 'renaming',
        'is_metadata': 'metadata',
        'is_activating': 'activating',
        'is_downloading': 'downloading',
        'is_ready': 'ready',
        'is_viewing': 'viewing',
        'is_waiting': 'waiting',
    }
    
    AGENT_STAGES_TO_FLAG_MAP = {
        'awaiting_metadata': 'is_metadata',
        'polling_for_size': 'is_metadata',
        'awaiting_pause_before_rename': 'is_metadata',
        'renaming': 'is_renaming',
        'rechecking': 'is_checking',
        'activating': 'is_activating',
    }

    def __init__(self, app: Flask, db: Database, broadcaster: ServerSentEvent, logger: Logger):
        self.app = app
        self.db = db
        self.broadcaster = broadcaster
        self.logger = logger

    def _update_and_broadcast(self, series_id: int):
        """
        Главный метод, который агрегирует статусы из таблицы флагов,
        записывает итоговое состояние в таблицу series и отправляет обновление в UI.
        """
        with self.app.app_context():
            series_data = self.db.get_series(series_id)
            if not series_data: return

            status_flags = self.db.get_series_statuses(series_id)
            if not status_flags: return
            
            active_status_names = []
            for flag_db_name, value in status_flags.items():
                is_active = False
                # Для DateTime проверяем, не NULL ли значение
                if flag_db_name == 'is_viewing':
                    is_active = value is not None
                # Для Boolean просто используем значение
                elif flag_db_name in self.FLAG_TO_NAME_MAP:
                    is_active = value
                
                if is_active and flag_db_name in self.FLAG_TO_NAME_MAP:
                    active_status_names.append(self.FLAG_TO_NAME_MAP[flag_db_name])
            
            # Если после всех проверок нет ни одного активного статуса, принудительно ставим 'Ожидание'
            if not active_status_names:
                self.db.set_series_status_flag(series_id, 'waiting', True)
                # Используем ключ из карты, а не жестко заданную строку
                active_status_names = [self.FLAG_TO_NAME_MAP['is_waiting']]

            # Сортируем статусы по приоритету для консистентного отображения
            active_status_names.sort(key=lambda s: self.STATUS_HIERARCHY.index(s) if s in self.STATUS_HIERARCHY else 99)
            final_status_string = ", ".join(active_status_names)

            # Записываем итоговую строку в основную таблицу series
            self.db.update_series(series_id, {'state': final_status_string})
            
            series_data = self.db.get_series(series_id)
            if series_data:
                if series_data.get('last_scan_time'):
                    series_data['last_scan_time'] = series_data['last_scan_time'].isoformat()
                
                # Фронтенд теперь будет работать с этим простым полем state
                self.broadcaster.broadcast('series_updated', series_data)

    def set_status(self, series_id: int, status_name: str, value: bool):
        """
        Универсальный метод для установки или снятия одного флага статуса.
        Например: set_status(1, 'scanning', True)
        """
        # Сбрасываем флаг 'Ожидание', если устанавливается любой другой активный статус
        if status_name != 'waiting' and value:
            self.db.set_series_status_flag(series_id, 'waiting', False)

        self.db.set_series_status_flag(series_id, status_name, value)
        
        # Проверяем, не нужно ли вернуть флаг 'Ожидание'
        self._sync_waiting_status(series_id)
        
        self._update_and_broadcast(series_id)

    def sync_agent_statuses(self, series_id: int):
        """
        Синхронизирует флаги is_metadata, is_renaming и т.д. с реальным
        состоянием в таблице agent_tasks.
        """
        agent_tasks = self.db.get_all_agent_tasks_for_series(series_id)
        active_stages = {task['stage'] for task in agent_tasks}
        
        active_flags = {self.AGENT_STAGES_TO_FLAG_MAP[stage] for stage in active_stages if stage in self.AGENT_STAGES_TO_FLAG_MAP}

        # Сбрасываем все агентские флаги
        for flag in set(self.AGENT_STAGES_TO_FLAG_MAP.values()):
             self.db.set_series_status_flag(series_id, flag.replace('is_', ''), False)
        
        # Выставляем только те, что активны сейчас
        if active_flags:
            self.db.set_series_status_flag(series_id, 'waiting', False)
            for flag in active_flags:
                self.db.set_series_status_flag(series_id, flag.replace('is_', ''), True)
        
        self._sync_waiting_status(series_id)
        self._update_and_broadcast(series_id)

    def sync_vk_statuses(self, series_id: int):
        """
        Атомарно синхронизирует все флаги статусов для VK-сериала на основе
        состояния его медиа-элементов.
        """
        # <<< НАЧАЛО ИЗМЕНЕНИЯ >>>

        # Шаг 1: Получаем ДВА набора данных для разных проверок
        # Элементы, которые сейчас в плане на загрузку/обработку
        planned_items = self.db.get_media_items_by_plan_statuses(series_id, ['in_plan_single', 'in_plan_compilation'])
        # ВСЕ медиа-элементы для этого сериала, чтобы проверить наличие уже готовых
        all_items = self.db.get_media_items_for_series(series_id)

        # Шаг 2: Вычисляем состояние всех флагов, используя правильные источники данных
        final_flags = {
            # Эти статусы зависят только от элементов в плане
            'downloading': any(item['status'] == 'downloading' for item in planned_items),
            'slicing': any(item['slicing_status'] == 'slicing' for item in planned_items),
            'error': any(item['status'] == 'error' or item['slicing_status'] == 'error' for item in planned_items),
            
            # Статус 'Готов' зависит от ВСЕХ элементов, а не только от тех, что в плане
            'ready': any(item['status'] == 'completed' for item in all_items)
        }
        
        # Шаг 3: Определяем статус 'waiting' на основе других активных состояний
        has_active_tasks = final_flags['downloading'] or final_flags['slicing'] or final_flags['error']
        # Статус 'Ожидание' выставляется, если есть ожидающие файлы И нет других активных задач
        final_flags['waiting'] = any(item['status'] == 'pending' for item in planned_items) and not has_active_tasks

        # Шаг 4: Выполняем одно атомарное обновление в БД
        self.db.update_vk_series_status_flags(series_id, final_flags)

        # Шаг 5: Один раз обновляем UI
        self._update_and_broadcast(series_id)

    def _sync_waiting_status(self, series_id: int):
        """
        Проверяет, остались ли какие-либо активные флаги. Если нет,
        устанавливает флаг 'is_waiting' в TRUE.
        """
        statuses = self.db.get_series_statuses(series_id)
        if not statuses: return

        has_any_active_task = any(
            is_active for flag_name, is_active in statuses.items() 
            if flag_name not in ['is_waiting', 'is_viewing']
        )
        
        if not has_any_active_task and not statuses.get('is_waiting', False):
            self.db.set_series_status_flag(series_id, 'waiting', True)

    def sync_torrent_statuses(self, series_id: int):
        """
        Синхронизирует флаги is_downloading и is_ready с состоянием
        торрент-задач в таблице download_tasks.
        """
        torrent_tasks = self.db.get_all_torrent_tasks_for_series(series_id)
        if not torrent_tasks:
            # Если для сериала больше нет активных торрентов, сбрасываем флаги
            self.set_status(series_id, 'downloading', False)
            self.set_status(series_id, 'ready', False)
            return

        is_any_downloading = any(
            task['progress'] < 100 and task['status'] not in ['pausedUP', 'pausedDL', 'uploading']
            for task in torrent_tasks
        )
        is_any_ready = any(task['progress'] == 100 for task in torrent_tasks)

        self.set_status(series_id, 'downloading', is_any_downloading)
        self.set_status(series_id, 'ready', is_any_ready)