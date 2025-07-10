import logging
import traceback
from logging import Handler, LogRecord
from typing import Any

# Глобальная переменная для базы данных, чтобы handler мог ее видеть
_db_instance = None

def set_db_for_logging(db):
    """Устанавливает экземпляр БД для логгера."""
    global _db_instance
    _db_instance = db

class DatabaseHandler(Handler):
    """Кастомный обработчик для записи логов в базу данных."""
    def emit(self, record: LogRecord):
        if _db_instance:
            # Форматируем сообщение, включая traceback для ошибок
            msg = self.format(record)
            
            # Извлекаем группу из record, если она была добавлена
            group = getattr(record, 'group', 'general')

            try:
                _db_instance.add_log(group, record.levelname, msg)
            except Exception as e:
                # В случае, если даже запись в БД не удалась, выводим в консоль
                print(f"!!! CRITICAL: FAILED TO LOG TO DATABASE: {e}")
                traceback.print_exc()

class Logger:
    """Обертка над стандартным логгером Python для удобства использования в приложении."""
    def __init__(self, name: str = 'app'):
        self.logger = logging.getLogger(name)
        # Устанавливаем уровень, чтобы перехватывать все сообщения от DEBUG и выше
        self.logger.setLevel(logging.DEBUG)
        
        # Убедимся, что обработчики не дублируются при многократной инициализации
        if not self.logger.handlers:
            # Обработчик для вывода в консоль
            stream_handler = logging.StreamHandler()
            stream_formatter = logging.Formatter('LOG::%(name)s::%(levelname)s::%(group)s >> %(message)s')
            stream_handler.setFormatter(stream_formatter)
            self.logger.addHandler(stream_handler)
            
            # Обработчик для записи в БД
            db_handler = DatabaseHandler()
            db_formatter = logging.Formatter('%(message)s')
            db_handler.setFormatter(db_formatter)
            self.logger.addHandler(db_handler)
            
    def _log(self, level, group, message, exc_info=None):
        """Внутренний метод для передачи группы в лог."""
        extra = {'group': group}
        self.logger.log(level, message, exc_info=exc_info, extra=extra)

    def info(self, group: str, message: str = None):
        """Логирует INFO. Если message не указан, group становится сообщением."""
        if message is None:
            message = group
            group = 'flask_internal'
        self._log(logging.INFO, group, message)

    def error(self, group: str, message: str = None, exc_info: Any = None):
        """Логирует ERROR. Если message не указан, group становится сообщением."""
        if message is None:
            message = group
            group = 'flask_internal'
        self._log(logging.ERROR, group, message, exc_info=exc_info)

    def debug(self, group: str, message: str = None):
        """Логирует DEBUG. Если message не указан, group становится сообщением."""
        if message is None:
            message = group
            group = 'flask_internal'
        self._log(logging.DEBUG, group, message)

    def warning(self, group: str, message: str = None): # <--- ДОБАВЛЕН МЕТОД WARNING
        """Логирует WARNING. Если message не указан, group становится сообщением."""
        if message is None:
            message = group
            group = 'flask_internal'
        self._log(logging.WARNING, group, message)

