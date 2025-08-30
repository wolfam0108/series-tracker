import re
import time
import os
from typing import Dict, Optional, List
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from db import Database
from logger import Logger
from flask import current_app as app
from urllib.parse import urlparse
import hashlib
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

def generate_anilibria_tv_torrent_id(link, date_time):
    """Вспомогательная функция для генерации ID, чтобы избежать дублирования."""
    unique_string = f"{link}{date_time or ''}"
    return hashlib.md5(unique_string.encode()).hexdigest()[:16]

def extract_en_title(full_title: str) -> str:
    if not full_title:
        return ""
    parts = [part.strip() for part in full_title.split('/')]
    latin_candidates = [part for part in parts if not re.search(r'[а-яА-Я]', part)]
    if not latin_candidates:
        return ""
    elif len(latin_candidates) == 1:
        return latin_candidates[0]
    else:
        return min(latin_candidates, key=len)

class AnilibriaTvParser:
    # --- ИЗМЕНЕНИЕ: Добавлены константы для Playwright ---
    MAX_RETRIES = 2
    RETRY_DELAY = 5
    TIMEOUT = 45000  # Увеличено время ожидания для прохождения JS-проверки

    def __init__(self, db: Database, logger: Logger):
        self.db = db
        self.logger = logger

    def _normalize_date(self, date_str: str) -> Optional[str]:
        try:
            dt_obj = datetime.fromisoformat(date_str)
            return dt_obj.strftime('%d.%m.%Y %H:%M:%S')
        except (ValueError, TypeError) as e:
            self.logger.error("anilibria_tv_parser", f"Ошибка нормализации даты '{date_str}': {e}")
            return None

    # --- НОВОЕ: Метод для сохранения HTML-дампа ---
    def _save_html_dump(self, html_content: str):
        try:
            DUMP_DIR = "parser_dumps"
            if not os.path.exists(DUMP_DIR):
                os.makedirs(DUMP_DIR)
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            filename = os.path.join(DUMP_DIR, f"anilibria_tv_parser_{timestamp}.html")
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(html_content)
            self.logger.info("anilibria_tv_parser", f"HTML-дамп сохранен в файл: {filename}")
        except Exception as e:
            self.logger.error(f"anilibria_tv_parser", f"Не удалось сохранить HTML-дамп: {e}", exc_info=True)

    # --- ИЗМЕНЕНИЕ: Метод _fetch_page_source теперь использует Playwright ---
    def _fetch_page_source(self, url: str) -> Optional[str]:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
        }
        for attempt in range(self.MAX_RETRIES):
            try:
                with sync_playwright() as p:
                    browser = p.firefox.launch(headless=True)
                    context = browser.new_context(user_agent=headers['User-Agent'])
                    page = context.new_page()
                    
                    self.logger.info("anilibria_tv_parser", f"Переход на страницу {url} (попытка {attempt + 1}). Ожидание JS-проверки...")
                    page.goto(url, timeout=self.TIMEOUT, wait_until="domcontentloaded")
                    
                    # Ждем, пока JS-челлендж не будет пройден и не появится таблица с торрентами
                    self.logger.info("anilibria_tv_parser", "Ожидаем появления таблицы с торрентами...")
                    page.wait_for_selector('table#publicTorrentTable', state='visible', timeout=self.TIMEOUT)
                    self.logger.info("anilibria_tv_parser", "Таблица найдена, страница загружена.")
                    
                    html_content = page.content()
                    browser.close()

                    if app.debug_manager.is_debug_enabled('save_html_anilibria_tv'):
                        self._save_html_dump(html_content)

                    return html_content
            except (PlaywrightTimeoutError, Exception) as e:
                self.logger.warning("anilibria_tv_parser", f"Ошибка Playwright при запросе к {url} (попытка {attempt + 1}/{self.MAX_RETRIES}): {e}")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
        
        self.logger.error(f"anilibria_tv_parser", f"Не удалось получить страницу {url} после {self.MAX_RETRIES} попыток.")
        return None

    def parse_series(self, url: str, last_known_torrents: Optional[List[Dict]] = None, debug_force_replace: bool = False) -> Dict:
        self.logger.info("anilibria_tv_parser", f"Начало парсинга {url}")
        html_content = self._fetch_page_source(url)
        if not html_content:
            return {"error": f"Не удалось загрузить страницу {url}"}

        soup = BeautifulSoup(html_content, 'lxml')
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

        title_tag = soup.find('title')
        full_title = title_tag.get_text(strip=True) if title_tag else ""
        title_ru = full_title
        title_en = extract_en_title(full_title)

        torrents = []
        torrent_table = soup.find('table', id='publicTorrentTable')
        if not torrent_table:
            return {"error": "Не найдена таблица с торрентами на странице."}

        known_torrents_dict = {t['torrent_id']: t for t in last_known_torrents} if last_known_torrents else {}
        rows = torrent_table.find_all('tr')

        for row in rows:
            if not row.find('td'): continue

            link_tag = row.find('a', class_='torrent-download-link')
            if not (link_tag and link_tag.has_attr('href')):
                continue
            
            link = base_url + link_tag['href']

            date_td = row.find('td', class_='torrent-datetime')
            date_iso = date_td['data-datetime'] if date_td and date_td.has_attr('data-datetime') else None
            if date_iso:
                self.logger.info("RAW_DATE_DEBUG", f"[Anilibria.TV] Raw date string found: '{date_iso}'")
            date_time = self._normalize_date(date_iso) if date_iso else None

            temp_torrent_id = generate_anilibria_tv_torrent_id(link, date_time)
            
            link_to_add = link
            if temp_torrent_id in known_torrents_dict:
                link_to_add = None

            info_td = row.find('td', class_='torrentcol1')
            info_text = info_td.get_text(strip=True) if info_td else ''
            
            episodes, quality = None, None
            match = re.match(r'(.+?)\s*\[(.+)\]', info_text)
            if match:
                episodes = match.group(1).strip()
                quality = match.group(2).strip()
            else:
                episodes = info_text

            torrents.append({
                "episodes": episodes,
                "quality": quality,
                "date_time": date_time,
                "link": link_to_add,
                "raw_link_for_id_gen": link,
            })
            
        self.logger.info("anilibria_tv_parser", f"Найдено и обработано {len(torrents)} торрентов.")
        
        return {
            "source": parsed_url.netloc,
            "title": {"ru": title_ru, "en": title_en},
            "torrents": torrents
        }