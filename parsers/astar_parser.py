from typing import Dict, Optional
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from datetime import datetime
import re
from db import Database
from logger import Logger
import time
from flask import current_app as app
from urllib.parse import urlparse

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

    def _fetch_page_source(self, url: str) -> Optional[str]:
        """Запрашивает HTML с использованием Playwright с повторными попытками."""
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
                    
                    self.logger.info("astar_parser", f"Страница {url} успешно загружена (попытка {attempt + 1}).")
                    return html_content
            except PlaywrightTimeoutError as e:
                self.logger.warning("astar_parser", f"Ошибка таймаута при загрузке страницы {url} (попытка {attempt + 1}/{self.MAX_RETRIES}): {e.message.splitlines()[0]}")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
            except Exception as e:
                self.logger.warning("astar_parser", f"Ошибка получения страницы {url} (попытка {attempt + 1}/{self.MAX_RETRIES}): {e}", exc_info=True)
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
        
        self.logger.error("astar_parser", f"Не удалось получить страницу {url} после {self.MAX_RETRIES} попыток.")
        return None
    
    # --- ИЗМЕНЕНИЕ: Метод _clean_filename больше не нужен и удален ---

    def parse_series(self, url: str) -> Dict:
        self.logger.info("astar_parser", f"Начало парсинга {url}")
        html_content = self._fetch_page_source(url)
        if not html_content:
            return {
                "source": "astar.bz", "title": {"ru": None, "en": None},
                "torrents": [], "error": "Не удалось загрузить страницу"
            }

        if app.debug_manager.is_debug_enabled('astar_parser'):
            self.logger.debug("astar_parser", "Начало парсинга HTML")
        soup = BeautifulSoup(html_content, 'html.parser')

        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

        title_tag = soup.find('h1')
        # --- ИЗМЕНЕНИЕ: Убираем вызов _clean_filename, получаем "сырое" название ---
        title_ru = title_tag.text.strip() if title_tag else None
        # ----------------------------------------------------------------------
        
        torrents = []
        episode_versions = {}
        torrent_items = soup.find_all('div', class_='torrent')
        
        for item in torrent_items:
            episode_div = item.find('div', class_='info_d1')
            episode_text = episode_div.text.strip() if episode_div else None
            episodes = None
            quality = None
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

                if episodes in episode_versions:
                    episode_versions[episodes].append(quality)
                else:
                    episode_versions[episodes] = [quality]

            torrent_link_tag = item.find('a', href=re.compile(r'/engine/gettorrent\.php\?id=\d+'))
            link = f"{base_url}{torrent_link_tag['href']}" if torrent_link_tag else None

            date_time = None
            date_divs = item.find_all('div', class_='bord_a1')
            for div in date_divs:
                date_text = re.sub(r'\s+', ' ', div.text.strip())
                date_match = re.search(r'Дата: (\d{2}-\d{2}-\d{4})', date_text)
                if date_match:
                    date_time = self._normalize_date(date_match.group(1))
                    break

            if link and episodes:
                torrents.append({
                    "torrent_id": f"temp_{len(torrents) + 1:03d}", "link": link,
                    "date_time": date_time, "quality": quality, "episodes": episodes
                })

        for episodes, qualities in episode_versions.items():
            if len(qualities) > 1 and "one" in qualities:
                for torrent in torrents:
                    if torrent["episodes"] == episodes and torrent["quality"] == "one":
                        torrent["quality"] = "old"

        return {
            "source": "astar.bz", "title": {"ru": title_ru, "en": None}, "torrents": torrents
        }