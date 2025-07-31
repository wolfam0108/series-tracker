import os
import string
import random
import logging
import json
from sqlalchemy import create_engine, func, inspect, text
from sqlalchemy.orm import sessionmaker, joinedload
from sqlalchemy.exc import OperationalError, ProgrammingError, IntegrityError
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Any

from models import (
    Base, Auth, Series, SeriesStatus,
    Torrent, TorrentFile, Setting, Log, AgentTask, ScanTask,
    ParserProfile, ParserRule, ParserRuleCondition, MediaItem, DownloadTask,
    SlicingTask, SlicedFile
)

class Database:
    ENABLE_DEBUG_SCHEMA_CHECK = True

    def __init__(self, db_url: str = "sqlite:///app.db", logger=None):
        self.engine = create_engine(db_url, connect_args={'check_same_thread': False, 'timeout': 15})
        self.logger = logger if logger else logging.getLogger(__name__)
        
        Base.metadata.create_all(self.engine) 
        self.Session = sessionmaker(bind=self.engine)

        if self.ENABLE_DEBUG_SCHEMA_CHECK:
            self._debug_check_and_migrate_tables_individually()

    def _debug_check_and_migrate_tables_individually(self):
        self.logger.info("db", "DEBUG: Начат детальный анализ схемы базы данных (по таблицам).")
        inspector = inspect(self.engine)
        
        with self.Session() as session:
            try:
                if self.engine.dialect.name == 'sqlite':
                    session.execute(text('PRAGMA foreign_keys = OFF;'))
                
                migrated_tables = set()

                # --- Специальная, неразрушающая миграция для series_statuses ---
                table_name = 'series_statuses'
                if inspector.has_table(table_name):
                    columns = inspector.get_columns(table_name)
                    is_viewing_col = next((c for c in columns if c['name'] == 'is_viewing'), None)
                    is_boolean_type = is_viewing_col and 'BOOL' in str(is_viewing_col.get('type', '')).upper()

                    if is_boolean_type:
                        self.logger.warning("db", f"Обнаружена устаревшая схема для таблицы '{table_name}'. Запуск неразрушающей миграции...")
                        
                        session.execute(text(f'ALTER TABLE {table_name} RENAME TO _{table_name}_old;'))
                        SeriesStatus.__table__.create(self.engine)
                        
                        old_columns = [c['name'] for c in inspector.get_columns(f'_{table_name}_old') if c['name'] != 'is_viewing']
                        columns_str = ", ".join(old_columns)
                        
                        session.execute(text(
                            f'INSERT INTO {table_name} ({columns_str}) SELECT {columns_str} FROM _{table_name}_old;'
                        ))
                        session.execute(text(f'DROP TABLE _{table_name}_old;'))
                        self.logger.info("db", f"Миграция таблицы '{table_name}' успешно завершена.")
                        migrated_tables.add(table_name)

                # --- Общая проверка и пересоздание остальных таблиц при необходимости ---
                for table_obj in Base.metadata.sorted_tables:
                    table_name = table_obj.name
                    if table_name in migrated_tables:
                        continue

                    if not inspector.has_table(table_name):
                        self.logger.warning("db", f"Таблица '{table_name}' не найдена. Создание...")
                        table_obj.create(self.engine)
                        continue

                    expected_columns = {c.name for c in table_obj.columns}
                    actual_columns = {c['name'] for c in inspector.get_columns(table_name)}
                    
                    if expected_columns != actual_columns:
                        self.logger.warning(
                            "db", 
                            f"Обнаружено несоответствие схемы для таблицы '{table_name}'. Таблица будет пересоздана."
                        )
                        self.logger.debug(f"db", f"Ожидаемые колонки: {expected_columns}")
                        self.logger.debug(f"db", f"Фактические колонки: {actual_columns}")
                        
                        table_obj.drop(self.engine)
                        table_obj.create(self.engine)
                        self.logger.info("db", f"Таблица '{table_name}' успешно пересоздана.")

                session.commit()

            except Exception as e:
                self.logger.error("db", f"Ошибка при миграции схемы: {e}. Может потребоваться ручное вмешательство.", exc_info=True)
                session.rollback()
            finally:
                if self.engine.dialect.name == 'sqlite':
                    session.execute(text('PRAGMA foreign_keys = ON;'))
                self.logger.info("db", "DEBUG: Детальный анализ схемы базы данных завершен.")

    def create_scan_task(self, series_id: int, task_data: List[Dict]) -> int:
        with self.Session() as session:
            new_task = ScanTask(
                series_id=series_id,
                task_data=json.dumps(task_data)
            )
            session.add(new_task)
            session.commit()
            return new_task.id

    def get_incomplete_scan_tasks(self) -> List[Dict]:
        with self.Session() as session:
            tasks = session.query(ScanTask).all()
            result = []
            for task in tasks:
                task_dict = {c.name: getattr(task, c.name) for c in task.__table__.columns}
                try:
                    task_dict['task_data'] = json.loads(task_dict.get('task_data')) if task_dict.get('task_data') else []
                    task_dict['results_data'] = json.loads(task_dict.get('results_data')) if task_dict.get('results_data') else {}
                except (json.JSONDecodeError, TypeError):
                    self.logger.error("db", f"Ошибка декодирования JSON для ScanTask ID {task.id}")
                    continue
                result.append(task_dict)
            return result

    def update_scan_task_results(self, task_id: int, results_data: Dict):
        with self.Session() as session:
            task = session.query(ScanTask).filter_by(id=task_id).first()
            if task:
                task.results_data = json.dumps(results_data)
                session.commit()

    def delete_scan_task(self, task_id: int):
        with self.Session() as session:
            task = session.query(ScanTask).filter_by(id=task_id).first()
            if task:
                session.delete(task)
                session.commit()

    def get_table_names(self) -> List[str]:
        return list(Base.metadata.tables.keys())

    def clear_table(self, table_name: str) -> bool:
        if table_name in Base.metadata.tables:
            if table_name == 'auth':
                self.logger.warning("db", "Попытка очистить защищенную таблицу 'auth' была заблокирована.")
                return False
            
            table = Base.metadata.tables[table_name]
            with self.Session() as session:
                try:
                    session.execute(table.delete())
                    session.commit()
                    self.logger.info("db", f"Таблица '{table_name}' была успешно очищена.")
                    return True
                except Exception as e:
                    self.logger.error("db", f"Ошибка при очистке таблицы '{table_name}': {e}", exc_info=True)
                    session.rollback()
                    return False
        else:
            self.logger.error("db", f"Попытка очистить несуществующую таблицу: '{table_name}'.")
            return False

    def add_auth(self, auth_type: str, username: str, password: str, url: Optional[str] = None):
        with self.Session() as session:
            session.merge(Auth(auth_type=auth_type, username=username, password=password, url=url))
            session.commit()

    def get_auth(self, auth_type: str) -> Optional[Dict[str, str]]:
        with self.Session() as session:
            auth = session.query(Auth).filter_by(auth_type=auth_type).first()
            return {"username": auth.username, "password": auth.password, "url": auth.url} if auth else None

    def add_series(self, data: Dict[str, Any]) -> int:
        with self.Session() as session:
            allowed_keys = {c.name for c in Series.__table__.columns if c.name not in ['id', 'active_status']}
            series_data = {key: data[key] for key in allowed_keys if key in data}
        
            if 'source_type' not in series_data:
                series_data['source_type'] = 'torrent'
        
            series = Series(**series_data)
            session.add(series)
            session.flush() # Получаем series.id до коммита
        
            # Создаем запись в таблице статусов
            new_status = SeriesStatus(series_id=series.id)
            session.add(new_status)
        
            session.commit()
            return series.id

    def get_series(self, series_id: int) -> Optional[Dict[str, Any]]:
        with self.Session() as session:
            series = session.query(Series).filter_by(id=series_id).first()
            if not series: return None
            return {c.name: getattr(series, c.name) for c in series.__table__.columns}

    def get_all_series(self) -> List[Dict[str, Any]]:
        with self.Session() as session:
            return [{c.name: getattr(s, c.name) for c in s.__table__.columns} for s in session.query(Series).all()]

    def get_all_series_for_auto_scan(self) -> List[Dict[str, Any]]:
        with self.Session() as session:
            series_list = session.query(Series).filter_by(auto_scan_enabled=True).all()
            return [{c.name: getattr(s, c.name) for c in s.__table__.columns} for s in series_list]

    def update_series(self, series_id: int, data: Dict[str, Any]):
        with self.Session() as session:
            series = session.query(Series).filter_by(id=series_id).first()
            if series:
                for key, value in data.items():
                    if hasattr(series, key) and key != 'id':
                        setattr(series, key, value)
                session.commit()

    # ДОБАВИТЬ ЭТИ МЕТОДЫ В КЛАСС Database
    def set_series_status_flag(self, series_id: int, status_name: str, value: bool):
        """Устанавливает конкретный флаг статуса для сериала."""
        with self.Session() as session:
            status_column = f"is_{status_name}"
            if hasattr(SeriesStatus, status_column):
                session.query(SeriesStatus).filter_by(series_id=series_id).update({status_column: value})
                session.commit()

    def get_series_statuses(self, series_id: int) -> Optional[Dict[str, Any]]:
        """Возвращает все флаги статусов для одного сериала."""
        with self.Session() as session:
            statuses = session.query(SeriesStatus).filter_by(series_id=series_id).first()
            if not statuses: return None
            return {c.name: getattr(statuses, c.name) for c in statuses.__table__.columns}

    def update_or_create_torrent_task(self, series_id: int, torrent_hash: str, data: Dict[str, Any]):
        """Обновляет или создает задачу мониторинга для торрента."""
        with self.Session() as session:
            task = session.query(DownloadTask).filter_by(task_key=torrent_hash, task_type='torrent').first()
            progress_percent = int(data.get('progress', 0) * 100)
        
            if task:
                task.status = data.get('state')
                task.progress = progress_percent
                task.dlspeed = data.get('dlspeed', 0)
                task.eta = data.get('eta', 0)
                task.updated_at = datetime.now(timezone.utc)
            else:
                task = DownloadTask(
                    task_key=torrent_hash,
                    series_id=series_id,
                    task_type='torrent',
                    status=data.get('state'),
                    progress=progress_percent,
                    dlspeed=data.get('dlspeed', 0),
                    eta=data.get('eta', 0)
                )
                session.add(task)
            session.commit()

    def remove_stale_torrent_tasks(self, series_id: int, active_hashes: List[str]):
        """Удаляет из БД задачи мониторинга для торрентов, которых больше нет в qBittorrent."""
        with self.Session() as session:
            session.query(DownloadTask).filter(
                DownloadTask.series_id == series_id,
                DownloadTask.task_type == 'torrent',
                ~DownloadTask.task_key.in_(active_hashes)
            ).delete(synchronize_session=False)
            session.commit()

    def delete_series(self, series_id: int):
        with self.Session() as session:
            series = session.query(Series).filter_by(id=series_id).first()
            if series:
                self.logger.info("db", f"Удаление связанных записей для series_id: {series_id}")

                # ---> ДОБАВЬТЕ ЭТОТ БЛОК ПЕРЕД УДАЛЕНИЕМ ТОРРЕНТОВ <---
                # Находим ID всех торрентов, связанных с сериалом
                torrent_ids_to_delete = [t.id for t in session.query(Torrent.id).filter_by(series_id=series_id).all()]
                if torrent_ids_to_delete:
                    # Удаляем все файлы, связанные с этими торрентами
                    session.query(TorrentFile).filter(TorrentFile.torrent_db_id.in_(torrent_ids_to_delete)).delete(synchronize_session=False)
                # ---> КОНЕЦ БЛОКА <---

                session.query(AgentTask).filter_by(series_id=series_id).delete(synchronize_session=False)
                session.query(Torrent).filter_by(series_id=series_id).delete(synchronize_session=False)
                session.query(MediaItem).filter_by(series_id=series_id).delete(synchronize_session=False)
                session.query(SlicedFile).filter_by(series_id=series_id).delete(synchronize_session=False)
                session.query(DownloadTask).filter_by(series_id=series_id).delete(synchronize_session=False)

                # Теперь удаляем сам сериал
                session.delete(series)
                session.commit()
                self.logger.info("db", f"Сериал {series_id} и все связанные с ним записи удалены.")
    
    def add_torrent(self, series_id: int, torrent_data: Dict[str, Any], is_active: bool = True, qb_hash: Optional[str] = None):
        with self.Session() as session:
            torrent = Torrent(
                series_id=series_id,
                torrent_id=torrent_data['torrent_id'],
                link=torrent_data["link"],
                date_time=torrent_data.get("date_time"),
                quality=torrent_data.get("quality"),
                episodes=torrent_data.get("episodes"),
                is_active=is_active,
                qb_hash=qb_hash
            )
            session.add(torrent)
            session.commit()
            return torrent.id

    def get_torrents(self, series_id: int, is_active: Optional[bool] = None) -> List[Dict[str, Any]]:
        with self.Session() as session:
            query = session.query(Torrent).filter_by(series_id=series_id)
            if is_active is not None: query = query.filter_by(is_active=is_active)
            return [{c.name: getattr(t, c.name) for c in t.__table__.columns} for t in query.all()]

    def get_torrent_by_hash(self, qb_hash: str) -> Optional[Dict[str, Any]]:
        with self.Session() as session:
            torrent = session.query(Torrent).filter_by(qb_hash=qb_hash).first()
            if torrent:
                return {c.name: getattr(torrent, c.name) for c in torrent.__table__.columns}
            return None

    def update_torrent_by_id(self, torrent_db_id: int, data: Dict[str, Any]):
        with self.Session() as session:
            torrent = session.query(Torrent).filter_by(id=torrent_db_id).first()
            if torrent:
                for key, value in data.items():
                    setattr(torrent, key, value)
                session.commit()

    def set_setting(self, key: str, value: Any):
        with self.Session() as session:
            session.merge(Setting(key=key, value=str(value)))
            session.commit()

    def get_setting(self, key: str, default: Any = None) -> Any:
        with self.Session() as session:
            setting = session.query(Setting).filter_by(key=key).first()
            return setting.value if setting else default

    def get_settings_by_prefix(self, prefix: str) -> Dict[str, str]:
        with self.Session() as session:
            settings = session.query(Setting).filter(Setting.key.like(f"{prefix}%")).all()
            return {s.key: s.value for s in settings}

    def add_log(self, group: str, level: str, message: str):
        with self.Session() as session:
            session.add(Log(group=group, level=level, message=message))
            session.commit()

    def get_logs(self, group: Optional[str] = None, level: Optional[str] = None) -> List[Dict[str, str]]:
        with self.Session() as session:
            query = session.query(Log)
            if group: query = query.filter_by(group=group)
            if level: query = query.filter_by(level=level)
            return [{"id": l.id, "timestamp": l.timestamp.isoformat(), "group": l.group, "level": l.level, "message": l.message} for l in query.order_by(Log.timestamp.asc()).all()]
            
    def clear_all_data_except_auth(self):
        with self.Session() as session:
            for table in reversed(Base.metadata.sorted_tables):
                if table.name != 'auth':
                    session.execute(table.delete())
            session.commit()
            self.logger.info("db", "Все данные, кроме данных авторизации, очищены.")

    def get_all_agent_tasks(self) -> List[Dict[str, Any]]:
        with self.Session() as session:
            tasks = session.query(AgentTask).all()
            return [{c.name: getattr(task, c.name) for c in task.__table__.columns} for task in tasks]

    def add_or_update_agent_task(self, task_data: Dict[str, Any]):
        with self.Session() as session:
            task = AgentTask(**task_data)
            session.merge(task)
            session.commit()

    def remove_agent_task(self, torrent_hash: str):
        with self.Session() as session:
            task = session.query(AgentTask).filter_by(torrent_hash=torrent_hash).first()
            if task:
                session.delete(task)
                session.commit()

    def get_parser_profiles(self) -> List[Dict[str, Any]]:
        with self.Session() as session:
            profiles = session.query(ParserProfile).all()
            return [{"id": p.id, "name": p.name, "preferred_voiceovers": p.preferred_voiceovers} for p in profiles]

    def create_parser_profile(self, name: str) -> int:
        with self.Session() as session:
            if session.query(ParserProfile).filter_by(name=name).first():
                raise ValueError(f"Профиль парсера с именем '{name}' уже существует.")
            new_profile = ParserProfile(name=name, preferred_voiceovers="")
            session.add(new_profile)
            session.commit()
            return new_profile.id

    def update_parser_profile(self, profile_id: int, data: Dict[str, Any]):
        with self.Session() as session:
            profile = session.query(ParserProfile).filter_by(id=profile_id).first()
            if not profile:
                raise ValueError(f"Профиль с ID {profile_id} не найден.")
            
            if 'name' in data:
                profile.name = data['name']
            if 'preferred_voiceovers' in data:
                profile.preferred_voiceovers = data['preferred_voiceovers']
            
            session.commit()

    def delete_parser_profile(self, profile_id: int):
        with self.Session() as session:
            profile = session.query(ParserProfile).filter_by(id=profile_id).first()
            if profile:
                series_using_profile = session.query(Series).filter_by(parser_profile_id=profile_id).count()
                if series_using_profile > 0:
                    raise ValueError(f"Невозможно удалить профиль, так как он используется в {series_using_profile} сериалах.")
                session.delete(profile)
                session.commit()

    def get_rules_for_profile(self, profile_id: int) -> List[Dict[str, Any]]:
        with self.Session() as session:
            rules = session.query(ParserRule).filter_by(profile_id=profile_id).options(joinedload(ParserRule.conditions)).order_by(ParserRule.priority).all()
            result = []
            for rule in rules:
                conditions = [
                    {"id": c.id, "condition_type": c.condition_type, "pattern": c.pattern, "logical_operator": c.logical_operator}
                    for c in rule.conditions
                ]
                result.append({
                    "id": rule.id,
                    "profile_id": rule.profile_id,
                    "name": rule.name,
                    "priority": rule.priority,
                    "action_pattern": rule.action_pattern,
                    # ---> ДОБАВЛЕНО НЕДОСТАЮЩЕЕ ПОЛЕ <---
                    "continue_after_match": rule.continue_after_match,
                    "conditions": conditions
                })
            return result

    def add_rule_to_profile(self, profile_id: int, rule_data: Dict[str, Any]) -> int:
        with self.Session() as session:
            max_priority_obj = session.query(func.max(ParserRule.priority)).filter_by(profile_id=profile_id).one_or_none()
            max_priority = max_priority_obj[0] if max_priority_obj and max_priority_obj[0] is not None else 0
            
            new_rule = ParserRule(
                profile_id=profile_id,
                name=rule_data.get('name', 'Новое правило'),
                action_pattern=rule_data.get('action_pattern', '[]'),
                priority=max_priority + 1,
                # ---> ДОБАВЛЕНО: Учитываем новое поле при создании <---
                continue_after_match=rule_data.get('continue_after_match', False)
            )
            
            if conditions_data := rule_data.get('conditions'):
                for cond_data in conditions_data:
                    new_rule.conditions.append(ParserRuleCondition(
                        condition_type=cond_data.get('condition_type'),
                        pattern=cond_data.get('pattern'),
                        logical_operator=cond_data.get('logical_operator', 'AND')
                    ))

            session.add(new_rule)
            session.commit()
            return new_rule.id

    def update_rule(self, rule_id: int, rule_data: Dict[str, Any]):
        with self.Session() as session:
            try:
                rule = session.query(ParserRule).filter_by(id=rule_id).first()
                if not rule:
                    self.logger.error("db", f"Попытка обновить несуществующее правило с ID: {rule_id}")
                    return

                session.query(ParserRuleCondition).filter_by(rule_id=rule_id).delete(synchronize_session=False)
                session.flush()

                rule.name = rule_data.get('name', rule.name)
                rule.action_pattern = rule_data.get('action_pattern', rule.action_pattern)
                # ---> ДОБАВЛЕНО: Обновляем новое поле <---
                rule.continue_after_match = rule_data.get('continue_after_match', rule.continue_after_match)

                if conditions_data := rule_data.get('conditions'):
                    for cond_data in conditions_data:
                        new_condition = ParserRuleCondition(
                            rule_id=rule.id,
                            condition_type=cond_data.get('condition_type'),
                            pattern=cond_data.get('pattern'),
                            logical_operator=cond_data.get('logical_operator', 'AND')
                        )
                        session.add(new_condition)
                
                session.commit()
            except Exception as e:
                self.logger.error("db.update_rule", f"Ошибка при обновлении правила ID {rule_id}: {e}", exc_info=True)
                session.rollback()
                raise
    
    def update_rules_order(self, ordered_rule_ids: List[int]):
         with self.Session() as session:
            for index, rule_id in enumerate(ordered_rule_ids):
                rule = session.query(ParserRule).filter_by(id=rule_id).first()
                if rule:
                    rule.priority = index
            session.commit()

    def delete_rule(self, rule_id: int):
        with self.Session() as session:
            rule = session.query(ParserRule).filter_by(id=rule_id).first()
            if rule:
                session.delete(rule)
                session.commit()
    
    def get_media_items_for_series(self, series_id: int) -> List[Dict[str, Any]]:
        with self.Session() as session:
            items = session.query(MediaItem).filter_by(series_id=series_id).options(joinedload(MediaItem.series)).all()
            
            result = []
            for item in items:
                item_dict = {c.name: getattr(item, c.name) for c in item.__table__.columns if c.name != 'series'}
                if item.series:
                    item_dict['series'] = {c.name: getattr(item.series, c.name) for c in item.series.__table__.columns}
                result.append(item_dict)
            return result

    # --- ДОБАВЛЕННЫЙ МЕТОД ---
    def get_media_items_with_filename(self, series_id: int) -> List[Dict[str, Any]]:
        """Возвращает список медиа-элементов для указанного сериала, у которых есть имя файла."""
        with self.Session() as session:
            items = session.query(MediaItem).filter(
                MediaItem.series_id == series_id,
                MediaItem.final_filename.isnot(None)
            ).all()
            return [{c.name: getattr(item, c.name) for c in item.__table__.columns} for item in items]

    def get_media_item_by_uid(self, unique_id: str) -> Optional[Dict[str, Any]]:
        with self.Session() as session:
            item = session.query(MediaItem).filter_by(unique_id=unique_id).first()
            if not item:
                return None
            return {c.name: getattr(item, c.name) for c in item.__table__.columns}
    
    def get_media_items_by_plan_status(self, series_id: int, plan_status: str) -> List[Dict[str, Any]]:
        """Возвращает медиа-элементы для указанного сериала с заданным plan_status."""
        with self.Session() as session:
            items = session.query(MediaItem).filter_by(series_id=series_id, plan_status=plan_status).all()
            return [{c.name: getattr(item, c.name) for c in item.__table__.columns} for item in items]

    def get_media_items_by_plan_statuses(self, series_id: int, plan_statuses: List[str]) -> List[Dict[str, Any]]:
        """Возвращает медиа-элементы для указанного сериала с одним из указанных plan_status."""
        with self.Session() as session:
            items = session.query(MediaItem).filter(
                MediaItem.series_id == series_id,
                MediaItem.plan_status.in_(plan_statuses)
            ).all()
            return [{c.name: getattr(item, c.name) for c in item.__table__.columns} for item in items]

    def update_media_item_plan_statuses(self, status_map: Dict[str, str]):
        """Массово обновляет plan_status для медиа-элементов."""
        with self.Session() as session:
            for unique_id, new_status in status_map.items():
                session.query(MediaItem).filter_by(unique_id=unique_id).update({'plan_status': new_status})
            session.commit()

    def reset_plan_status_for_series(self, series_id: int):
        """Сбрасывает plan_status в 'candidate' для всех медиа-элементов сериала."""
        with self.Session() as session:
            session.query(MediaItem).filter_by(series_id=series_id).update(
                {'plan_status': 'candidate'}, synchronize_session=False
            )
            session.commit()

    def update_media_item_filename(self, unique_id: str, filename: str):
        with self.Session() as session:
            item = session.query(MediaItem).filter_by(unique_id=unique_id).first()
            if item:
                item.final_filename = filename
                session.commit()
            else:
                self.logger.warning("db", f"Попытка обновить имя файла для несуществующего media_item с UID: {unique_id}")

    # --- ДОБАВЛЕННЫЙ МЕТОД ---
    def update_media_item_download_status(self, unique_id: str, status: str):
        """Обновляет статус загрузки для медиа-элемента по его unique_id."""
        with self.Session() as session:
            item = session.query(MediaItem).filter_by(unique_id=unique_id).first()
            if item:
                item.status = status
                session.commit()
            else:
                self.logger.warning("db", f"Попытка обновить статус для несуществующего media_item с UID: {unique_id}")

    # --- ДОБАВЛЕННЫЙ МЕТОД ---
    def reset_media_item_download_state(self, unique_id: str):
        """Сбрасывает состояние загрузки для медиа-элемента: удаляет имя файла и ставит статус 'pending'."""
        with self.Session() as session:
            item = session.query(MediaItem).filter_by(unique_id=unique_id).first()
            if item:
                item.final_filename = None
                item.status = 'pending'
                session.commit()
            else:
                self.logger.warning("db", f"Попытка сбросить статус для несуществующего media_item с UID: {unique_id}")

    def add_or_update_media_items(self, items_to_process: List[Dict[str, Any]]):
        if not items_to_process:
            return

        series_id_to_update = items_to_process[0].get('series_id')
        if not series_id_to_update:
            self.logger.error("db", "В add_or_update_media_items не передан series_id.")
            return

        with self.Session() as session:
            try:
                existing_items_query = session.query(MediaItem).filter_by(series_id=series_id_to_update).all()
                existing_items_map = {item.unique_id: item for item in existing_items_query}
                
                items_added = 0
                items_updated = 0

                for item_data in items_to_process:
                    unique_id = item_data.get('unique_id')
                    if not unique_id: continue

                    if existing_item := existing_items_map.get(unique_id):
                        # --- НАЧАЛО ИЗМЕНЕНИЯ: Логика обновления существующего элемента ---
                        
                        # Принудительно обновляем все распарсенные поля новыми данными
                        existing_item.season = item_data.get('season')
                        existing_item.episode_start = item_data.get('episode_start')
                        existing_item.episode_end = item_data.get('episode_end')
                        existing_item.publication_date = item_data.get('publication_date')
                        existing_item.voiceover_tag = item_data.get('voiceover_tag')
                        existing_item.resolution = item_data.get('resolution')

                        # КРИТИЧЕСКИ ВАЖНО: Сбрасываем статус планирования.
                        # Это заставит SmartCollector пересмотреть этот элемент с новыми данными.
                        existing_item.plan_status = 'candidate'
                        
                        items_updated += 1
                        # --- КОНЕЦ ИЗМЕНЕНИЯ ---
                    else:
                        # Добавляем новый элемент, если его не было
                        new_item = MediaItem(**item_data)
                        session.add(new_item)
                        items_added += 1

                session.commit()
                self.logger.info("db", f"Сохранение медиа-элементов завершено. Добавлено: {items_added}, Обновлено: {items_updated}.")
            except Exception as e:
                self.logger.error("db", f"Ошибка в транзакции add_or_update_media_items: {e}", exc_info=True)
                session.rollback()
                raise

    def set_media_item_ignored_status(self, item_id: int, is_ignored: bool):
         with self.Session() as session:
            item = session.query(MediaItem).filter_by(id=item_id).first()
            if item:
                item.is_ignored_by_user = is_ignored
                session.commit()
    
    # --- ДОБАВЛЕННЫЙ МЕТОД ---
    def get_series_download_statuses(self, series_id: int) -> Dict[str, int]:
        """Агрегирует статусы загрузок для указанного сериала по таблице MediaItem."""
        with self.Session() as session:
            statuses = session.query(MediaItem.status, func.count(MediaItem.id)).\
                filter(MediaItem.series_id == series_id).\
                group_by(MediaItem.status).all()
            return {status: count for status, count in statuses}

    def add_download_task(self, task_data: Dict[str, Any]):
        task_data['task_key'] = task_data.pop('unique_id')
        with self.Session() as session:
            new_task = DownloadTask(**task_data, status='pending', attempts=0)
            session.add(new_task)
            session.commit()

    def get_download_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        with self.Session() as session:
            task = session.query(DownloadTask).filter_by(id=task_id).first()
            if not task: return None
            return {c.name: getattr(task, c.name) for c in task.__table__.columns}

    def get_download_task_by_uid(self, unique_id: str) -> Optional[Dict[str, Any]]:
        with self.Session() as session:
            task = session.query(DownloadTask).filter(
                DownloadTask.task_key == unique_id,
                DownloadTask.task_type == 'vk_video',
                DownloadTask.status.in_(['pending', 'downloading'])
            ).first()
            if not task: return None
            return {c.name: getattr(task, c.name) for c in task.__table__.columns}

    def get_pending_download_tasks(self, limit: int) -> List[Dict[str, Any]]:
        with self.Session() as session:
            # Используем правильное имя столбца `task_key` и фильтруем по типу задачи
            tasks = session.query(DownloadTask).join(
                MediaItem, DownloadTask.task_key == MediaItem.unique_id
            ).filter(
                DownloadTask.task_type == 'vk_video',
                DownloadTask.status == 'pending',
                MediaItem.plan_status.in_(['in_plan_single', 'in_plan_compilation'])
            ).order_by(DownloadTask.created_at).limit(limit).all()
            
            return [{c.name: getattr(task, c.name) for c in task.__table__.columns} for task in tasks]
        
    def get_active_download_tasks(self) -> List[Dict[str, Any]]:
        """Возвращает список VK-задач, находящихся в статусе 'pending' или 'downloading'."""
        with self.Session() as session:
            tasks = session.query(DownloadTask).filter(
                DownloadTask.task_type == 'vk_video',  # <--- ДОБАВЛЕНО ЭТО УСЛОВИЕ
                DownloadTask.status.in_(['pending', 'downloading'])
            ).order_by(DownloadTask.created_at).all()

            result = []
            for task in tasks:
                task_dict = {}
                for c in task.__table__.columns:
                    value = getattr(task, c.name)
                    if isinstance(value, datetime):
                        task_dict[c.name] = value.isoformat()
                    else:
                        task_dict[c.name] = value
                result.append(task_dict)
            return result

    def update_download_task_status(self, task_id: int, status: str, error_message: str = None):
        with self.Session() as session:
            task = session.query(DownloadTask).filter_by(id=task_id).first()
            if task:
                task.status = status
                if status == 'downloading':
                    task.attempts = (task.attempts or 0) + 1
                if error_message:
                    task.error_message = error_message
                session.commit()

    # --- ДОБАВЛЕННЫЙ МЕТОД ---
    def delete_download_task(self, task_id: int):
        """Удаляет задачу на загрузку по ее ID."""
        with self.Session() as session:
            task = session.query(DownloadTask).filter_by(id=task_id).first()
            if task:
                session.delete(task)
                session.commit()

    def requeue_stuck_downloads(self) -> int:
        with self.Session() as session:
            # --- ИЗМЕНЕНИЕ: Ищем задачи со статусом 'downloading' И 'error' ---
            stuck_tasks = session.query(DownloadTask).filter(
                DownloadTask.status.in_(['downloading', 'error'])
            )
            # --- КОНЕЦ ИЗМЕНЕНИЯ ---
            count = stuck_tasks.count()
            if count > 0:
                # Сбрасываем все найденные задачи в статус 'pending'
                stuck_tasks.update({"status": "pending"}, synchronize_session=False)
                session.commit()
            return count

    def get_all_download_tasks(self) -> List[Dict[str, Any]]:
        with self.Session() as session:
            tasks = session.query(DownloadTask).order_by(DownloadTask.created_at.desc()).all()

            result = []
            for task in tasks:
                task_dict = {}
                for c in task.__table__.columns:
                    value = getattr(task, c.name)
                    if isinstance(value, datetime):
                        task_dict[c.name] = value.isoformat()
                    else:
                        task_dict[c.name] = value
                result.append(task_dict)
            return result

    def clear_download_queue(self) -> int:
        """Удаляет все задачи, которые не находятся в процессе загрузки."""
        with self.Session() as session:
            tasks_to_delete = session.query(DownloadTask).filter(DownloadTask.status.in_(['pending', 'error']))
            count = tasks_to_delete.count()
            if count > 0:
                tasks_to_delete.delete(synchronize_session=False)
                session.commit()
            return count

    def update_media_item_chapters(self, unique_id: str, chapters_json: str):
        """Сохраняет оглавление для медиа-элемента."""
        with self.Session() as session:
            item = session.query(MediaItem).filter_by(unique_id=unique_id).first()
            if item:
                item.chapters = chapters_json
                session.commit()

    def register_downloaded_media_item(self, unique_id: str, filename: str):
        """Регистрирует медиа-элемент как скачанный, обновляя имя файла и статус."""
        with self.Session() as session:
            item = session.query(MediaItem).filter_by(unique_id=unique_id).first()
            if item:
                item.final_filename = filename
                item.status = 'completed'
                session.commit()
            else:
                self.logger.warning("db", f"Попытка зарегистрировать файл для несуществующего media_item с UID: {unique_id}")

    def get_raw_table_content(self, table_name: str) -> List[Dict]:
        """Возвращает все содержимое таблицы в виде списка словарей."""
        from datetime import datetime
        
        with self.engine.connect() as connection:
            table = Base.metadata.tables[table_name]
            result = connection.execute(table.select())
            
            rows = []
            for row in result:
                row_dict = dict(row._mapping)
                for key, value in row_dict.items():
                    if isinstance(value, datetime):
                        row_dict[key] = value.isoformat()
                rows.append(row_dict)
            return rows

    def set_media_item_ignored_status_by_uid(self, unique_id: str, is_ignored: bool):
        """Обновляет статус игнорирования для одного медиа-элемента по его unique_id."""
        with self.Session() as session:
            item = session.query(MediaItem).filter_by(unique_id=unique_id).first()
            if item:
                item.is_ignored_by_user = is_ignored
                session.commit()

    def update_series_ignored_seasons(self, series_id: int, seasons: list):
        """Обновляет список игнорируемых сезонов для сериала."""
        with self.Session() as session:
            series = session.query(Series).filter_by(id=series_id).first()
            if series:
                series.ignored_seasons = json.dumps(seasons)
                session.commit()

    def update_media_item_slicing_status(self, unique_id: str, status: str):
        """Обновляет статус нарезки для медиа-элемента."""
        with self.Session() as session:
            item = session.query(MediaItem).filter_by(unique_id=unique_id).first()
            if item:
                item.slicing_status = status
                session.commit()

    def create_slicing_task(self, unique_id: str, series_id: int) -> int:
        """Создает новую задачу на нарезку в очереди."""
        with self.Session() as session:
            new_task = SlicingTask(media_item_unique_id=unique_id, series_id=series_id, status='pending')
            session.add(new_task)
            session.commit()
            return new_task.id

    def get_pending_slicing_task(self) -> Optional[Dict[str, Any]]:
        """Извлекает одну ожидающую задачу на нарезку."""
        with self.Session() as session:
            task = session.query(SlicingTask).filter_by(status='pending').order_by(SlicingTask.created_at).first()
            if not task:
                return None
            return {c.name: getattr(task, c.name) for c in task.__table__.columns}

    def update_slicing_task(self, task_id: int, updates: Dict[str, Any]):
        """Обновляет данные задачи на нарезку (статус, прогресс и т.д.)."""
        with self.Session() as session:
            task = session.query(SlicingTask).filter_by(id=task_id).first()
            if task:
                for key, value in updates.items():
                    setattr(task, key, value)
                session.commit()

    def delete_slicing_task(self, task_id: int):
        """Удаляет завершенную задачу на нарезку."""
        with self.Session() as session:
            task = session.query(SlicingTask).filter_by(id=task_id).first()
            if task:
                session.delete(task)
                session.commit()

    def add_sliced_file(self, series_id: int, source_unique_id: str, episode_number: int, file_path: str):
        """Добавляет запись о новом нарезанном файле."""
        with self.Session() as session:
            new_file = SlicedFile(
                series_id=series_id,
                source_media_item_unique_id=source_unique_id,
                episode_number=episode_number,
                file_path=file_path
            )
            session.add(new_file)
            session.commit()

    def get_sliced_files_for_source(self, source_unique_id: str) -> List[Dict[str, Any]]:
        """Возвращает все нарезанные файлы для указанной компиляции."""
        with self.Session() as session:
            items = session.query(SlicedFile).filter_by(source_media_item_unique_id=source_unique_id).all()
            return [{c.name: getattr(item, c.name) for c in item.__table__.columns} for item in items]

    def requeue_stuck_slicing_tasks(self) -> int:
        """Восстанавливает 'зависшие' задачи нарезки после перезапуска."""
        with self.Session() as session:
            stuck_tasks = session.query(SlicingTask).filter_by(status='slicing')
            count = stuck_tasks.count()
            if count > 0:
                stuck_tasks.update({"status": "pending"}, synchronize_session=False)
                session.commit()
            return count
        
    def get_all_slicing_tasks(self) -> List[Dict[str, Any]]:
        """Возвращает все активные задачи на нарезку."""
        with self.Session() as session:
            tasks = session.query(SlicingTask).order_by(SlicingTask.created_at).all()
            result = []
            for task in tasks:
                task_dict = {c.name: getattr(task, c.name) for c in task.__table__.columns}
                if task_dict.get('created_at'):
                    task_dict['created_at'] = task_dict['created_at'].isoformat()
                result.append(task_dict)
            return result

    def delete_sliced_files_for_source(self, source_unique_id: str) -> int:
        """Удаляет все записи о нарезанных файлах для указанной компиляции."""
        with self.Session() as session:
            deleted_count = session.query(SlicedFile).filter_by(source_media_item_unique_id=source_unique_id).delete(synchronize_session=False)
            session.commit()
            return deleted_count

    def get_all_sliced_files_for_series(self, series_id: int) -> List[Dict[str, Any]]:
        """Возвращает все нарезанные файлы для указанного сериала."""
        with self.Session() as session:
            items = session.query(SlicedFile).filter_by(series_id=series_id).all()
            return [{c.name: getattr(item, c.name) for c in item.__table__.columns} for item in items]
        
    def update_sliced_file_status(self, file_id: int, status: str):
        """Обновляет статус для одного нарезанного файла по его ID."""
        with self.Session() as session:
            item = session.query(SlicedFile).filter_by(id=file_id).first()
            if item:
                item.status = status
                session.commit()

    def update_media_item_slicing_status_by_uid(self, unique_id: str, status: str):
        """Обновляет статус нарезки для медиа-элемента по его unique_id."""
        with self.Session() as session:
            item = session.query(MediaItem).filter_by(unique_id=unique_id).first()
            if item:
                item.slicing_status = status
                session.commit()

    def get_series_slicing_statuses(self, series_id: int) -> Dict[str, int]:
        """Агрегирует статусы нарезки для указанного сериала по таблице MediaItem."""
        with self.Session() as session:
            statuses = session.query(MediaItem.slicing_status, func.count(MediaItem.id)).\
                filter(MediaItem.series_id == series_id).\
                group_by(MediaItem.slicing_status).all()
            return {status: count for status, count in statuses}
    
    def get_unique_log_groups(self) -> List[str]:
        """Возвращает отсортированный список всех уникальных групп из логов."""
        with self.Session() as session:
            # Выполняем запрос на получение уникальных значений из столбца 'group'
            query_result = session.query(Log.group).distinct().order_by(Log.group).all()
            # Преобразуем результат (список кортежей) в простой список строк
            return [item[0] for item in query_result]
    
    def delete_slicing_task_by_uid(self, unique_id: str):
        """Удаляет все задачи на нарезку для указанного media_item_unique_id."""
        with self.Session() as session:
            tasks = session.query(SlicingTask).filter_by(media_item_unique_id=unique_id)
            if tasks.count() > 0:
                self.logger.info("db", f"Удаление {tasks.count()} старых задач на нарезку для UID {unique_id}.")
                tasks.delete(synchronize_session=False)
                session.commit()

    def get_all_slicing_tasks(self) -> List[Dict[str, Any]]:
        """Возвращает все активные задачи на нарезку."""
        with self.Session() as session:
            tasks = session.query(SlicingTask).order_by(SlicingTask.created_at).all()
            result = []
            for task in tasks:
                task_dict = {c.name: getattr(task, c.name) for c in task.__table__.columns}
                if task_dict.get('created_at'):
                    task_dict['created_at'] = task_dict['created_at'].isoformat()
                result.append(task_dict)
            return result
        
    def get_media_items_by_slicing_status(self, series_id: int, status: str) -> List[Dict[str, Any]]:
        """Возвращает медиа-элементы для сериала с указанным статусом нарезки."""
        with self.Session() as session:
            items = session.query(MediaItem).filter_by(series_id=series_id, slicing_status=status).all()
            return [{c.name: getattr(item, c.name) for c in item.__table__.columns} for item in items]

    def add_sliced_file_if_not_exists(self, series_id: int, source_unique_id: str, episode_number: int, file_path: str):
        """Добавляет запись о нарезанном файле, только если её ещё не существует."""
        with self.Session() as session:
            exists = session.query(SlicedFile).filter_by(
                source_media_item_unique_id=source_unique_id,
                episode_number=episode_number
            ).first()

            if not exists:
                new_file = SlicedFile(
                    series_id=series_id,
                    source_media_item_unique_id=source_unique_id,
                    episode_number=episode_number,
                    file_path=file_path
                )
                session.add(new_file)
                session.commit()
                return True
            return False
    def get_all_agent_tasks_for_series(self, series_id: int) -> List[Dict[str, Any]]:
        """Возвращает все активные задачи агента для указанного сериала."""
        with self.Session() as session:
            tasks = session.query(AgentTask).filter_by(series_id=series_id).all()
            return [{c.name: getattr(task, c.name) for c in task.__table__.columns} for task in tasks]
        
    def get_all_active_torrent_tasks(self) -> List[Dict[str, Any]]:
        """Возвращает все задачи мониторинга торрентов с именем сериала."""
        with self.Session() as session:
            tasks = session.query(DownloadTask, Series.name).join(
                Series, Series.id == DownloadTask.series_id
            ).filter(DownloadTask.task_type == 'torrent').all()
            
            result = []
            for task, series_name in tasks:
                task_dict = {c.name: getattr(task, c.name) for c in task.__table__.columns}
                task_dict['series_name'] = series_name
                result.append(task_dict)
            return result
        
    def set_viewing_status(self, series_id: int, is_viewing: bool):
        """Устанавливает или сбрасывает статус просмотра."""
        with self.Session() as session:
            value = datetime.now(timezone.utc) if is_viewing else None
            session.query(SeriesStatus).filter_by(series_id=series_id).update({'is_viewing': value})
            session.commit()

    def get_stale_viewing_series_ids(self, timeout_seconds: int = 90) -> list[int]:
        """Находит ID сериалов, у которых статус 'viewing' (метка времени) устарел."""
        with self.Session() as session:
            stale_threshold = datetime.now(timezone.utc) - timedelta(seconds=timeout_seconds)
            stale_series = session.query(SeriesStatus).filter(
                SeriesStatus.is_viewing.isnot(None),
                SeriesStatus.is_viewing < stale_threshold
            ).all()
            return [s.series_id for s in stale_series]

    def get_all_torrent_tasks_for_series(self, series_id: int) -> List[Dict[str, Any]]:
        """Возвращает все задачи мониторинга торрентов для указанного сериала."""
        with self.Session() as session:
            tasks = session.query(DownloadTask).filter_by(
                series_id=series_id,
                task_type='torrent'
            ).all()
            return [{c.name: getattr(task, c.name) for c in task.__table__.columns} for task in tasks]
        
    def update_vk_series_status_flags(self, series_id: int, flags: Dict[str, bool]):
        """Атомарно обновляет все флаги статусов для VK-сериала."""
        with self.Session() as session:
            update_data = {f"is_{name}": value for name, value in flags.items()}
            session.query(SeriesStatus).filter_by(series_id=series_id).update(update_data)
            session.commit()

    def get_media_items_by_status(self, series_id: int, status: str) -> List[Dict[str, Any]]:
        """Возвращает медиа-элементы для указанного сериала с заданным статусом выполнения."""
        with self.Session() as session:
            items = session.query(MediaItem).filter_by(series_id=series_id, status=status).all()
            return [{c.name: getattr(item, c.name) for c in item.__table__.columns} for item in items]
        
    def update_download_task_progress(self, task_id: int, progress_data: Dict[str, Any]):
        """Атомарно обновляет все поля прогресса для задачи на загрузку."""
        with self.Session() as session:
            session.query(DownloadTask).filter_by(id=task_id).update(progress_data)
            session.commit()

    def add_or_update_torrent_files(self, torrent_db_id: int, files_data: List[Dict[str, Any]]):
        """
        Массово добавляет или обновляет записи о файлах для одного торрента.
        Удаляет из БД записи о файлах, которых больше нет в qBittorrent.
        """
        with self.Session() as session:
            try:
                # Получаем существующие файлы из БД для этого торрента
                existing_files = session.query(TorrentFile).filter_by(torrent_db_id=torrent_db_id).all()
                existing_paths = {f.original_path: f for f in existing_files}

                # Получаем актуальные пути из переданных данных
                current_paths = {f['original_path'] for f in files_data}

                # Добавляем или обновляем файлы
                for file_info in files_data:
                    path = file_info['original_path']
                    if path in existing_paths:
                        # Если файл уже есть в БД, обновляем его
                        existing_file = existing_paths[path]
                        existing_file.status = file_info['status']
                        existing_file.extracted_metadata = file_info['extracted_metadata']
                        existing_file.renamed_path = file_info.get('renamed_path')
                    else:
                        # Если файла нет, создаем новую запись
                        new_file = TorrentFile(
                            torrent_db_id=torrent_db_id,
                            **file_info
                        )
                        session.add(new_file)

                # Удаляем записи о файлах, которых больше нет в торренте
                for path, file_obj in existing_paths.items():
                    if path not in current_paths:
                        session.delete(file_obj)

                session.commit()
            except Exception as e:
                self.logger.error("db", f"Ошибка при обновлении файлов торрента (ID: {torrent_db_id}): {e}", exc_info=True)
                session.rollback()
                raise
    def get_torrent_files_for_series(self, series_id: int) -> List[Dict[str, Any]]:
        """Возвращает все записи TorrentFile для указанного сериала, включая qb_hash."""
        with self.Session() as session:
            results = session.query(TorrentFile, Torrent.qb_hash).\
                join(Torrent, TorrentFile.torrent_db_id == Torrent.id).\
                filter(Torrent.series_id == series_id).all()

            files_with_hash = []
            for file_obj, qb_hash in results:
                file_dict = {c.name: getattr(file_obj, c.name) for c in file_obj.__table__.columns}
                file_dict['qb_hash'] = qb_hash
                files_with_hash.append(file_dict)
            return files_with_hash

    def get_source_filenames_for_series(self, series_id: int) -> List[str]:
        """
        Возвращает список исходных имён файлов для тестирования парсера.
        Для торрентов - original_path из torrent_files.
        Для VK - final_filename из media_items.
        """
        with self.Session() as session:
            series = session.query(Series).filter_by(id=series_id).first()
            if not series:
                return []

            filenames = []
            if series.source_type == 'torrent':
                results = session.query(TorrentFile.original_path).\
                    join(Torrent).\
                    filter(Torrent.series_id == series_id).all()
                filenames = [row[0] for row in results]

            elif series.source_type == 'vk_video':
                # Для VK исходных названий нет, поэтому берем финальные как наиболее близкие
                results = session.query(MediaItem.final_filename).\
                    filter(MediaItem.series_id == series_id, MediaItem.final_filename.isnot(None)).all()
                filenames = [row[0] for row in results]

            # Для тестирования парсера возвращаем только базовые имена, без подкаталогов
            return [os.path.basename(f) for f in filenames]

    def get_pending_rename_files_for_series(self, series_id: int) -> List[Dict[str, Any]]:
        """Возвращает файлы, ожидающие переименования, с хешем их родительского торрента."""
        with self.Session() as session:
            results = session.query(TorrentFile, Torrent.qb_hash).\
                join(Torrent, TorrentFile.torrent_db_id == Torrent.id).\
                filter(
                    Torrent.series_id == series_id,
                    TorrentFile.status == 'pending_rename'
                ).all()

            files_to_rename = []
            for file_obj, qb_hash in results:
                file_dict = {c.name: getattr(file_obj, c.name) for c in file_obj.__table__.columns}
                file_dict['qb_hash'] = qb_hash
                files_to_rename.append(file_dict)
            return files_to_rename

    def update_torrent_file_status(self, file_id: int, new_status: str, new_path: str = None):
        """Обновляет статус и новое имя файла торрента."""
        with self.Session() as session:
            file = session.query(TorrentFile).filter_by(id=file_id).first()
            if file:
                file.status = new_status
                if new_path:
                    file.renamed_path = new_path
                session.commit()

    def deactivate_torrent_and_clear_files(self, torrent_db_id: int):
        """
        Помечает торрент как неактивный и удаляет все связанные с ним записи о файлах.
        """
        with self.Session() as session:
            try:
                # Находим торрент
                torrent = session.query(Torrent).filter_by(id=torrent_db_id).first()
                if torrent:
                    # Удаляем все связанные файлы из таблицы torrent_files
                    session.query(TorrentFile).filter_by(torrent_db_id=torrent_db_id).delete(synchronize_session=False)

                    # Помечаем сам торрент как неактивный
                    torrent.is_active = False

                    session.commit()
                    self.logger.info("db", f"Торрент ID {torrent_db_id} деактивирован, связанные файлы очищены.")
            except Exception as e:
                self.logger.error("db", f"Ошибка при деактивации торрента ID {torrent_db_id}: {e}", exc_info=True)
                session.rollback()
                raise

    def get_torrent_files_for_torrent(self, torrent_db_id: int) -> List[Dict[str, Any]]:
        """Возвращает все записи TorrentFile для указанного ID торрента."""
        with self.Session() as session:
            files = session.query(TorrentFile).filter_by(torrent_db_id=torrent_db_id).all()
            return [{c.name: getattr(item, c.name) for c in item.__table__.columns} for item in files]