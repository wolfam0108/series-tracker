# Файл: kinozal_parser.py

import re
import os
from typing import Dict, Optional, List
from bs4 import BeautifulSoup
import requests
from datetime import datetime, timedelta, timezone
from auth import AuthManager
from db import Database
from logger import Logger
import time
from requests.exceptions import RequestException, Timeout
from flask import current_app as app
from urllib.parse import urlparse
import hashlib

def generate_kinozal_torrent_id(link, date_time):
    """Вспомогательная функция для генерации ID, чтобы избежать дублирования."""
    unique_string = f"{link}{date_time or ''}"
    return hashlib.md5(unique_string.encode()).hexdigest()[:16]

class KinozalParser:
    MAX_RETRIES = 3 
    RETRY_DELAY = 2 

    def __init__(self, auth_manager: AuthManager, db: Database, logger: Logger):
        self.auth_manager = auth_manager
        self.db = db
        self.logger = logger

    def _normalize_date(self, date_str: str) -> Optional[str]:
        # Устанавливаем часовой пояс Москвы (UTC+3)
        moscow_tz = timezone(timedelta(hours=3))
        # Получаем текущее время с учетом этого часового пояса
        current_date = datetime.now(moscow_tz)
        
        month_map = {
            'января': '01', 'февраля': '02', 'марта': '03', 'апреля': '04',
            'мая': '05', 'июня': '06', 'июля': '07', 'августа': '08',
            'сентября': '09', 'октября': '10', 'ноября': '11', 'декабря': '12'
        }

        date_str = date_str.strip().lower()
        try:
            if 'сегодня' in date_str:
                time_str = date_str.split('в ')[1].strip()
                return current_date.strftime('%d.%m.%Y') + f' {time_str}:00'
            elif 'вчера' in date_str:
                time_str = date_str.split('в ')[1].strip()
                yesterday = current_date - timedelta(days=1)
                return yesterday.strftime('%d.%m.%Y') + f' {time_str}:00'
            else:
                date_parts = date_str.split(' в ')
                date_part = date_parts[0].strip()
                time_part = date_parts[1].strip()
                day, month_name, year = date_part.split()
                month = month_map.get(month_name, '01')
                return f"{day.zfill(2)}.{month}.{year} {time_part}:00"
        except (IndexError, ValueError) as e:
            self.logger.error("kinozal_parser", f"Ошибка нормализации даты '{date_str}': {str(e)}")
            return None

    def _save_html_dump(self, html_content: str):
        """Сохраняет HTML-дамп страницы для отладки."""
        try:
            DUMP_DIR = "parser_dumps"
            if not os.path.exists(DUMP_DIR):
                os.makedirs(DUMP_DIR)
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            filename = os.path.join(DUMP_DIR, f"kinozal_parser_{timestamp}.html")
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(html_content)
            self.logger.info("kinozal_parser", f"HTML-дамп сохранен в файл: {filename}")
        except Exception as e:
            self.logger.error(f"kinozal_parser", f"Не удалось сохранить HTML-дамп: {e}", exc_info=True)

    def parse_series(self, url: str, last_known_torrents: Optional[List[Dict]] = None, debug_force_replace: bool = False) -> Dict:
        self.logger.info("kinozal_parser", f"Начало парсинга {url}")
        
        credentials = self.db.get_auth("kinozal")
        if not credentials or not credentials.get('username'):
            error_msg = "Учетные данные для kinozal не найдены в базе данных."
            self.logger.error("kinozal_parser", error_msg)
            return {"source": "kinozal.me", "title": {"ru": None, "en": None}, "torrents": [], "error": error_msg}

        session = requests.Session()
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        login_url = f"{base_url}/takelogin.php"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9',
            'Connection': 'keep-alive',
            'Referer': base_url + '/' 
        }

        try:
            login_response = session.post(
                login_url,
                data={"username": credentials["username"], "password": credentials["password"], "returnto": ""},
                headers=headers,
                timeout=15
            )
            login_response.raise_for_status()
            if "takelogin.php" in login_response.url:
                error_msg = f"Не удалось авторизоваться на {base_url}. Проверьте логин и пароль."
                self.logger.error("kinozal_parser", error_msg)
                return {"source": "kinozal.me", "title": {"ru": None, "en": None}, "torrents": [], "error": error_msg}
            self.logger.info("kinozal_parser", f"Успешная авторизация на {base_url}")
        except RequestException as e:
            error_msg = f"Ошибка сети при авторизации на {base_url}: {e}"
            self.logger.error("kinozal_parser", error_msg)
            return {"source": "kinozal.me", "title": {"ru": None, "en": None}, "torrents": [], "error": error_msg}

        for attempt in range(self.MAX_RETRIES):
            try:
                if app.debug_manager.is_debug_enabled('kinozal_parser'):
                    self.logger.debug("kinozal_parser", f"Отправка запроса на {url} (попытка {attempt + 1}/{self.MAX_RETRIES})")
                response = session.get(url, headers=headers, timeout=15)
                response.raise_for_status()
                self.logger.info("kinozal_parser", f"Страница {url} успешно загружена (попытка {attempt + 1}).")
                
                html_content = response.content.decode('windows-1251', errors='replace')
                
                if app.debug_manager.is_debug_enabled('save_html_kinozal'):
                    self._save_html_dump(html_content)
                
                if app.debug_manager.is_debug_enabled('kinozal_parser'):
                    self.logger.debug("kinozal_parser", "Начало парсинга HTML")
                soup = BeautifulSoup(html_content, 'lxml') 

                title_tag = soup.find('title')
                title_text = title_tag.text.strip() if title_tag else None
                title_ru = None
                if title_text:
                    title_ru = re.sub(r'\s*::\s*Кинозал\.(ТВ|МЕ)$', '', title_text, flags=re.IGNORECASE).strip()
                
                if app.debug_manager.is_debug_enabled('kinozal_parser'):
                    self.logger.debug("kinozal_parser", f"Найдено название: ru='{title_ru}'")

                date_text = None
                for key_word in ['Обновлен', 'Залит']:
                    li_tag = soup.find(lambda tag: tag.name == 'li' and len(tag.contents) > 0 and key_word in tag.contents[0])
                    if li_tag:
                        date_span = li_tag.find('span', class_='floatright')
                        if date_span:
                            date_str = date_span.get_text(strip=True)
                            date_text = self._normalize_date(date_str)
                            break
                
                if not date_text:
                    banner_tag = soup.find('div', class_='bx1 justify', text=re.compile(r'Торрент-файл обновлен'))
                    if banner_tag:
                        full_text = banner_tag.get_text(strip=True)
                        match = re.search(r'Торрент-файл обновлен\s+(.*?)\s*Чтобы', full_text)
                        if match:
                            date_str = match.group(1)
                            date_text = self._normalize_date(date_str)

                if date_text:
                    self.logger.info(f"Найдена и обработана дата: {date_text}")
                else:
                    self.logger.warning("kinozal_parser", "Не удалось найти дату ни одним из методов.")
                    raise ValueError("Дата обновления торрента не найдена на странице")

                last_known_date = last_known_torrents[0].get('date_time') if last_known_torrents else None
                
                if last_known_date and last_known_date == date_text and not debug_force_replace:
                    self.logger.info("kinozal_parser", "Дата на сайте совпадает с известной. Обновление не требуется.")
                    return {
                        "source": "kinozal.me",
                        "title": {"ru": title_ru, "en": None},
                        "torrents": [{"date_time": date_text, "link": None}] 
                    }

                torrent_link = None
                torrent_link_tag = soup.find('a', href=lambda href: href and 'download.php?id=' in href)
                if torrent_link_tag:
                    href = torrent_link_tag['href']
                    match = re.search(r'(download\.php\?id=\d+)', href)
                    href = match.group(1) if match else href.lstrip('/')
                    
                    download_domain = f"dl.{parsed_url.netloc}"
                    torrent_link = f"{parsed_url.scheme}://{download_domain}/{href}"

                    if app.debug_manager.is_debug_enabled('kinozal_parser'):
                        self.logger.debug("kinozal_parser", f"Найдена ссылка на скачивание: {torrent_link}")
                else:
                    self.logger.error("kinozal_parser", "Ссылка на торрент не найдена")

                torrents = []
                if torrent_link and date_text:
                    torrents.append({
                        "link": torrent_link, 
                        "date_time": date_text, 
                        "quality": None, 
                        "episodes": None 
                    })

                return {
                    "source": "kinozal.me",
                    "title": {"ru": title_ru, "en": None},
                    "torrents": torrents
                }

            except (Timeout, RequestException, UnicodeDecodeError, ValueError) as e:
                self.logger.warning("kinozal_parser", f"Ошибка при обработке {url} (попытка {attempt + 1}/{self.MAX_RETRIES}): {e}")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
                else:
                    return {"source": "kinozal.me", "title": {"ru": None, "en": None}, "torrents": [], "error": str(e)}
            except Exception as e:
                self.logger.error("kinozal_parser", f"Непредвиденная ошибка парсинга {url} (попытка {attempt + 1}/{self.MAX_RETRIES}): {e}", exc_info=True)
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
        
        self.logger.error("kinozal_parser", f"Не удалось получить или распарсить страницу {url} после {self.MAX_RETRIES} попыток.")
        return {"source": "kinozal.me", "title": {"ru": None, "en": None}, "torrents": [], "error": f"Не удалось подключиться к сайту после {self.MAX_RETRIES} попыток."}