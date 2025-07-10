import requests
import time
import re
import locale
from urllib.parse import urlparse
from datetime import datetime
from bs4 import BeautifulSoup
from db import Database
from logger import Logger
from typing import Optional, Dict
from requests.exceptions import RequestException, Timeout
from flask import current_app as app

class AnilibriaParser:
    MAX_RETRIES = 3
    RETRY_DELAY = 2

    def __init__(self, db: Database, logger: Logger):
        self.db = db
        self.logger = logger
        try:
            locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
        except locale.Error:
            self.logger.warning("anilibria_parser", "Предупреждение: не удалось установить локаль en_US.UTF-8. Парсинг даты может не сработать на вашей системе.")


    def _normalize_date_from_anilibria(self, date_str: str) -> Optional[str]:
        """
        Нормализует дату из формата Anilibria ('MM/DD/YYYY, HH:MM:SS AM/PM')
        в 'DD.MM.YYYY HH:MM:SS'.
        """
        try:
            parsed_datetime = datetime.strptime(date_str, '%m/%d/%Y, %I:%M:%S %p')
            return parsed_datetime.strftime('%d.%m.%Y %H:%M:%S')
        except ValueError as e:
            self.logger.error("anilibria_parser", f"Ошибка нормализации даты Anilibria '{date_str}': {str(e)}")
            return None

    def _fetch_page_source(self, url: str) -> Optional[str]:
        """
        Запрашивает HTML-код страницы по URL с повторными попытками.
        Использует requests вместо Playwright.
        """
        if app.debug_manager.is_debug_enabled('anilibria_parser'):
            self.logger.debug("anilibria_parser", f"Запрос страницы: {url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        }

        for attempt in range(self.MAX_RETRIES):
            try:
                response = requests.get(url, timeout=15, headers=headers)
                response.raise_for_status()
                self.logger.info("anilibria_parser", f"Страница {url} успешно загружена (попытка {attempt + 1}).")
                return response.text
            except Timeout:
                self.logger.warning("anilibria_parser", f"Ошибка таймаута при запросе к {url} (попытка {attempt + 1}/{self.MAX_RETRIES}).")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
            except RequestException as e:
                self.logger.warning("anilibria_parser", f"Ошибка запроса к {url} (попытка {attempt + 1}/{self.MAX_RETRIES}): {e}")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
        
        self.logger.error("anilibria_parser", f"Не удалось получить страницу {url} после {self.MAX_RETRIES} попыток.")
        return None

    def parse_series(self, original_url: str) -> Dict:
        """Парсит данные сериала с aniliberty.top."""
        self.logger.info("anilibria_parser", f"Начало парсинга {original_url}")

        # --- ИЗМЕНЕНИЕ: Более гибкое регулярное выражение для захвата базового URL релиза ---
        match = re.match(r"(https://aniliberty\.top/(?:release|anime/releases/release)/[^/]+)", original_url)
        if not match:
            self.logger.error("anilibria_parser", f"Не удалось распознать URL релиза: {original_url}. Убедитесь, что ссылка верна.")
            return {
                "source": "aniliberty.top", "title": {"ru": None, "en": None},
                "torrents": [], "error": "Некорректный URL релиза"
            }
        
        # Корректно формируем URL для страницы с торрентами
        base_release_url = match.group(1)
        url_to_fetch = f"{base_release_url}/torrents"
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---

        if app.debug_manager.is_debug_enabled('anilibria_parser') and url_to_fetch != original_url:
            self.logger.debug("anilibria_parser", f"URL скорректирован на страницу с торрентами: {url_to_fetch}")

        html_content = self._fetch_page_source(url_to_fetch)
        if not html_content:
            return {
                "source": "aniliberty.top", "title": {"ru": None, "en": None},
                "torrents": [], "error": f"Не удалось загрузить страницу {url_to_fetch}"
            }

        if app.debug_manager.is_debug_enabled('anilibria_parser'):
            self.logger.debug("anilibria_parser", "Начало парсинга HTML с lxml...")
        soup = BeautifulSoup(html_content, 'lxml')

        ru_title_element = soup.find('div', class_='text-autosize ff-heading lh-110 font-weight-bold mb-1')
        ru_title = ru_title_element.text.strip() if ru_title_element else None
        
        en_title_element = soup.find('div', class_='fz-70 ff-heading text-grey-darken-2 mb-3')
        en_title = en_title_element.text.strip() if en_title_element else None

        if ru_title: self.logger.info("anilibria_parser", f"Название (ru): {ru_title}")
        else: self.logger.error("anilibria_parser", "Название (ru) не найдено")
        
        if en_title: self.logger.info("anilibria_parser", f"Название (en): {en_title}")
        else: self.logger.warning("anilibria_parser", "Название (en) не найдено")

        torrents = []
        torrent_blocks = soup.find_all('div', class_='v-list-item--variant-text')
        
        if not torrent_blocks:
             self.logger.error("anilibria_parser", "Не найдено блоков с торрентами на странице. Структура сайта могла измениться.")
             return {
                "source": urlparse(url_to_fetch).netloc,
                "title": {"ru": ru_title, "en": en_title},
                "torrents": [],
                "error": "Не найдено блоков с торрентами"
            }

        for index, block in enumerate(torrent_blocks):
            try:
                episodes_element = block.find('div', class_='fz-90')
                episodes = episodes_element.text.strip() if episodes_element else None

                magnet_link_tag = block.find('a', href=lambda href: href and href.startswith('magnet:'))
                if not magnet_link_tag:
                    self.logger.warning("anilibria_parser", f"В блоке торрента №{index+1} не найдена magnet-ссылка.")
                    continue
                
                magnet_link = magnet_link_tag['href']
                
                info_element = block.find('div', class_='text-grey-darken-2', string=re.compile(r'\d+/\d+/\d+'))
                
                if not info_element:
                    self.logger.warning("anilibria_parser", f"В блоке торрента №{index+1} не найдена строка с датой/качеством.")
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
                if app.debug_manager.is_debug_enabled('anilibria_parser'):
                    self.logger.debug("anilibria_parser", f"Добавлен торрент: {torrent_info['episodes']}, {torrent_info['quality']}")

            except (AttributeError, KeyError, IndexError, ValueError) as e:
                self.logger.warning("anilibria_parser", f"Пропущен один блок торрента из-за ошибки парсинга: {e}. Блок: {block.text[:100]}...")
                continue
        
        self.logger.info("anilibria_parser", f"Найдено и обработано {len(torrents)} торрентов.")
        
        return {
            "source": urlparse(url_to_fetch).netloc,
            "title": {"ru": ru_title, "en": en_title},
            "torrents": torrents
        }