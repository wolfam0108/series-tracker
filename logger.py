import logging
import os
from logging.handlers import RotatingFileHandler
from pythonjsonlogger import jsonlogger
from typing import Any
from datetime import datetime

# Больше не требуется подключение к БД для логирования
_db_instance = None
def set_db_for_logging(db):
    """Эта функция больше не используется, но оставлена для обратной совместимости,
       чтобы не вызывать ошибок в run.py при запуске."""
    pass

# --- НАЧАЛО НОВОЙ ЛОГИКИ ---

# 1. Создаем директорию для логов, если ее нет
LOG_DIR = 'logs'
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# 2. Создаем фильтр, который пропускает логи только ОДНОГО конкретного уровня
class LevelFilter(logging.Filter):
    def __init__(self, level):
        super().__init__()
        self.level = level

    def filter(self, record):
        return record.levelno == self.level

# 3. Создаем кастомный JSON-форматтер для добавления нужных полей
class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        
        # --- НАЧАЛО ИЗМЕНЕНИЙ ---
        # Вместо formatTime, мы теперь вручную создаем ISO-строку из Unix-времени.
        # Это самый надежный способ.
        if record.created:
            log_record['timestamp'] = datetime.utcfromtimestamp(record.created).isoformat() + 'Z'
        # --- КОНЕЦ ИЗМЕНЕНИЙ ---
            
        log_record['level'] = record.levelname
        
        if hasattr(record, 'group'):
            log_record['group'] = record.group
            
        if 'levelname' in log_record:
            del log_record['levelname']
        if 'message' in log_record and not log_record['message']:
            log_record['message'] = record.getMessage()

class Logger:
    def __init__(self, name: str = 'app'):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        if not self.logger.handlers:
            stream_handler = logging.StreamHandler()
            stream_formatter = logging.Formatter('LOG::%(name)s::%(levelname)s::%(group)s >> %(message)s')
            stream_handler.setFormatter(stream_formatter)
            stream_handler.setLevel(logging.INFO)
            self.logger.addHandler(stream_handler)
            
            # --- ИЗМЕНЕНИЕ: Убираем datefmt, он больше не нужен ---
            json_formatter = CustomJsonFormatter(
                '%(timestamp)s %(level)s %(group)s %(message)s',
                json_ensure_ascii=False
            )

            log_levels = {
                'debug': logging.DEBUG,
                'info': logging.INFO,
                'warning': logging.WARNING,
                'error': logging.ERROR
            }

            for name, level in log_levels.items():
                handler = RotatingFileHandler(
                    os.path.join(LOG_DIR, f'{name}.log'),
                    maxBytes=10485760,
                    backupCount=5,
                    encoding='utf-8'
                )
                handler.setFormatter(json_formatter)
                handler.addFilter(LevelFilter(level))
                self.logger.addHandler(handler)
            
    def _log(self, level, group, message, exc_info=None):
        """Внутренний метод для передачи группы в лог."""
        extra = {'group': group}
        self.logger.log(level, message, exc_info=exc_info, extra=extra)

    def info(self, group: str, message: str = None):
        if message is None:
            message = group
            group = 'flask_internal'
        self._log(logging.INFO, group, message)

    def error(self, group: str, message: str = None, exc_info: Any = None):
        if message is None:
            message = group
            group = 'flask_internal'
        self._log(logging.ERROR, group, message, exc_info=exc_info)

    def debug(self, group: str, message: str = None):
        if message is None:
            message = group
            group = 'flask_internal'
        self._log(logging.DEBUG, group, message)

    def warning(self, group: str, message: str = None):
        if message is None:
            message = group
            group = 'flask_internal'
        self._log(logging.WARNING, group, message)