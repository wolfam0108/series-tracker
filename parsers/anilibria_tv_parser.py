import re
import time
from typing import Dict, Optional
from bs4 import BeautifulSoup
import requests
from datetime import datetime
from db import Database
from logger import Logger
from requests.exceptions import RequestException, Timeout
from flask import current_app as app
from urllib.parse import urlparse

def extract_en_title(full_title: str) -> str:
    """
    Извлекает наиболее вероятное английское название из комплексной строки.
    """
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
    """
    Парсер для новой версии сайта anilibria.tv.
    """
    MAX_RETRIES = 3
    RETRY_DELAY = 2

    def __init__(self, db: Database, logger: Logger):
        self.db = db
        self.logger = logger

    def _normalize_date(self, date_str: str) -> Optional[str]:
        """
        Нормализует дату из формата ISO ('2025-07-02T18:38:02+00:00')
        в стандартный формат проекта 'DD.MM.YYYY HH:MM:SS'.
        """
        try:
            # datetime.fromisoformat отлично справляется с форматом, включая таймзону
            dt_obj = datetime.fromisoformat(date_str)
            return dt_obj.strftime('%d.%m.%Y %H:%M:%S')
        except (ValueError, TypeError) as e:
            self.logger.error("anilibria_tv_parser", f"Ошибка нормализации даты '{date_str}': {e}")
            return None

    def _fetch_page_source(self, url: str) -> Optional[str]:
        """Запрашивает HTML-код страницы по URL."""
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

    def parse_series(self, url: str) -> Dict:
        self.logger.info("anilibria_tv_parser", f"Начало парсинга {url}")
        html_content = self._fetch_page_source(url)
        if not html_content:
            return {"error": f"Не удалось загрузить страницу {url}"}

        soup = BeautifulSoup(html_content, 'lxml')
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

        # 1. Парсинг названий
        title_tag = soup.find('title')
        full_title = title_tag.get_text(strip=True) if title_tag else ""
        title_ru = full_title
        title_en = extract_en_title(full_title)

        torrents = []
        torrent_table = soup.find('table', id='publicTorrentTable')
        if not torrent_table:
            return {"error": "Не найдена таблица с торрентами на странице."}

        rows = torrent_table.find_all('tr')
        for row in rows:
            if not row.find('td'): continue # Пропускаем заголовок таблицы

            # 2. Парсинг информации о торренте
            info_td = row.find('td', class_='torrentcol1')
            info_text = info_td.get_text(strip=True) if info_td else ''
            
            episodes = quality = None
            match = re.match(r'(.+?)\s*\[(.+)\]', info_text)
            if match:
                episodes = match.group(1).strip()
                quality = match.group(2).strip()
            else:
                episodes = info_text # Если качество не указано в скобках

            # 3. Парсинг даты
            date_td = row.find('td', class_='torrent-datetime')
            date_iso = date_td['data-datetime'] if date_td and date_td.has_attr('data-datetime') else None
            date_time = self._normalize_date(date_iso) if date_iso else None

            # 4. Парсинг ссылки на скачивание
            link_tag = row.find('a', class_='torrent-download-link')
            if link_tag and link_tag.has_attr('href'):
                link = base_url + link_tag['href']
            else:
                continue # Пропускаем строку, если нет ссылки

            torrents.append({
                "episodes": episodes,
                "quality": quality,
                "date_time": date_time,
                "link": link
            })
            
        self.logger.info("anilibria_tv_parser", f"Найдено и обработано {len(torrents)} торрентов.")
        
        return {
            "source": parsed_url.netloc,
            "title": {"ru": title_ru, "en": title_en},
            "torrents": torrents
        }