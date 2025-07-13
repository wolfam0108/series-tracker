import re
import time
from typing import Dict, Optional, List
from bs4 import BeautifulSoup
import requests
from datetime import datetime
from db import Database
from logger import Logger
from requests.exceptions import RequestException, Timeout
from flask import current_app as app
from urllib.parse import urlparse
import hashlib

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
    MAX_RETRIES = 3
    RETRY_DELAY = 2

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

    def _fetch_page_source(self, url: str) -> Optional[str]:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
        }
        for attempt in range(self.MAX_RETRIES):
            try:
                response = requests.get(url, headers=headers, timeout=15)
                response.raise_for_status()
                return response.text
            except (RequestException, Timeout) as e:
                self.logger.warning("anilibria_tv_parser", f"Ошибка запроса к {url} (попытка {attempt + 1}/{self.MAX_RETRIES}): {e}")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
        return None

    # --- ИЗМЕНЕНИЕ: Метод теперь принимает известные торренты для сравнения ---
    def parse_series(self, url: str, last_known_torrents: Optional[List[Dict]] = None) -> Dict:
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
            date_time = self._normalize_date(date_iso) if date_iso else None

            # Генерируем ID для проверки
            temp_torrent_id = generate_anilibria_tv_torrent_id(link, date_time)
            
            link_to_add = link
            # --- ИЗМЕНЕНИЕ: Если торрент уже известен, не возвращаем ссылку ---
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
                "raw_link_for_id_gen": link, # Сохраняем для генерации постоянного ID в сканере
            })
            
        self.logger.info("anilibria_tv_parser", f"Найдено и обработано {len(torrents)} торрентов.")
        
        return {
            "source": parsed_url.netloc,
            "title": {"ru": title_ru, "en": title_en},
            "torrents": torrents
        }