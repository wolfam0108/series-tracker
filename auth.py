from typing import Optional, Dict
import requests
import cloudscraper 
from db import Database
from logger import Logger
from dataclasses import dataclass
from flask import current_app as app
from urllib.parse import urlparse

@dataclass
class AuthCredentials:
    username: str
    password: str
    url: Optional[str] = None

class AuthManager:
    DEBUG = True

    def __init__(self, db: Database, logger: Logger):
        self.db = db
        self.logger = logger
        # --- ИЗМЕНЕНИЕ: Заменяем одиночную сессию на словарь для поддержки нескольких доменов ---
        self.kinozal_sessions: Dict[str, requests.Session] = {}
        # ------------------------------------------------------------------------------------
        self.qb_session: Optional[requests.Session] = None
        self.qb_sid: Optional[str] = None
        self.scraper: Optional[cloudscraper.CloudScraper] = None

    def get_kinozal_session(self, url: str) -> Optional[requests.Session]:
        """
        Получает или создает валидную сессию для указанного URL Kinozal.
        Сессии кэшируются по домену (kinozal.me, kinozal.tv).
        """
        try:
            parsed_url = urlparse(url)
            # Нормализуем домен, убирая 'dl.' для авторизации
            domain = parsed_url.netloc.replace('dl.', '')
            base_url = f"{parsed_url.scheme}://{domain}"
        except Exception as e:
            self.logger.error("auth", f"Не удалось распарсить URL '{url}' для получения сессии: {e}")
            return None

        # Проверяем, есть ли уже рабочая сессия в кэше
        if domain in self.kinozal_sessions:
            return self.kinozal_sessions[domain]

        # Если сессии нет, проходим аутентификацию
        self.logger.info("auth", f"Создание новой сессии для домена {domain}")
        credentials = self.db.get_auth("kinozal")
        if not credentials:
            self.logger.error("auth", "Учетные данные для kinozal не найдены")
            return None

        try:
            session = requests.Session()
            login_url = f"{base_url}/takelogin.php"
            
            response = session.post(
                login_url,
                data={"username": credentials["username"], "password": credentials["password"], "returnto": ""},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10
            )
            response.raise_for_status()

            if "takelogin.php" in response.url:
                self.logger.error("auth", f"Не удалось авторизоваться на {domain}. Проверьте логин/пароль.")
                return None
            
            self.logger.info("auth", f"Успешная авторизация на {domain} для скачивания.")
            self.kinozal_sessions[domain] = session  # Кэшируем новую сессию
            return session

        except requests.RequestException as e:
            self.logger.error("auth", f"Ошибка авторизации на {domain}: {str(e)}", exc_info=e)
            return None

    def get_scraper(self) -> cloudscraper.CloudScraper:
        if self.scraper is None:
            if app.debug_manager.is_debug_enabled('auth'):
                self.logger.debug("auth", "Создание нового экземпляра CloudScraper")
            self.scraper = cloudscraper.create_scraper()
        return self.scraper

    def authenticate(self, auth_type: str) -> Dict:
        credentials = self.db.get_auth(auth_type)
        if not credentials:
            self.logger.error("auth", f"Учетные данные для {auth_type} не найдены")
            return {"error": f"Учетные данные для {auth_type} не найдены"}

        creds = AuthCredentials(
            username=credentials["username"],
            password=credentials["password"],
            url=credentials.get("url")
        )
        
        # --- ИЗМЕНЕНИЕ: Логика для kinozal вынесена в get_kinozal_session ---
        if auth_type == "kinozal":
            # Этот метод больше не должен использоваться для получения сессии kinozal,
            # но мы оставим его для возможной проверки учетных данных в будущем.
            # Для реальной работы теперь используется get_kinozal_session(url).
            return {"success": True, "message": "Для получения сессии используйте get_kinozal_session(url)"}

        elif auth_type == "qbittorrent":
            try:
                saved_sid = self.db.get_setting("qbittorrent_sid")
                if saved_sid and not self.qb_session:
                    self.qb_session = requests.Session()
                    self.qb_session.cookies.set("SID", saved_sid, domain=self._parse_domain(creds.url))
                    if app.debug_manager.is_debug_enabled('auth'):
                        self.logger.debug("auth", "Попытка использовать существующий SID для qBittorrent")
                    response = self.qb_session.get(f"{creds.url}/api/v2/app/version")
                    if response.status_code == 200:
                        self.logger.info("auth", "Использован существующий SID для qBittorrent")
                        return {"success": True, "session": self.qb_session}

                self.qb_session = requests.Session()
                if app.debug_manager.is_debug_enabled('auth'):
                    self.logger.debug("auth", "Инициализация новой сессии для qBittorrent")
                response = self.qb_session.post(f"{creds.url}/api/v2/auth/login", data={
                    "username": creds.username,
                    "password": creds.password
                })
                if response.status_code == 200 and response.text == "Ok.":
                    self.qb_sid = response.cookies.get("SID")
                    if self.qb_sid:
                        self.db.set_setting("qbittorrent_sid", self.qb_sid)
                        self.logger.info("auth", "Успешная авторизация qBittorrent")
                        return {"success": True, "session": self.qb_session}
                    self.logger.error("auth", "SID не получен от qBittorrent")
                    return {"error": "Не удалось авторизоваться в qBittorrent"}
                self.logger.error("auth", "Не удалось авторизоваться в qBittorrent")
                return {"error": "Не удалось авторизоваться в qBittorrent"}
            except requests.RequestException as e:
                self.logger.error("auth", f"Ошибка авторизации qBittorrent: {str(e)}", exc_info=e)
                return {"error": "Не удалось подключиться к qBittorrent"}

        self.logger.error("auth", f"Неизвестный тип авторизации: {auth_type}")
        return {"error": f"Неизвестный тип авторизации: {auth_type}"}

    def get_credentials(self, auth_type: str) -> Optional[AuthCredentials]:
        creds = self.db.get_auth(auth_type)
        if creds:
            if app.debug_manager.is_debug_enabled('auth'):
                self.logger.debug("auth", f"Получены учетные данные для {auth_type}")
            return AuthCredentials(**creds)
        self.logger.error("auth", f"Учетные данные для {auth_type} не найдены")
        return None

    def _parse_domain(self, url: str) -> str:
        from urllib.parse import urlparse
        if app.debug_manager.is_debug_enabled('auth'):
            self.logger.debug("auth", f"Извлечение домена из URL: {url}")
        return urlparse(url).hostname