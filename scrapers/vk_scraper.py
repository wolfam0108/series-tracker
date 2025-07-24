import requests
from urllib.parse import urlparse
from datetime import datetime
from typing import List, Dict, Any

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
            if response.get('response') and isinstance(response.get('response'), dict):
                object_id = response['response']['object_id']
                obj_type = response['response']['type']
                owner_id = -object_id if obj_type == 'group' else object_id
                self.logger.info("vk_scraper", f"ID канала: {owner_id}")
                return owner_id
            else:
                self.logger.error(f"vk_scraper", f"Неожиданный формат ответа от API VK для screen_name '{screen_name}': {response}")
                return None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"vk_scraper", f"Сетевая ошибка: {e}")
            return None

    def _execute_vk_paginated_request(self, method: str, params: dict) -> list:
        """Универсальный метод для выполнения запросов к VK API с пагинацией."""
        all_items = []
        offset = 0
        count = 200

        while True:
            params['offset'] = offset
            params['count'] = count
            
            try:
                response = requests.get(f"{self.BASE_URL}{method}", params=params).json()
                if 'error' in response:
                    self.logger.error(f"vk_scraper", f"Ошибка API ({method}): {response['error']['error_msg']}")
                    break

                items = response.get('response', {}).get('items', [])
                if not items:
                    break
                
                all_items.extend(items)
                self.logger.info("vk_scraper", f"  ...загружено {len(all_items)} видео...")
                offset += count
                
            except requests.exceptions.RequestException as e:
                self.logger.error(f"vk_scraper", f"Сетевая ошибка при вызове {method}: {e}")
                break
        
        return all_items

    def scrape_video_data(self, channel_url: str, query: str, search_mode: str = 'search') -> List[Dict[str, Any]]:
        if not self.access_token:
            raise ValueError("Токен доступа VK не настроен.")
            
        try:
            parsed_url = urlparse(channel_url)
            path_parts = parsed_url.path.strip('/').split('/')
            screen_name_part = next((part for part in path_parts if part.startswith('@')), None)
            if not screen_name_part:
                raise ValueError("Не удалось найти имя канала (должно начинаться с @) в URL.")
            screen_name = screen_name_part[1:]
        except Exception as e:
            self.logger.error("vk_scraper", f"Не удалось распарсить URL канала '{channel_url}': {e}")
            raise ValueError("Неверный формат URL канала.")

        owner_id = self._get_owner_id(screen_name)
        if not owner_id:
            raise ValueError(f"Не удалось определить ID для канала '{screen_name}'.")

        base_params = {
            'owner_id': owner_id,
            'access_token': self.access_token,
            'v': self.API_VERSION,
            # --- ИЗМЕНЕНИЕ: Запрашиваем поле с файлами для определения качества ---
            'fields': 'files'
        }
        
        query_terms = [q.strip() for q in query.split('/') if q.strip()]
        
        videos = []
        if search_mode == 'search':
            self.logger.info("vk_scraper", f"Режим: ПОИСК (video.search). Запросы: {query_terms}")
            if not query_terms:
                return []
            
            all_found_videos = []
            for term in query_terms:
                search_params = base_params.copy()
                search_params['q'] = term
                self.logger.info("vk_scraper", f"Выполняю поиск по запросу: '{term}'...")
                all_found_videos.extend(self._execute_vk_paginated_request('video.search', search_params))
            
            seen_ids = set()
            for video in all_found_videos:
                if video.get('id') not in seen_ids:
                    videos.append(video)
                    seen_ids.add(video.get('id'))

        else: # search_mode == 'get_all'
            self.logger.info("vk_scraper", f"Режим: ПОЛНОЕ СКАНИРОВАНИЕ (video.get). Фильтры: {query_terms}")
            all_channel_videos = self._execute_vk_paginated_request('video.get', base_params)
            
            if not query_terms:
                videos = all_channel_videos
            else:
                self.logger.info(f"Всего получено {len(all_channel_videos)} видео. Начинаю локальный поиск...")
                for video in all_channel_videos:
                    title = video.get('title', '').lower()
                    if any(term.lower() in title for term in query_terms):
                        videos.append(video)
        
        results = []
        for video in videos:
            # --- ИЗМЕНЕНИЕ: Извлекаем максимальное разрешение ---
            max_resolution = 0
            if 'files' in video and isinstance(video['files'], dict):
                for key in video['files']:
                    if key.startswith('mp4_'):
                        try:
                            resolution = int(key.split('_')[1])
                            if resolution > max_resolution:
                                max_resolution = resolution
                        except (ValueError, IndexError):
                            continue
            # --- КОНЕЦ ИЗМЕНЕНИЯ ---

            video_id = video.get('id')
            video_owner_id = video.get('owner_id')
            video_url = f"https://vk.com/video{video_owner_id}_{video_id}"
            
            unix_timestamp = video.get('date', 0)
            publication_date = datetime.utcfromtimestamp(unix_timestamp)
            
            results.append({
                "title": video.get('title', 'Без названия'),
                "url": video_url,
                "publication_date": publication_date,
                "resolution": max_resolution if max_resolution > 0 else None
            })
            
        self.logger.info("vk_scraper", f"Найдено и отфильтровано {len(results)} видео.")
        return sorted(results, key=lambda x: x['publication_date'], reverse=True)
