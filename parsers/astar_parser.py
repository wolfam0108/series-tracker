# Файл: astar_parser.py

from typing import Dict, Optional, List
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from datetime import datetime, timezone
import re
from db import Database
from logger import Logger
import time
from flask import current_app as app
from urllib.parse import urlparse
import hashlib
import os

def generate_astar_torrent_id(link, date_time):
    """Вспомогательная функция для генерации ID, чтобы избежать дублирования."""
    unique_string = f"{link}{date_time or ''}"
    return hashlib.md5(unique_string.encode()).hexdigest()[:16]

class AstarParser:
    TIMEOUT = 10000 
    MAX_RETRIES = 3 
    RETRY_DELAY = 2

    def __init__(self, db: Database, logger: Logger):
        self.db = db
        self.logger = logger

    def _normalize_date(self, date_str: str) -> Optional[str]:
        try:
            date_obj = datetime.strptime(date_str, '%d-%m-%Y')
            return date_obj.strftime('%d.%m.%Y')
        except ValueError as e:
            self.logger.error("astar_parser", f"Ошибка нормализации даты '{date_str}': {str(e)}")
            return None

    def _save_html_dump(self, html_content: str):
        try:
            DUMP_DIR = "parser_dumps"
            if not os.path.exists(DUMP_DIR):
                os.makedirs(DUMP_DIR)
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            filename = os.path.join(DUMP_DIR, f"astar_parser_{timestamp}.html")
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(html_content)
            self.logger.info("astar_parser", f"HTML-дамп сохранен в файл: {filename}")
        except Exception as e:
            self.logger.error(f"astar_parser", f"Не удалось сохранить HTML-дамп: {e}", exc_info=True)

    def _fetch_page_source(self, url: str) -> Optional[str]:
        if app.debug_manager.is_debug_enabled('astar_parser'):
            self.logger.debug("astar_parser", f"Запрос страницы: {url}")
        
        for attempt in range(self.MAX_RETRIES):
            try:
                with sync_playwright() as p:
                    if app.debug_manager.is_debug_enabled('astar_parser'):
                        self.logger.debug("astar_parser", "Запуск браузера Firefox...")
                    browser = p.firefox.launch(headless=True)
                    
                    context = browser.new_context(
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
                        viewport={"width": 1920, "height": 1080},
                        ignore_https_errors=True
                    )
                    page = context.new_page()
                    
                    if app.debug_manager.is_debug_enabled('astar_parser'):
                        self.logger.debug("astar_parser", f"Переход на URL: {url}")
                    page.goto(url, timeout=self.TIMEOUT, wait_until="domcontentloaded")
                    
                    if app.debug_manager.is_debug_enabled('astar_parser'):
                        self.logger.debug("astar_parser", "Ожидаем кнопку 'Все торренты'...")
                    page.wait_for_selector('span#torrent_all', state='visible', timeout=self.TIMEOUT)
                    page.click('span#torrent_all')
                    
                    if app.debug_manager.is_debug_enabled('astar_parser'):
                        self.logger.debug("astar_parser", "Ожидаем появления списка торрентов...")
                    page.wait_for_selector('div.list_torrent', state='visible', timeout=self.TIMEOUT)
                    
                    html_content = page.content()
                    browser.close()
                    
                    if app.debug_manager.is_debug_enabled('save_html_astar'):
                        self._save_html_dump(html_content)
                    
                    self.logger.info("astar_parser", f"Страница {url} успешно загружена (попытка {attempt + 1}).")
                    return html_content
            except (PlaywrightTimeoutError, Exception) as e:
                error_message = str(e).splitlines()[0] if isinstance(e, PlaywrightTimeoutError) else str(e)
                self.logger.warning("astar_parser", f"Ошибка получения страницы {url} (попытка {attempt + 1}/{self.MAX_RETRIES}): {error_message}")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
        
        self.logger.error("astar_parser", f"Не удалось получить страницу {url} после {self.MAX_RETRIES} попыток.")
        return None

    def parse_series(self, url: str, last_known_torrents: Optional[List[Dict]] = None, debug_force_replace: bool = False) -> Dict:
        self.logger.info("astar_parser", f"Начало парсинга {url}")
        html_content = self._fetch_page_source(url)
        if not html_content:
            return {
                "source": "astar.bz", "title": {"ru": None, "en": None},
                "torrents": [], "error": "Не удалось загрузить страницу"
            }

        soup = BeautifulSoup(html_content, 'html.parser')
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

        title_tag = soup.find('h1')
        title_ru = title_tag.text.strip() if title_tag else None
        
        torrents = []
        torrent_items = soup.find_all('div', class_='torrent')
        
        known_torrents_dict = {t['torrent_id']: t for t in last_known_torrents} if last_known_torrents else {}

        for item in torrent_items:
            torrent_link_tag = item.find('a', href=re.compile(r'/engine/gettorrent\.php\?id=\d+'))
            link = f"{base_url}{torrent_link_tag['href']}" if torrent_link_tag else None
            if not link: continue

            date_time = None
            date_divs = item.find_all('div', class_='bord_a1')
            for div in date_divs:
                date_text = re.sub(r'\s+', ' ', div.text.strip())
                date_match = re.search(r'Дата: (\d{2}-\d{2}-\d{4})', date_text)
                if date_match:
                    date_time = self._normalize_date(date_match.group(1))
                    break
            
            temp_torrent_id = generate_astar_torrent_id(link, date_time)

            if temp_torrent_id in known_torrents_dict:
                link_to_add = None
            else:
                link_to_add = link
            
            episode_div = item.find('div', class_='info_d1')
            episode_text = episode_div.text.strip() if episode_div else None
            episodes, quality = None, None
            if episode_text:
                episode_text = re.sub(r'\s*END\s*', '', episode_text).strip()
                episode_text = re.sub(r'\s*\(\d+\.\d+\s*(Mb|Gb)\)', '', episode_text).strip()
                series_range_match = re.match(r'^Серии\s+(\d+-\d+)(?:\s+(.+))?$', episode_text)
                single_episode_match = re.match(r'^Серия\s+(\d+)(?:\s+(.+))?$', episode_text)
                special_match = re.match(r'^Спешл\s+(\d+)(?:\s+(.+))?$', episode_text)

                if series_range_match:
                    episodes = series_range_match.group(1)
                    quality = series_range_match.group(2) or "one"
                elif single_episode_match:
                    episodes = single_episode_match.group(1)
                    quality = single_episode_match.group(2) or "one"
                elif special_match:
                    episodes = f"Спешл {special_match.group(1)}"
                    quality = special_match.group(2) or "one"
                else:
                    continue

            if episodes:
                torrents.append({
                    "link": link_to_add,
                    "raw_link_for_id_gen": link,
                    "date_time": date_time, 
                    "quality": quality, 
                    "episodes": episodes
                })
        
        episode_versions = {}
        for t in torrents:
            if t['episodes'] not in episode_versions:
                episode_versions[t['episodes']] = []
            episode_versions[t['episodes']].append(t['quality'])

        for episodes, qualities in episode_versions.items():
            if len(qualities) > 1 and "one" in qualities:
                for torrent in torrents:
                    if torrent["episodes"] == episodes and torrent["quality"] == "one":
                        torrent["quality"] = "old"

        return {
            "source": "astar.bz", "title": {"ru": title_ru, "en": None}, "torrents": torrents
        }