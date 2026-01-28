import requests
import time
from typing import Optional, Dict, List, Any
from flask import current_app

class TMDBClient:
    def __init__(self, db, logger):
        self.db = db
        self.logger = logger
        self.base_url = "https://api.themoviedb.org/3"
        self._token = None

    @property
    def token(self):
        # Always fetch fresh token from settings
        token_setting = self.db.get_setting('tmdb_token')
        return token_setting if token_setting else None

    @property
    def headers(self):
        return {
            "accept": "application/json",
            "Authorization": f"Bearer {self.token}"
        }

    def search_series(self, query: str) -> List[Dict[str, Any]]:
        if not self.token:
            self.logger.warning("tmdb", "Запрос поиска без токена TMDB.")
            return []

        url = f"{self.base_url}/search/tv"
        params = {
            "query": query,
            "include_adult": "false",
            "language": "ru-RU",
            "page": "1"
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get('results', [])
        except Exception as e:
            self.logger.error("tmdb", f"Ошибка поиска TMDB: {e}")
            return []

    def get_series_details(self, tmdb_id: int) -> Optional[Dict[str, Any]]:
        if not self.token:
            return None

        url = f"{self.base_url}/tv/{tmdb_id}"
        params = {"language": "ru-RU"}
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error("tmdb", f"Ошибка получения деталей TMDB ID {tmdb_id}: {e}")
            return None

    def get_season_episode_count(self, tmdb_id: int, season_number: int) -> int:
        details = self.get_series_details(tmdb_id)
        if not details:
            return 0
        
        for season in details.get('seasons', []):
            if season.get('season_number') == season_number:
                return season.get('episode_count', 0)
        
        return 0
