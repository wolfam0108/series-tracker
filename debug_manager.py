import time
from threading import Lock
from typing import Dict

class DebugManager:
    """
    Централизованно управляет флагами отладки для разных модулей.
    Кэширует настройки из БД для высокой производительности.
    """
    def __init__(self, db, cache_ttl_seconds: int = 60):
        self.db = db
        self.cache_ttl = cache_ttl_seconds
        self._cache: Dict[str, bool] = {}
        self._last_cache_update: float = 0
        self._lock = Lock()
        self._refresh_cache() # Первоначальная загрузка

    def _refresh_cache(self):
        """Обновляет кэш флагов из базы данных, если он устарел."""
        with self._lock:
            now = time.time()
            if now - self._last_cache_update > self.cache_ttl:
                try:
                    # Предполагаем, что в db.py будет метод get_settings_by_prefix
                    raw_flags = self.db.get_settings_by_prefix('debug_enabled_')
                    self._cache = {
                        key.replace('debug_enabled_', ''): value == 'true'
                        for key, value in raw_flags.items()
                    }
                    self._last_cache_update = now
                except Exception:
                    # В случае недоступности БД при старте или другой ошибки,
                    # работаем со старым кэшем или пустым, если это первый запуск.
                    pass

    def is_debug_enabled(self, module_name: str) -> bool:
        """
        Проверяет, включена ли отладка для указанного модуля.
        Использует кэшированные данные.
        """
        # Проверка на TTL происходит внутри _refresh_cache
        self._refresh_cache()
        return self._cache.get(module_name, False)