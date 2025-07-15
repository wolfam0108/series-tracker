import string
import random
import logging
import json
from sqlalchemy import create_engine, func, inspect, text
from sqlalchemy.orm import sessionmaker, joinedload
from sqlalchemy.exc import OperationalError, ProgrammingError, IntegrityError
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any

from models import (
    Base, Auth, Series, RenamingPattern, SeasonPattern, AdvancedRenamingPattern,
    Torrent, Setting, Log, QualityPattern, QualitySearchPattern, ResolutionPattern,
    ResolutionSearchPattern, AgentTask, ScanTask,
    ParserProfile, ParserRule, ParserRuleCondition, MediaItem
)

class Database:
    ENABLE_DEBUG_SCHEMA_CHECK = True

    def __init__(self, db_url: str = "sqlite:///app.db", logger=None):
        self.engine = create_engine(db_url, connect_args={'check_same_thread': False})
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
                    session.commit()

                for table_obj in Base.metadata.sorted_tables:
                    table_name = table_obj.name
                    
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
                        self.logger.debug(f"Ожидаемые колонки: {expected_columns}")
                        self.logger.debug(f"Фактические колонки: {actual_columns}")
                        
                        missing_in_db = expected_columns - actual_columns
                        extra_in_db = actual_columns - expected_columns
                        if missing_in_db:
                            self.logger.debug(f"Колонки, отсутствующие в БД: {missing_in_db}")
                        if extra_in_db:
                            self.logger.debug(f"Лишние колонки в БД: {extra_in_db}")

                        table_obj.drop(self.engine)
                        table_obj.create(self.engine)
                        self.logger.info("db", f"Таблица '{table_name}' успешно пересоздана.")

            except Exception as e:
                self.logger.error("db", f"Ошибка при миграции схемы: {e}. Может потребоваться ручное вмешательство.", exc_info=True)
            finally:
                if self.engine.dialect.name == 'sqlite':
                    session.execute(text('PRAGMA foreign_keys = ON;'))
                    session.commit()
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
            allowed_keys = {c.name for c in Series.__table__.columns if c.name != 'id'}
            series_data = {key: data[key] for key in allowed_keys if key in data}
            
            if 'source_type' not in series_data:
                series_data['source_type'] = 'torrent'
            
            series = Series(**series_data)
            session.add(series)
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
                        if key == 'active_status' and isinstance(value, dict):
                            setattr(series, key, json.dumps(value))
                        else:
                            setattr(series, key, value)
                session.commit()

    def delete_series(self, series_id: int):
        with self.Session() as session:
            series = session.query(Series).filter_by(id=series_id).first()
            if series:
                session.query(Torrent).filter_by(series_id=series_id).delete()
                session.delete(series)
                session.commit()

    def set_series_state(self, series_id: int, state: Any, scan_time: Optional[datetime] = None):
        with self.Session() as session:
            series = session.query(Series).filter_by(id=series_id).first()
            if series:
                if isinstance(state, dict):
                    series.state = json.dumps(state)
                else:
                    series.state = str(state)
                
                if scan_time: series.last_scan_time = scan_time
                session.commit()
    
    def get_series_tasks_in_state(self, series_id: int, state_prefix: str) -> bool:
        with self.Session() as session:
            series = session.query(Series).filter_by(id=series_id).first()
            return series and series.state.startswith(state_prefix)

    def reset_stuck_series_states(self, states_to_reset: List[str]):
        with self.Session() as session:
            query = session.query(Series).filter(Series.state.in_(states_to_reset))
            updated_count = query.update({"state": "waiting"}, synchronize_session=False)
            session.commit()
            self.logger.info("db", f"Сброшен статус для {updated_count} сериалов.")
            return updated_count

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

    def add_torrent_mapping(self, torrent_id: str, qb_hash: str):
        with self.Session() as session:
            torrent = session.query(Torrent).filter_by(torrent_id=torrent_id).first()
            if torrent:
                torrent.qb_hash = qb_hash
                session.commit()
    
    def get_patterns(self) -> List[Dict[str, Any]]:
        with self.Session() as session:
            patterns = session.query(RenamingPattern).order_by(RenamingPattern.priority).all()
            return [{"id": p.id, "name": p.name, "pattern": p.pattern, "priority": p.priority, "is_active": p.is_active} for p in patterns]

    def add_pattern(self, name: str, pattern_str: str) -> int:
        with self.Session() as session:
            if session.query(RenamingPattern).filter_by(name=name).first():
                raise ValueError(f"Паттерн с именем '{name}' уже существует.")
            max_priority = session.query(func.max(RenamingPattern.priority)).scalar() or 0
            new_pattern = RenamingPattern(name=name, pattern=pattern_str, priority=max_priority + 1)
            session.add(new_pattern)
            session.commit()
            return new_pattern.id

    def update_pattern(self, pattern_id: int, data: Dict[str, Any]):
        with self.Session() as session:
            pattern = session.query(RenamingPattern).filter_by(id=pattern_id).first()
            if pattern:
                if 'name' in data and data['name'] != pattern.name:
                    if session.query(RenamingPattern).filter_by(name=data['name']).first():
                        raise ValueError(f"Паттерн с именем '{data['name']}' уже существует.")
                    pattern.name = data['name']
                if 'pattern' in data: pattern.pattern = data['pattern']
                if 'is_active' in data: pattern.is_active = data['is_active']
                session.commit()

    def delete_pattern(self, pattern_id: int):
        with self.Session() as session:
            pattern = session.query(RenamingPattern).filter_by(id=pattern_id).first()
            if pattern:
                session.delete(pattern)
                session.commit()
    
    def update_patterns_order(self, ordered_ids: List[int]):
        with self.Session() as session:
            for index, pattern_id in enumerate(ordered_ids):
                pattern = session.query(RenamingPattern).filter_by(id=pattern_id).first()
                if pattern:
                    pattern.priority = index
            session.commit()
            
    def get_season_patterns(self) -> List[Dict[str, Any]]:
        with self.Session() as session:
            patterns = session.query(SeasonPattern).order_by(SeasonPattern.priority).all()
            return [{"id": p.id, "name": p.name, "pattern": p.pattern, "priority": p.priority, "is_active": p.is_active} for p in patterns]

    def add_season_pattern(self, name: str, pattern_str: str) -> int:
        with self.Session() as session:
            if session.query(SeasonPattern).filter_by(name=name).first():
                raise ValueError(f"Паттерн сезона с именем '{name}' уже существует.")
            max_priority = session.query(func.max(SeasonPattern.priority)).scalar() or 0
            new_pattern = SeasonPattern(name=name, pattern=pattern_str, priority=max_priority + 1)
            session.add(new_pattern)
            session.commit()
            return new_pattern.id

    def update_season_pattern(self, pattern_id: int, data: Dict[str, Any]):
        with self.Session() as session:
            pattern = session.query(SeasonPattern).filter_by(id=pattern_id).first()
            if pattern:
                if 'name' in data and data['name'] != pattern.name:
                    if session.query(SeasonPattern).filter_by(name=data['name']).first():
                        raise ValueError(f"Паттерн сезона с именем '{data['name']}' уже существует.")
                    pattern.name = data['name']
                if 'pattern' in data: pattern.pattern = data['pattern']
                if 'is_active' in data: pattern.is_active = data['is_active']
                session.commit()

    def delete_season_pattern(self, pattern_id: int):
        with self.Session() as session:
            pattern = session.query(SeasonPattern).filter_by(id=pattern_id).first()
            if pattern:
                session.delete(pattern)
                session.commit()
    
    def update_season_patterns_order(self, ordered_ids: List[int]):
        with self.Session() as session:
            for index, pattern_id in enumerate(ordered_ids):
                pattern = session.query(SeasonPattern).filter_by(id=pattern_id).first()
                if pattern:
                    pattern.priority = index
            session.commit()

    def get_advanced_patterns(self) -> List[Dict[str, Any]]:
        with self.Session() as session:
            patterns = session.query(AdvancedRenamingPattern).order_by(AdvancedRenamingPattern.priority).all()
            return [
                {
                    "id": p.id, "name": p.name, "file_filter": p.file_filter,
                    "pattern_search": p.pattern_search, "area_to_replace": p.area_to_replace,
                    "replacement_template": p.replacement_template,
                    "arithmetic_op": p.arithmetic_op,
                    "priority": p.priority, "is_active": p.is_active
                } for p in patterns
            ]

    def add_advanced_pattern(self, data: Dict[str, Any]) -> int:
        with self.Session() as session:
            if session.query(AdvancedRenamingPattern).filter_by(name=data['name']).first():
                raise ValueError(f"Продвинутый паттерн с именем '{data['name']}' уже существует.")
            
            max_priority = session.query(func.max(AdvancedRenamingPattern.priority)).scalar() or 0
            
            new_pattern = AdvancedRenamingPattern(
                name=data['name'],
                file_filter=data['file_filter'],
                pattern_search=data['pattern_search'],
                area_to_replace=data['area_to_replace'],
                replacement_template=data['replacement_template'],
                arithmetic_op=data.get('arithmetic_op'),
                priority=max_priority + 1
            )
            session.add(new_pattern)
            session.commit()
            return new_pattern.id

    def update_advanced_pattern(self, pattern_id: int, data: Dict[str, Any]):
        with self.Session() as session:
            pattern = session.query(AdvancedRenamingPattern).filter_by(id=pattern_id).first()
            if pattern:
                if 'name' in data and data['name'] != pattern.name:
                    if session.query(AdvancedRenamingPattern).filter_by(name=data['name']).first():
                        raise ValueError(f"Продвинутый паттерн с именем '{data['name']}' уже существует.")
                
                for key, value in data.items():
                    if hasattr(pattern, key) and key != 'id':
                        if key == 'arithmetic_op' and (value == '' or value is None):
                             setattr(pattern, key, None)
                        else:
                             setattr(pattern, key, value)
                session.commit()

    def delete_advanced_pattern(self, pattern_id: int):
        with self.Session() as session:
            pattern = session.query(AdvancedRenamingPattern).filter_by(id=pattern_id).first()
            if pattern:
                session.delete(pattern)
                session.commit()

    def update_advanced_patterns_order(self, ordered_ids: List[int]):
        with self.Session() as session:
            for index, pattern_id in enumerate(ordered_ids):
                pattern = session.query(AdvancedRenamingPattern).filter_by(id=pattern_id).first()
                if pattern:
                    pattern.priority = index
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

    def get_quality_patterns(self) -> List[Dict[str, Any]]:
        with self.Session() as session:
            patterns = session.query(QualityPattern).order_by(QualityPattern.priority).all()
            result = []
            for p in patterns:
                session.expire(p)
                search_patterns = [{"id": sp.id, "pattern": sp.pattern} for sp in p.search_patterns]
                result.append({"id": p.id, "standard_value": p.standard_value, "priority": p.priority, "is_active": p.is_active, "search_patterns": search_patterns})
            return result

    def add_quality_pattern(self, standard_value: str) -> int:
        with self.Session() as session:
            if session.query(QualityPattern).filter_by(standard_value=standard_value).first():
                raise ValueError(f"Стандартизированное значение качества '{standard_value}' уже существует.")
            max_priority = session.query(func.max(QualityPattern.priority)).scalar() or 0
            new_pattern = QualityPattern(standard_value=standard_value, priority=max_priority + 1)
            session.add(new_pattern)
            session.commit()
            return new_pattern.id

    def update_quality_pattern(self, pattern_id: int, data: Dict[str, Any]):
        with self.Session() as session:
            pattern = session.query(QualityPattern).filter_by(id=pattern_id).first()
            if pattern:
                if 'standard_value' in data and data['standard_value'] != pattern.standard_value:
                    if session.query(QualityPattern).filter_by(standard_value=data['standard_value']).first():
                        raise ValueError(f"Стандартизированное значение качества '{data['standard_value']}' уже существует.")
                    pattern.standard_value = data['standard_value']
                if 'is_active' in data: pattern.is_active = data['is_active']
                session.commit()

    def delete_quality_pattern(self, pattern_id: int):
        with self.Session() as session:
            pattern = session.query(QualityPattern).filter_by(id=pattern_id).first()
            if pattern:
                session.delete(pattern)
                session.commit()
    
    def update_quality_patterns_order(self, ordered_ids: List[int]):
        with self.Session() as session:
            for index, pattern_id in enumerate(ordered_ids):
                pattern = session.query(QualityPattern).filter_by(id=pattern_id).first()
                if pattern:
                    pattern.priority = index
            session.commit()

    def add_quality_search_pattern(self, quality_pattern_id: int, pattern_str: str):
        with self.Session() as session:
            if session.query(QualitySearchPattern).filter_by(quality_pattern_id=quality_pattern_id, pattern=pattern_str).first():
                raise ValueError(f"Поисковый паттерн '{pattern_str}' уже существует для этого качества.")
            session.add(QualitySearchPattern(quality_pattern_id=quality_pattern_id, pattern=pattern_str))
            session.commit()

    def delete_quality_search_pattern(self, search_pattern_id: int):
        with self.Session() as session:
            pattern = session.query(QualitySearchPattern).filter_by(id=search_pattern_id).first()
            if pattern:
                session.delete(pattern)
                session.commit()

    def get_resolution_patterns(self) -> List[Dict[str, Any]]:
        with self.Session() as session:
            patterns = session.query(ResolutionPattern).order_by(ResolutionPattern.priority).all()
            result = []
            for p in patterns:
                session.expire(p)
                search_patterns = [{"id": sp.id, "pattern": sp.pattern} for sp in p.search_patterns]
                result.append({"id": p.id, "standard_value": p.standard_value, "priority": p.priority, "is_active": p.is_active, "search_patterns": search_patterns})
            return result

    def add_resolution_pattern(self, standard_value: str) -> int:
        with self.Session() as session:
            if session.query(ResolutionPattern).filter_by(standard_value=standard_value).first():
                raise ValueError(f"Стандартизированное значение разрешения '{standard_value}' уже существует.")
            max_priority = session.query(func.max(ResolutionPattern.priority)).scalar() or 0
            new_pattern = ResolutionPattern(standard_value=standard_value, priority=max_priority + 1)
            session.add(new_pattern)
            session.commit()
            return new_pattern.id

    def update_resolution_pattern(self, pattern_id: int, data: Dict[str, Any]):
        with self.Session() as session:
            pattern = session.query(ResolutionPattern).filter_by(id=pattern_id).first()
            if pattern:
                if 'standard_value' in data and data['standard_value'] != pattern.standard_value:
                    if session.query(ResolutionPattern).filter_by(standard_value=data['standard_value']).first():
                        raise ValueError(f"Стандартизированное значение разрешения '{data['standard_value']}' уже существует.")
                    pattern.standard_value = data['standard_value']
                if 'is_active' in data: pattern.is_active = data['is_active']
                session.commit()

    def delete_resolution_pattern(self, pattern_id: int):
        with self.Session() as session:
            pattern = session.query(ResolutionPattern).filter_by(id=pattern_id).first()
            if pattern:
                session.delete(pattern)
                session.commit()

    def update_resolution_patterns_order(self, ordered_ids: List[int]):
        with self.Session() as session:
            for index, pattern_id in enumerate(ordered_ids):
                pattern = session.query(ResolutionPattern).filter_by(id=pattern_id).first()
                if pattern:
                    pattern.priority = index
            session.commit()

    def add_resolution_search_pattern(self, resolution_pattern_id: int, pattern_str: str):
        with self.Session() as session:
            if session.query(ResolutionSearchPattern).filter_by(resolution_pattern_id=resolution_pattern_id, pattern=pattern_str).first():
                raise ValueError(f"Поисковый паттерн '{pattern_str}' уже существует для этого разрешения.")
            session.add(ResolutionSearchPattern(resolution_pattern_id=resolution_pattern_id, pattern=pattern_str))
            session.commit()

    def delete_resolution_search_pattern(self, search_pattern_id: int):
        with self.Session() as session:
            pattern = session.query(ResolutionSearchPattern).filter_by(id=search_pattern_id).first()
            if pattern:
                session.delete(pattern)
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
                    "action_type": rule.action_type,
                    "action_pattern": rule.action_pattern,
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
                action_type=rule_data.get('action_type', 'exclude'),
                action_pattern=rule_data.get('action_pattern', '[]'),
                priority=max_priority + 1
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

                # Явное удаление старых условий
                session.query(ParserRuleCondition).filter_by(rule_id=rule_id).delete(synchronize_session=False)
                session.flush()

                # Обновление полей правила
                rule.name = rule_data.get('name', rule.name)
                rule.action_type = rule_data.get('action_type', rule.action_type)
                rule.action_pattern = rule_data.get('action_pattern', rule.action_pattern)

                # Добавление новых условий
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

    def add_or_update_media_items(self, items_to_process: List[Dict[str, Any]]):
        with self.Session() as session:
            for item_data in items_to_process:
                unique_id = item_data.get('unique_id')
                if not unique_id:
                    continue

                existing_item = session.query(MediaItem).filter_by(unique_id=unique_id).first()
                if existing_item:
                    existing_item.status = item_data.get('status', existing_item.status)
                else:
                    new_item = MediaItem(**item_data)
                    session.add(new_item)
            session.commit()

    def set_media_item_ignored_status(self, item_id: int, is_ignored: bool):
         with self.Session() as session:
            item = session.query(MediaItem).filter_by(id=item_id).first()
            if item:
                item.is_ignored_by_user = is_ignored
                session.commit()