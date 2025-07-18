import time
import re
import locale
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from db import Database
from logger import Logger
from typing import Optional, Dict, List
from flask import current_app as app
import os
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

class AnilibriaParser:
    MAX_RETRIES = 2
    RETRY_DELAY = 5
    DUMP_DIR = "parser_dumps"
    TIMEOUT = 30000 

    def __init__(self, db: Database, logger: Logger):
        self.db = db
        self.logger = logger
        try:
            locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
        except locale.Error:
            self.logger.warning("anilibria_parser", "Предупреждение: не удалось установить локаль en_US.UTF-8. Парсинг даты может не сработать на вашей системе.")

    def _normalize_date_from_anilibria(self, date_str: str) -> Optional[str]:
        try:
            date_str_cleaned = date_str.replace(',', '')
            parsed_datetime = datetime.strptime(date_str_cleaned, '%m/%d/%Y %I:%M:%S %p')
            return parsed_datetime.strftime('%d.%m.%Y %H:%M:%S')
        except ValueError as e:
            self.logger.error(f"anilibria_parser - Ошибка нормализации даты Anilibria '{date_str}': {str(e)}")
            return None

    def _save_html_dump(self, html_content: str):
        try:
            if not os.path.exists(self.DUMP_DIR):
                os.makedirs(self.DUMP_DIR)
                self.logger.info("anilibria_parser", f"Создана директория для дампов: {self.DUMP_DIR}")
            
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            filename = os.path.join(self.DUMP_DIR, f"anilibria_parser_{timestamp}.html")
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            self.logger.info("anilibria_parser", f"HTML-дамп сохранен в файл: {filename}")
        except Exception as e:
            self.logger.error(f"anilibria_parser - Не удалось сохранить HTML-дамп: {e}", exc_info=True)

    def _fetch_page_source(self, url: str) -> Optional[str]:
        if app.debug_manager.is_debug_enabled('anilibria_parser'):
            self.logger.debug("anilibria_parser", f"Запрос страницы с помощью Playwright: {url}")
        
        for attempt in range(self.MAX_RETRIES):
            try:
                with sync_playwright() as p:
                    browser = p.firefox.launch(headless=True)
                    context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0')
                    page = context.new_page()
                    page.goto(url, timeout=self.TIMEOUT, wait_until="domcontentloaded")
                    
                    self.logger.info("anilibria_parser", "Ожидание отрисовки контента страницы...")
                    page.wait_for_selector('div.v-list-item', state='visible', timeout=self.TIMEOUT)
                    self.logger.info("anilibria_parser", "Контент отрисован.")
                    
                    html_content = page.content()
                    browser.close()

                    self.logger.info(f"anilibria_parser - Страница {url} успешно загружена и отрисована (попытка {attempt + 1}).")

                    if app.debug_manager.is_debug_enabled('save_parser_html'):
                        self._save_html_dump(html_content)

                    return html_content
            except PlaywrightTimeoutError:
                self.logger.warning(f"anilibria_parser - Ошибка таймаута Playwright при запросе к {url} (попытка {attempt + 1}/{self.MAX_RETRIES}).")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
            except Exception as e:
                self.logger.warning(f"anilibria_parser - Ошибка Playwright при запросе к {url} (попытка {attempt + 1}/{self.MAX_RETRIES}): {e}")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
        
        self.logger.error(f"anilibria_parser - Не удалось получить страницу {url} после {self.MAX_RETRIES} попыток.")
        return None

    def parse_series(self, original_url: str, last_known_torrents: Optional[List[Dict]] = None) -> Dict:
        self.logger.info("anilibria_parser", f"Начало парсинга {original_url}")

        match = re.match(r"(https://anilibria\.top/(?:release|anime/releases/release)/[^/]+)", original_url)
        if not match:
            return {"source": "anilibria.top", "title": {"ru": None, "en": None}, "torrents": [], "error": "Некорректный URL релиза"}
        
        base_release_url = match.group(1)
        url_to_fetch = f"{base_release_url}/torrents"

        html_content = self._fetch_page_source(url_to_fetch)
        if not html_content:
            return {"source": "anilibria.top", "title": {"ru": None, "en": None}, "torrents": [], "error": f"Не удалось загрузить страницу {url_to_fetch}"}

        soup = BeautifulSoup(html_content, 'html.parser')

        ru_title_element = soup.find('div', class_='text-autosize')
        ru_title = ru_title_element.text.strip() if ru_title_element else "Название не найдено"
        en_title_element = soup.find('div', class_='text-grey-darken-2')
        en_title = en_title_element.text.strip() if en_title_element else "Eng title not found"
        self.logger.info(f"Название (ru): {ru_title}")
        self.logger.info(f"Название (en): {en_title}")

        torrents = []
        torrent_blocks = soup.find_all('div', class_='v-list-item')
        if not torrent_blocks:
            self.logger.error("anilibria_parser", "Не найдены блоки торрентов ('div.v-list-item').")
            return {"source": urlparse(url_to_fetch).netloc, "title": {"ru": ru_title, "en": en_title}, "torrents": [], "error": "Не найдены блоки торрентов"}
        
        self.logger.info(f"Найдено {len(torrent_blocks)} визуальных блоков торрентов.")

        for index, block in enumerate(torrent_blocks):
            try:
                episodes_element = block.find('div', class_='fz-90')
                episodes = episodes_element.text.strip() if episodes_element else "N/A"
                
                magnet_link_tag = block.find('a', href=re.compile(r'^magnet:'))
                if not magnet_link_tag:
                    self.logger.warning(f"В блоке торрента №{index+1} не найдена magnet-ссылка.")
                    continue
                magnet_link = magnet_link_tag['href']
                
                # --- ИЗМЕНЕНИЕ: Уточнен селектор для поиска информации о торренте ---
                info_element = block.find('div', class_='text-grey-darken-2 fz-75')
                # --- КОНЕЦ ИЗМЕНЕНИЯ ---
                
                if not info_element:
                    self.logger.warning(f"В блоке торрента №{index+1} не найдена строка с датой/качеством.")
                    continue
                
                info_string = info_element.text.strip()
                parts = [p.strip() for p in info_string.split('•')]
                
                date_raw = parts[0]
                formatted_datetime = self._normalize_date_from_anilibria(date_raw)
                quality = " • ".join(parts[1:]) if len(parts) > 1 else None

                torrent_info = {
                    "torrent_id": f"anilibria_{len(torrents) + 1:03d}",
                    "episodes": episodes,
                    "date_time": formatted_datetime,
                    "quality": quality,
                    "link": magnet_link
                }
                torrents.append(torrent_info)
            except Exception as e:
                self.logger.warning(f"Пропущен один блок торрента из-за ошибки парсинга: {e}. Блок: {block.text[:150]}...")
                continue
        
        self.logger.info(f"Найдено и обработано {len(torrents)} торрентов.")
        
        return {
            "source": urlparse(url_to_fetch).netloc,
            "title": {"ru": ru_title, "en": en_title},
            "torrents": torrents
        }