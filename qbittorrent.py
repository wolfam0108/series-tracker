import requests
import time
import uuid
from typing import Dict, List, Optional, Tuple
from flask import current_app as app

from requests.exceptions import Timeout
from db import Database
from logger import Logger
from auth import AuthManager

class QBittorrentClient:
    def __init__(self, auth_manager: AuthManager, db: Database, logger: Logger):
        self.auth_manager = auth_manager
        self.db = db
        self.logger = logger
        self.session = None
        self.base_url = None
        self.MAX_RETRIES = 5
        self.RETRY_DELAY = 2

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
                # --- ИЗМЕНЕНИЕ: Добавляем фильтрацию для "шумных" эндпоинтов ---
                is_polling_endpoint = 'sync/maindata' in endpoint or 'torrents/info' in endpoint
                if app.debug_manager.is_debug_enabled('qbittorrent') and not is_polling_endpoint:
                    self.logger.debug("qbittorrent", f"Запрос {method.upper()} к {url} (попытка {attempt + 1})")
                
                response = self.session.request(method, url, timeout=request_timeout, **kwargs)
                if response.status_code == 403:
                    self.logger.warning("qbittorrent", "Получен статус 403 (Forbidden). Попытка повторной аутентификации.")
                    self.session = None
                    if not self._ensure_authenticated(): return None
                    continue
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

    def add_torrent(self, link: str, save_path: str, torrent_id: str, tag: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        self.logger.info("qbittorrent", f"Добавление торрента ID: {torrent_id} в qBittorrent.")
        
        final_tag = tag if tag else str(uuid.uuid4())
        
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
            if app.debug_manager.is_debug_enabled('qbittorrent'):
                self.logger.debug("qbittorrent", f"Скачивание .torrent файла для {torrent_id}.")
            link_type = 'file'
            try:
                # --- ИЗМЕНЕНИЕ: Передаем URL в get_kinozal_session для правильной авторизации ---
                if 'kinozal' in link:
                    session = self.auth_manager.get_kinozal_session(link)
                # --- КОНЕЦ ИЗМЕНЕНИЯ ---
                elif 'astar' in link:
                    session = self.auth_manager.get_scraper()
                else:
                    session = requests.Session()
                
                if not session:
                    raise Exception("Не удалось получить сессию для скачивания .torrent файла.")

                response = session.get(link, timeout=20)
                response.raise_for_status()
                files_payload = {'torrents': ('file.torrent', response.content)}
                if app.debug_manager.is_debug_enabled('qbittorrent'):
                    self.logger.debug("qbittorrent", f"Файл для {torrent_id} успешно скачан.")
            except Exception as e:
                self.logger.error("qbittorrent", f"Не удалось скачать .torrent файл {link}: {e}", exc_info=True)
                return None, None
        
        if files_payload:
            add_params['files'] = files_payload

        response = self._request_with_retries("post", "api/v2/torrents/add", **add_params)
        
        if response and response.status_code == 200 and "Ok." in response.text:
            qb_hash = self._get_torrent_hash_by_tag(final_tag, retries=15, delay=2)
            if qb_hash:
                self.logger.info("qbittorrent", f"Торрент {torrent_id} успешно добавлен на паузе, qb_hash: {qb_hash}")
                self._remove_tag(final_tag, qb_hash)
                return qb_hash, link_type
        
        self.logger.error("qbittorrent", f"Не удалось добавить торрент {torrent_id} в qBittorrent. Ответ: {response.text if response else 'No response'}")
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