from typing import Optional, Dict
import requests
import cloudscraper
import time
from bs4 import BeautifulSoup
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
        self.rutracker_sessions: Dict[str, requests.Session] = {}
        # ------------------------------------------------------------------------------------
        self.qb_session: Optional[requests.Session] = None
        self.qb_sid: Optional[str] = None
        self.scraper: Optional[cloudscraper.CloudScraper] = None

    def get_kinozal_session(self, url: str) -> Optional[requests.Session]:
        """
        Получает или создает и КЭШИРУЕТ валидную сессию для Kinozal.
        Теперь с циклом повторных попыток при авторизации.
        """
        MAX_LOGIN_RETRIES = 5
        RETRY_LOGIN_DELAY = 5

        if app.debug_manager.is_debug_enabled('auth'):
            self.logger.debug("auth", f"[get_kinozal_session] Вызван для URL {url} из AuthManager ID: {id(self)}")

        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.replace('dl.', '').replace('www.', '')
            base_url = f"{parsed_url.scheme}://{domain}"
        except Exception as e:
            self.logger.error("auth", f"Не удалось распарсить URL '{url}' для получения сессии: {e}")
            return None

        if domain in self.kinozal_sessions:
            session = self.kinozal_sessions[domain]
            if app.debug_manager.is_debug_enabled('auth'):
                self.logger.debug("auth", f"Использована кэшированная сессия ID: {id(session)} для {domain}")
            return session

        self.logger.info("auth", f"Создание новой сессии для домена {domain}")
        credentials = self.db.get_auth("kinozal")
        if not credentials: return None

        # --- НАЧАЛО ИЗМЕНЕНИЙ: Добавлен цикл повторных попыток ---
        for attempt in range(MAX_LOGIN_RETRIES):
            try:
                session = requests.Session()
                login_url = f"{base_url}/takelogin.php"
                self.logger.info("auth", f"Попытка авторизации на {domain} (попытка {attempt + 1}/{MAX_LOGIN_RETRIES})...")
                
                response = session.post(
                    login_url, 
                    data={"username": credentials["username"], "password": credentials["password"], "returnto": ""}, 
                    headers={"User-Agent": "Mozilla/5.0"}, 
                    timeout=15 # Немного увеличим таймаут для самого запроса
                )
                response.raise_for_status()
                
                if "takelogin.php" in response.url:
                    self.logger.error("auth", f"Не удалось авторизоваться на {domain}. Проверьте логин/пароль.")
                    return None # Ошибка в данных, нет смысла повторять
                
                self.logger.info("auth", f"Успешная авторизация на {domain} для скачивания.")
                if app.debug_manager.is_debug_enabled('auth'):
                    self.logger.debug("auth", f"[ОТЛАДКА] Cookies ПОСЛЕ ЛОГИНА: {session.cookies.get_dict()}")

                self.kinozal_sessions[domain] = session
                return session

            except requests.RequestException as e:
                self.logger.error("auth", f"Ошибка авторизации на {domain} (попытка {attempt + 1}): {str(e)}")
                if attempt < MAX_LOGIN_RETRIES - 1:
                    time.sleep(RETRY_LOGIN_DELAY)
                else:
                    self.logger.error("auth", f"Не удалось авторизоваться на {domain} после {MAX_LOGIN_RETRIES} попыток.")
                    return None
        # --- КОНЕЦ ИЗМЕНЕНИЙ ---
        
        return None # На всякий случай, если цикл завершится без возврата
        
    def get_rutracker_session(self, url: str) -> Optional[requests.Session]:
        """
        Получает или создает и КЭШИРУЕТ валидную сессию для RuTracker.
        """
        MAX_LOGIN_RETRIES = 5
        RETRY_LOGIN_DELAY = 5

        if app.debug_manager.is_debug_enabled('auth'):
            self.logger.debug("auth", f"[get_rutracker_session] Вызван для URL {url} из AuthManager ID: {id(self)}")

        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.replace('www.', '')
            base_url = f"{parsed_url.scheme}://{domain}"
        except Exception as e:
            self.logger.error("auth", f"Не удалось распарсить URL '{url}' для получения сессии: {e}")
            return None

        if domain in self.rutracker_sessions:
            session = self.rutracker_sessions[domain]
            if app.debug_manager.is_debug_enabled('auth'):
                self.logger.debug("auth", f"Использована кэшированная сессия ID: {id(session)} для {domain}")
            return session

        self.logger.info("auth", f"Создание новой сессии для домена {domain}")
        credentials = self.db.get_auth("rutracker")
        if not credentials: return None

        for attempt in range(MAX_LOGIN_RETRIES):
            try:
                session = requests.Session()
                # RuTracker использует другой URL для входа
                login_url = f"{base_url}/forum/login.php"
                self.logger.info("auth", f"Попытка авторизации на {domain} (попытка {attempt + 1}/{MAX_LOGIN_RETRIES})...")
                
                # Сначала получаем страницу логина, чтобы получить возможные скрытые поля
                login_page_response = session.get(login_url, timeout=15)
                login_page_soup = BeautifulSoup(login_page_response.text, 'html.parser')
                
                # Находим форму логина
                login_form = login_page_soup.find('form', {'method': 'post'})
                form_data = {}
                
                # Собираем все поля из формы (не только скрытые, но и другие тоже могут быть важны)
                if login_form:
                    for input_field in login_form.find_all('input'):
                        field_type = input_field.get('type', 'text').lower()
                        field_name = input_field.get('name')
                        field_value = input_field.get('value', '')
                        
                        # Собираем все поля, кроме тех, что пользователь должен заполнить сам
                        if field_name and field_name not in ['login_username', 'login_password']:
                            form_data[field_name] = field_value
                
                # Добавляем учетные данные
                form_data["login_username"] = credentials["username"]
                form_data["login_password"] = credentials["password"]
                
                # Проверяем, есть ли поле 'login' или ему подобное, и если нет, добавляем
                if "login" not in form_data:
                    form_data["login"] = "Вход"

                response = session.post(
                    login_url,
                    data=form_data,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                        "Referer": login_url,
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                        "Accept-Encoding": "gzip, deflate, br",
                        "Connection": "keep-alive",
                        "Upgrade-Insecure-Requests": "1"
                    },
                    timeout=15
                )
                response.raise_for_status()
                
                # Проверяем успешность авторизации
                # Проверяем, есть ли на странице элементы, указывающие на успешный вход
                success_indicators = ["logout", "выход", "привет", "добро пожаловать", "profile", "user", "personal"]
                is_success = any(indicator in response.text.lower() for indicator in success_indicators)
                
                if is_success:
                    self.logger.info("auth", f"Успешная авторизация на {domain} для скачивания.")
                    if app.debug_manager.is_debug_enabled('auth'):
                        self.logger.debug("auth", f"[ОТЛАДКА] Cookies ПОСЛЕ ЛОГИНА: {session.cookies.get_dict()}")
                else:
                    # Проверяем, остались ли мы на странице логина или есть сообщения об ошибке
                    error_indicators = ["login.php", "login", "error", "ошибк", "неверный", "пароль", "требуется"]
                    is_error = any(indicator in response.url.lower() or indicator in response.text.lower() for indicator in error_indicators)
                    
                    if is_error:
                        self.logger.error("auth", f"Не удалось авторизоваться на {domain}. Проверьте логин/пароль.")
                        return None  # Ошибка в данных, нет смысла повторять
                    else:
                        # Возможно, авторизация прошла успешно, но нужно проверить другой признак
                        self.logger.info("auth", f"Возможно, успешная авторизация на {domain} (проверка по другим признакам).")
               
                self.rutracker_sessions[domain] = session
                return session

            except requests.RequestException as e:
                self.logger.error("auth", f"Ошибка авторизации на {domain} (попытка {attempt + 1}): {str(e)}")
                if attempt < MAX_LOGIN_RETRIES - 1:
                    time.sleep(RETRY_LOGIN_DELAY)
                else:
                    self.logger.error("auth", f"Не удалось авторизоваться на {domain} после {MAX_LOGIN_RETRIES} попыток.")
                    return None
        
        return None  # На всякий случай, если цикл завершится без возврата
        
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
            
        elif auth_type == "rutracker":
            # Для RuTracker используем get_rutracker_session(url)
            return {"success": True, "message": "Для получения сессии используйте get_rutracker_session(url)"}

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