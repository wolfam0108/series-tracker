import time
import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from db import Database
from logger import Logger
from typing import Optional, Dict, List
from flask import current_app as app
import os
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

class AnilibriaParser:
    MAX_RETRIES = 2
    RETRY_DELAY = 5
    DUMP_DIR = "parser_dumps"
    TIMEOUT = 30000 

    def __init__(self, db: Database, logger: Logger):
        self.db = db
        self.logger = logger
        # locale больше не используется

    def _normalize_date_from_anilibria(self, date_str: str) -> Optional[str]:
        """
        Нормализует строку с датой от Anilibria (которая приходит в UTC)
        и конвертирует ее в ЛОКАЛЬНОЕ время сервера.
        """
        try:
            if app.debug_manager.is_debug_enabled('anilibria_parser_debug'):
                self.logger.debug("anilibria_parser_debug", f"RAW DATE STRING RECEIVED: '{date_str}'")

            # 1. Определяем часовые пояса: UTC и локальный часовой пояс сервера
            utc_tz = timezone.utc
            local_tz = datetime.now().astimezone().tzinfo

            # 2. Ручной разбор строки
            match = re.match(r'(\d{1,2})/(\d{1,2})/(\d{4}),?\s*(\d{1,2}):(\d{2}):(\d{2})\s*(AM|PM)', date_str, re.IGNORECASE)
            if not match:
                raise ValueError(f"Формат даты '{date_str}' не соответствует 'm/d/yyyy, h:mm:ss am/pm'")
            
            month, day, year, hour, minute, second, am_pm = match.groups()
            month, day, year, hour, minute, second = map(int, [month, day, year, hour, minute, second])

            if am_pm.upper() == 'PM' and hour < 12:
                hour += 12
            elif am_pm.upper() == 'AM' and hour == 12:
                hour = 0
                
            # 3. Создаем "наивный" объект datetime
            dt_naive = datetime(year, month, day, hour, minute, second)

            # 4. Делаем его "осведомленным", сказав, что это время в UTC
            dt_utc = dt_naive.replace(tzinfo=utc_tz)

            # 5. Конвертируем время из UTC в локальный часовой пояс сервера
            dt_local = dt_utc.astimezone(local_tz)
            
            final_str = dt_local.strftime('%d.%m.%Y %H:%M:%S')

            if app.debug_manager.is_debug_enabled('anilibria_parser_debug'):
                self.logger.debug("anilibria_parser_debug", f"PARSED UTC: {dt_utc}, CONVERTED TO LOCAL ({local_tz}): {dt_local}, FINAL STRING: '{final_str}'")

            return final_str

        except Exception as e:
            self.logger.error(f"anilibria_parser - КРИТИЧЕСКАЯ ошибка нормализации даты '{date_str}': {e}")
            return None

    def _save_html_dump(self, html_content: str):
        try:
            if not os.path.exists(self.DUMP_DIR):
                os.makedirs(self.DUMP_DIR)
            
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            filename = os.path.join(self.DUMP_DIR, f"anilibria_parser_{timestamp}.html")
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            self.logger.info("anilibria_parser", f"HTML-дамп сохранен в файл: {filename}")
        except Exception as e:
            self.logger.error(f"anilibria_parser - Не удалось сохранить HTML-дамп: {e}", exc_info=True)

    def _fetch_page_source(self, url: str) -> Optional[str]:
        # Playwright больше не нуждается в принудительной установке timezone_id
        for attempt in range(self.MAX_RETRIES):
            try:
                with sync_playwright() as p:
                    browser = p.firefox.launch(headless=True)
                    context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0')
                    page = context.new_page()
                    page.goto(url, timeout=self.TIMEOUT, wait_until="domcontentloaded")
                    
                    page.wait_for_selector('div.v-list-item', state='visible', timeout=self.TIMEOUT)
                    
                    html_content = page.content()
                    browser.close()

                    if app.debug_manager.is_debug_enabled('save_parser_html'):
                        self._save_html_dump(html_content)

                    return html_content
            except (PlaywrightTimeoutError, Exception) as e:
                self.logger.warning(f"anilibria_parser - Ошибка Playwright при запросе к {url} (попытка {attempt + 1}/{self.MAX_RETRIES}): {e}")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
        
        self.logger.error(f"anilibria_parser - Не удалось получить страницу {url} после {self.MAX_RETRIES} попыток.")
        return None

    def parse_series(self, original_url: str, last_known_torrents: Optional[List[Dict]] = None) -> Dict:
        self.logger.info("anilibria_parser", f"Начало парсинга {original_url}")

        match = re.match(r"(https://aniliberty\.top/(?:release|anime/releases/release)/[^/]+)", original_url)
        if not match:
            return {"source": "aniliberty.top", "title": {"ru": None, "en": None}, "torrents": [], "error": "Некорректный URL релиза"}
        
        base_release_url = match.group(1)
        url_to_fetch = f"{base_release_url}/torrents"

        html_content = self._fetch_page_source(url_to_fetch)
        if not html_content:
            return {"source": "aniliberty.top", "title": {"ru": None, "en": None}, "torrents": [], "error": f"Не удалось загрузить страницу {url_to_fetch}"}

        soup = BeautifulSoup(html_content, 'html.parser')

        ru_title_element = soup.find('div', class_='text-autosize')
        ru_title = ru_title_element.text.strip() if ru_title_element else "Название не найдено"
        en_title_element = soup.find('div', class_='text-grey-darken-2')
        en_title = en_title_element.text.strip() if en_title_element else "Eng title not found"
        
        torrents = []
        torrent_blocks = soup.find_all('div', class_='v-list-item')
        if not torrent_blocks:
            return {"source": urlparse(url_to_fetch).netloc, "title": {"ru": ru_title, "en": en_title}, "torrents": [], "error": "Не найдены блоки торрентов"}
        
        for index, block in enumerate(torrent_blocks):
            try:
                episodes_element = block.find('div', class_='fz-90')
                episodes = episodes_element.text.strip() if episodes_element else "N/A"
                
                magnet_link_tag = block.find('a', href=re.compile(r'^magnet:'))
                if not magnet_link_tag:
                    continue
                magnet_link = magnet_link_tag['href']
                
                info_element = block.find('div', class_='text-grey-darken-2 fz-75')
                if not info_element:
                    continue
                
                info_string = info_element.text.strip()
                parts = [p.strip() for p in info_string.split('•')]
                
                date_raw = parts[0]
                formatted_datetime = self._normalize_date_from_anilibria(date_raw)
                quality = " • ".join(parts[1:]) if len(parts) > 1 else None

                torrent_info = {
                    "episodes": episodes,
                    "date_time": formatted_datetime,
                    "quality": quality,
                    "link": magnet_link
                }
                torrents.append(torrent_info)
            except Exception as e:
                self.logger.warning(f"Пропущен один блок торрента из-за ошибки парсинга: {e}. Блок: {block.text[:150]}...")
                continue
        
        if app.debug_manager.is_debug_enabled('anilibria_parser_debug'):
            self.logger.debug("anilibria_parser_debug", f"FINAL TORRENTS PAYLOAD: {torrents}")
        
        return {
            "source": urlparse(url_to_fetch).netloc,
            "title": {"ru": ru_title, "en": en_title},
            "torrents": torrents
        }
