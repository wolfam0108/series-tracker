import requests
from urllib.parse import urlparse
from datetime import datetime
from typing import List, Dict

class VKScraper:
    API_VERSION = '5.199'
    BASE_URL = 'https://api.vk.com/method/'

    def __init__(self, db, logger):
        self.db = db
        self.logger = logger
        self.access_token = self._get_token()

    def _get_token(self) -> str | None:
        vk_auth = self.db.get_auth('vk')
        token = vk_auth.get('password') if vk_auth else None
        if not token:
            self.logger.error("vk_scraper", "Access Token для VK не найден в настройках авторизации.")
        return token

    def _get_owner_id(self, screen_name: str) -> int | None:
        if not self.access_token: return None

        self.logger.info("vk_scraper", f"Определяю ID для канала '{screen_name}'...")
        params = {
            'screen_name': screen_name,
            'access_token': self.access_token,
            'v': self.API_VERSION
        }
        try:
            response = requests.get(f"{self.BASE_URL}utils.resolveScreenName", params=params).json()
            if 'error' in response:
                self.logger.error(f"vk_scraper", f"Ошибка API: {response['error']['error_msg']}")
                return None
            
            object_id = response['response']['object_id']
            obj_type = response['response']['type']
            
            owner_id = -object_id if obj_type == 'group' else object_id
            self.logger.info("vk_scraper", f"ID канала: {owner_id}")
            return owner_id
        except requests.exceptions.RequestException as e:
            self.logger.error(f"vk_scraper", f"Сетевая ошибка: {e}")
            return None

    def _search_videos_on_channel(self, owner_id: int, query: str) -> list:
        if not self.access_token: return []
        
        all_videos = []
        offset = 0
        count = 200

        self.logger.info("vk_scraper", f"Выполняю поиск по запросу '{query}' на канале {owner_id}...")
        
        while True:
            params = {
                'owner_id': owner_id,
                'q': query,
                'count': count,
                'offset': offset,
                'access_token': self.access_token,
                'v': self.API_VERSION
            }
            try:
                response = requests.get(f"{self.BASE_URL}video.search", params=params).json()
                if 'error' in response:
                    self.logger.error(f"vk_scraper", f"Ошибка API: {response['error']['error_msg']}")
                    break

                items = response.get('response', {}).get('items', [])
                if not items:
                    break
                
                all_videos.extend(items)
                if len(items) < count:
                    break
                offset += count
                
            except requests.exceptions.RequestException as e:
                self.logger.error(f"vk_scraper", f"Сетевая ошибка: {e}")
                break
                
        return all_videos

    async def scrape_titles_and_dates(self, channel_url: str, query: str) -> List[Dict[str, str]]:
        if not self.access_token:
            raise ValueError("Токен доступа VK не настроен.")
            
        try:
            parsed_url = urlparse(channel_url)
            screen_name = parsed_url.path.strip('/').split('/')[-1]
            if screen_name.startswith('@'):
                screen_name = screen_name[1:]
        except Exception as e:
            self.logger.error("vk_scraper", f"Не удалось распарсить URL канала '{channel_url}': {e}")
            raise ValueError("Неверный формат URL канала.")

        owner_id = self._get_owner_id(screen_name)
        if not owner_id:
            raise ValueError(f"Не удалось определить ID для канала '{screen_name}'.")

        videos = self._search_videos_on_channel(owner_id, query)
        
        results = []
        for video in videos:
            creation_date = "Неизвестно"
            if 'date' in video:
                unix_timestamp = video['date']
                creation_date = datetime.utcfromtimestamp(unix_timestamp).strftime('%d.%m.%Y')
            
            results.append({
                "title": video.get('title', 'Без названия'),
                "date": creation_date
            })
            
        self.logger.info("vk_scraper", f"Найдено {len(results)} видео.")
        return results