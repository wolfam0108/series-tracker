import requests
import time
import uuid
from typing import Dict, List, Optional, Tuple
from flask import current_app as app
from urllib.parse import urlparse
from requests.exceptions import Timeout
from db import Database
from logger import Logger
from auth import AuthManager
from file_cache import read_from_cache, save_to_cache
from utils.tracker_resolver import TrackerResolver


class QBittorrentClient:
    def __init__(self, auth_manager: AuthManager, db: Database, logger: Logger):
        self.auth_manager = auth_manager
        self.db = db
        self.logger = logger
        self.session = None
        self.base_url = None
        self.MAX_RETRIES = 5
        self.RETRY_DELAY = 2
        if app.debug_manager.is_debug_enabled('auth'):
            self.logger.debug("auth", f"[QBittorrentClient] Инициализирован с AuthManager ID: {id(self.auth_manager)}")

    def _ensure_authenticated(self) -> bool:
        if self.session:
            return True
        auth_result = self.auth_manager.authenticate("qbittorrent")
        if not auth_result.get("success"):
            self.logger.error("qbittorrent", f"Ошибка авторизации: {auth_result.get('error')}")
            return False
        self.session = auth_result["session"]
        creds = self.auth_manager.get_credentials("qbittorrent")
        self.base_url = creds.url if creds else None
        return True

    def _request_with_retries(self, method: str, endpoint: str, request_timeout: int = 20, **kwargs) -> Optional[requests.Response]:
        if not self._ensure_authenticated():
            return None
        url = f"{self.base_url}/{endpoint}"
        for attempt in range(self.MAX_RETRIES):
            try:
                is_polling_endpoint = 'sync/maindata' in endpoint or 'torrents/info' in endpoint
                if app.debug_manager.is_debug_enabled('qbittorrent') and not is_polling_endpoint:
                    self.logger.debug("qbittorrent", f"Запрос {method.upper()} к {url} (попытка {attempt + 1})")
                
                response = self.session.request(method, url, timeout=request_timeout, **kwargs)

                # Обработка 403 Forbidden (проблема с авторизацией) -> Повторяем попытку
                if response.status_code == 403:
                    self.logger.warning("qbittorrent", "Получен статус 403 (Forbidden). Попытка повторной аутентификации.")
                    self.session = None
                    if not self._ensure_authenticated(): return None
                    continue

                # --- НАЧАЛО ИЗМЕНЕНИЙ ---
                # Обработка 404 Not Found (торрент не существует) -> НЕ повторяем попытку
                if response.status_code == 404:
                    self.logger.warning("qbittorrent", f"Получен статус 404 (Not Found) от {url}. Ресурс не существует в qBittorrent.")
                    return None # Немедленно выходим с результатом None
                # --- КОНЕЦ ИЗМЕНЕНИЙ ---

                # Для всех остальных ошибок (500, 401 и т.д.) вызываем исключение и повторяем попытку
                response.raise_for_status()
                return response
            except Timeout:
                if 'sync/maindata' in endpoint:
                    if app.debug_manager.is_debug_enabled('qbittorrent'):
                        self.logger.debug("qbittorrent", f"Таймаут long-polling запроса к {url}, это ожидаемо.")
                    return None
                self.logger.warning("qbittorrent", f"Таймаут запроса к {url} (попытка {attempt + 1}/{self.MAX_RETRIES})")
            except requests.RequestException as e:
                self.logger.warning("qbittorrent", f"Ошибка запроса к {url} (попытка {attempt + 1}/{self.MAX_RETRIES}): {e}")
            
            if attempt < self.MAX_RETRIES - 1:
                time.sleep(self.RETRY_DELAY)
        
        self.logger.error("qbittorrent", f"Не удалось выполнить запрос к {url} после {self.MAX_RETRIES} попыток.")
        return None

    def add_torrent(self, link: str, save_path: str, torrent_id: str) -> Tuple[Optional[str], Optional[str]]:
        self.logger.info("qbittorrent", f"Добавление торрента ID: {torrent_id} в qBittorrent.")
        
        final_tag = torrent_id
        
        payload = {'savepath': save_path, 'tags': final_tag, 'paused': 'true'}
        add_params = {'data': payload}
        files_payload = None
        link_type = None

        if link.startswith('magnet:'):
            if app.debug_manager.is_debug_enabled('qbittorrent'):
                self.logger.debug("qbittorrent", f"Подготовка magnet-ссылки для {torrent_id}.")
            payload['urls'] = link
            link_type = 'magnet'
        else:
            link_type = 'file'
            file_content = read_from_cache(torrent_id)
            if not file_content:
                if app.debug_manager.is_debug_enabled('qbittorrent'):
                    self.logger.debug("qbittorrent", f"Файл для торрента {torrent_id} не найден в кэше. Скачивание...")
                try:
                    resolver = TrackerResolver(self.db)
                    tracker_info = resolver.get_tracker_by_url(link)
                    auth_type = tracker_info['auth_type'] if tracker_info else 'none'
                    self.logger.info("qbittorrent", f"Определен тип аутентификации для ссылки '{link}': {auth_type}")

                    if auth_type == 'kinozal':
                        session = self.auth_manager.get_kinozal_session(link)
                        if app.debug_manager.is_debug_enabled('auth') and session:
                            self.logger.debug("auth", f"[QBittorrentClient] Получена сессия ID: {id(session)} от AuthManager")
                    elif auth_type == 'astar':
                        session = self.auth_manager.get_scraper()
                    else:
                        session = requests.Session()
                    
                    if not session:
                        raise Exception("Не удалось получить сессию для скачивания .torrent файла.")

                    request_kwargs = {'timeout': 20}
                    if auth_type == 'kinozal':
                        parsed_link = urlparse(link)
                        base_domain = parsed_link.netloc.replace('dl.', '')
                        referer_url = f"{parsed_link.scheme}://{base_domain}/"
                        request_kwargs['headers'] = {'Referer': referer_url}
                        self.logger.debug("qbittorrent", f"Добавлен заголовок Referer для Kinozal: {referer_url}")

                    if app.debug_manager.is_debug_enabled('auth'):
                        self.logger.debug("auth", f"[ОТЛАДКА] Cookies ПЕРЕД СКАЧИВАНИЕМ .torrent: {session.cookies.get_dict()}")
                    
                    response = session.get(link, **request_kwargs)
                    response.raise_for_status()
                    
                    content_type = response.headers.get('Content-Type', '')
                    if 'text/html' in content_type:
                        error_reason = "Неизвестная ошибка: трекер вернул HTML страницу."
                        if "Вы использовали доступное Вам количество торрент-файлов в сутки" in response.text:
                            error_reason = "Достигнут суточный лимит скачиваний на трекере."
                        self.logger.error("qbittorrent", f"Ошибка скачивания файла {link}. Причина: {error_reason}")
                        return None, None

                    file_content = response.content
                    save_to_cache(torrent_id, file_content)

                except Exception as e:
                    self.logger.error("qbittorrent", f"Не удалось скачать .torrent файл {link}: {e}", exc_info=True)
                    return None, None
            
            files_payload = {'torrents': ('file.torrent', file_content, 'application/x-bittorrent')}
        
        if files_payload:
            add_params['files'] = files_payload

        response = self._request_with_retries("post", "api/v2/torrents/add", **add_params)
        
        # --- НАЧАЛО ИЗМЕНЕНИЯ ---
        # Если qBittorrent ответил "Fails."
        if response and response.status_code == 200 and "Fails." in response.text:
            self.logger.warning("qbittorrent", f"qBittorrent вернул 'Fails.' для торрента {torrent_id}. Проверяем, может он уже существует...")
            # Пытаемся найти хеш по временному тегу. Если найдем - значит, торрент уже был добавлен.
            qb_hash = self._get_torrent_hash_by_tag(final_tag, retries=3, delay=1)
            if qb_hash:
                self.logger.info("qbittorrent", f"Торрент {torrent_id} уже существует в qBittorrent. Используем его хеш: {qb_hash}")
                self._remove_tag(final_tag, qb_hash) # Просто удаляем тег
                return qb_hash, link_type
            else:
                # Если хеш не нашелся, то это реальная ошибка
                self.logger.error("qbittorrent", f"Не удалось добавить торрент {torrent_id} и он не найден по тегу. Ответ: {response.text}")
                return None, None

        # Если ответ успешный ("Ok.")
        if response and response.status_code == 200 and "Ok." in response.text:
            qb_hash = self._get_torrent_hash_by_tag(final_tag, retries=15, delay=2)
            if qb_hash:
                self.logger.info("qbittorrent", f"Торрент {torrent_id} успешно добавлен на паузе, qb_hash: {qb_hash}")
                self._remove_tag(final_tag, qb_hash)
                return qb_hash, link_type
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---
        
        error_text = response.text if response else 'No response'
        status_code = response.status_code if response else 'N/A'
        self.logger.error("qbittorrent", f"Не удалось добавить торрент {torrent_id} в qBittorrent. Статус: {status_code}, Ответ: {error_text}")
        return None, None


    def _get_torrent_hash_by_tag(self, tag: str, retries: int = 3, delay: int = 1) -> Optional[str]:
        for i in range(retries):
            if app.debug_manager.is_debug_enabled('qbittorrent'):
                self.logger.debug("qbittorrent", f"Попытка {i+1}/{retries} получить hash по тегу {tag}")
            response = self._request_with_retries("get", "api/v2/torrents/info", params={"tag": tag})
            if response and response.status_code == 200:
                torrents = response.json()
                if torrents:
                    return torrents[0].get('hash')
            time.sleep(delay)
        self.logger.error("qbittorrent", f"Не удалось получить hash для тега {tag} после {retries} попыток.")
        return None

    def _remove_tag(self, tag: str, qb_hash: str):
        if app.debug_manager.is_debug_enabled('qbittorrent'):
            self.logger.debug("qbittorrent", f"Удаление временного тега '{tag}' с торрента {qb_hash[:8]}")
        self._request_with_retries("post", "api/v2/torrents/removeTags", data={"hashes": qb_hash, "tags": tag})

    def get_torrents_info(self, hashes: List[str]) -> Optional[List[Dict]]:
        if not hashes: return []
        hashes_str = '|'.join(hashes)
        response = self._request_with_retries("get", "api/v2/torrents/info", params={"hashes": hashes_str})
        return response.json() if response and response.status_code == 200 else None

    def get_torrent_files_by_hash(self, torrent_hash: str) -> Optional[List[str]]:
        if not torrent_hash:
            return None
        if app.debug_manager.is_debug_enabled('qbittorrent'):
            self.logger.debug("qbittorrent", f"Запрос списка файлов для хэша: {torrent_hash}")
        response = self._request_with_retries("get", "api/v2/torrents/files", params={"hash": torrent_hash})
        if response and response.status_code == 200:
            files_data = response.json()
            file_paths = [file['name'] for file in files_data]
            if app.debug_manager.is_debug_enabled('qbittorrent'):
                self.logger.debug("qbittorrent", f"Найдено {len(file_paths)} файлов для хэша {torrent_hash}")
            return file_paths
        else:
            self.logger.error("qbittorrent", f"Не удалось получить список файлов для хэша {torrent_hash}")
            return None

    def rename_file(self, torrent_hash: str, old_path: str, new_path: str) -> bool:
        self.logger.info("qbittorrent", f"Переименование файла в торренте {torrent_hash}: '{old_path}' -> '{new_path}'")
        response = self._request_with_retries(
            "post", "api/v2/torrents/renameFile", data={"hash": torrent_hash, "oldPath": old_path, "newPath": new_path}
        )
        if response and response.status_code == 200:
            if app.debug_manager.is_debug_enabled('qbittorrent'):
                self.logger.debug("qbittorrent", "Файл успешно переименован.")
            return True
        else:
            status = response.status_code if response is not None else 'N/A'
            text = response.text if response is not None else 'No response'
            self.logger.error(f"qbittorrent", f"Ошибка переименования файла. Статус: {status}, Ответ: {text}")
            return False
            
    def sync_main_data(self, rid: int) -> Optional[Dict]:
        response = self._request_with_retries(
            "get", "api/v2/sync/maindata", 
            request_timeout=30,
            params={"rid": rid}
        )
        return response.json() if response and response.status_code == 200 else None

    def recheck_torrents(self, hashes: List[str]):
        if not hashes: return
        self.logger.info("qbittorrent", f"Запуск recheck для торрентов: {', '.join(h[:8] for h in hashes)}")
        self._request_with_retries("post", "api/v2/torrents/recheck", data={"hashes": '|'.join(hashes)})

    def resume_torrents(self, hashes: List[str]):
        if not hashes: return
        self.logger.info("qbittorrent", f"Запуск resume для торрентов: {', '.join(h[:8] for h in hashes)}")
        self._request_with_retries("post", "api/v2/torrents/resume", data={"hashes": '|'.join(hashes)})
        
    def pause_torrents(self, hashes: List[str]):
        if not hashes: return
        self.logger.info("qbittorrent", f"Постановка на паузу торрентов: {', '.join(h[:8] for h in hashes)}")
        self._request_with_retries("post", "api/v2/torrents/pause", data={"hashes": '|'.join(hashes)})

    def delete_torrents(self, hashes: List[str], delete_files: bool):
        if not hashes: return
        self.logger.info("qbittorrent", f"Удаление торрентов: {', '.join(h[:8] for h in hashes)}. Удалить файлы: {delete_files}")
        self._request_with_retries("post", "api/v2/torrents/delete", data={"hashes": '|'.join(hashes), "deleteFiles": str(delete_files).lower()})
    
    def set_location(self, torrent_hash: str, new_location: str) -> bool:
        """Изменяет путь сохранения для одного торрента."""
        self.logger.info("qbittorrent", f"Изменение пути для торрента {torrent_hash[:8]} на '{new_location}'")
        response = self._request_with_retries(
            "post", "api/v2/torrents/setLocation",
            data={"hashes": torrent_hash, "location": new_location}
        )
        if response and response.status_code == 200:
            self.logger.info("qbittorrent", "Команда на перемещение успешно отправлена.")
            return True
        else:
            status = response.status_code if response is not None else 'N/A'
            text = response.text if response is not None else 'No response'
            self.logger.error(f"qbittorrent", f"Ошибка перемещения торрента. Статус: {status}, Ответ: {text}")
            return False