import json
from urllib.parse import urlparse
from db import Database

class TrackerResolver:
    def __init__(self, db: Database):
        self.db = db
        self._cache = None

    def _get_all_trackers_with_mirrors(self):
        """Получает и кэширует список трекеров из БД."""
        if self._cache is None:
            self._cache = self.db.get_all_trackers()
        return self._cache

    def get_tracker_by_url(self, url: str) -> dict | None:
        """
        Определяет трекер по URL, проверяя список его зеркал.
        Возвращает полную информацию о трекере из БД.
        """
        try:
            # --- ИЗМЕНЕНИЕ: Добавляем .replace('dl.', '') как в AuthManager ---
            domain = urlparse(url).netloc.replace('www.', '').replace('dl.', '')
            all_trackers = self._get_all_trackers_with_mirrors()
            
            for tracker in all_trackers:
                # Зеркала уже десериализованы в get_all_trackers
                mirrors = tracker['mirrors'] if tracker['mirrors'] else []
                if domain in mirrors:
                    return tracker
            return None
        except Exception:
            return None