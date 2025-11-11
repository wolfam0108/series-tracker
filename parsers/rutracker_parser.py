import re
import os
from typing import Dict, Optional, List
from bs4 import BeautifulSoup
import requests
from datetime import datetime, timedelta, timezone
from db import Database
from logger import Logger
import time
from requests.exceptions import RequestException, Timeout
from flask import current_app as app
from urllib.parse import urlparse
from auth import AuthManager


class RuTrackerParser:
    MAX_RETRIES = 5
    RETRY_DELAY = 3

    def __init__(self, auth_manager: AuthManager, db: Database, logger: Logger):
        self.db = db
        self.logger = logger
        self.auth_manager = auth_manager
        if app.debug_manager.is_debug_enabled('auth'):
            self.logger.debug("auth", f"[RuTrackerParser] Инициализирован с AuthManager ID: {id(self.auth_manager)}")

    def _normalize_date(self, date_str: str) -> Optional[str]:
        """
        Нормализует строку с датой и возвращает ее в формате DD.MM.YYYY HH:MM:SS
        """
        try:
            # Приводим к нижнему регистру и убираем лишние пробелы
            date_str = date_str.strip()
            
            # Проверяем формат даты DD-MMM-YY HH:MM (например, 04-Ноя-25 10:18)
            month_map = {
                'янв': '01', 'фев': '02', 'мар': '03', 'апр': '04',
                'мая': '05', 'июн': '06', 'июл': '07', 'авг': '08',
                'сен': '09', 'окт': '10', 'ноя': '11', 'дек': '12',
                'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
                'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
                'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
            }
            
            # Разбиваем строку на части
            parts = date_str.split()
            if len(parts) >= 2:
                date_part = parts[0]  # 04-Ноя-25
                time_part = parts[1]  # 10:18
                
                # Разбиваем дату
                date_components = date_part.split('-')
                if len(date_components) == 3:
                    day, month_name, year = date_components
                    month = month_map.get(month_name.lower(), '01')
                    
                    # Преобразуем год из 2-значного в 4-значный
                    if int(year) < 50:
                        year = '20' + year
                    else:
                        year = '19' + year
                    
                    return f"{day.zfill(2)}.{month}.{year} {time_part}:00"
            
            # Если формат не распознан, возвращаем как есть
            return date_str
        except Exception as e:
            self.logger.error("rutracker_parser", f"Ошибка нормализации даты '{date_str}': {str(e)}")
            return None

    def _save_html_dump(self, html_content: str):
        """Сохраняет HTML-дамп страницы для отладки."""
        try:
            DUMP_DIR = "parser_dumps"
            if not os.path.exists(DUMP_DIR):
                os.makedirs(DUMP_DIR)
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            filename = os.path.join(DUMP_DIR, f"rutracker_parser_{timestamp}.html")
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(html_content)
            self.logger.info("rutracker_parser", f"HTML-дамп сохранен в файл: {filename}")
        except Exception as e:
            self.logger.error(f"rutracker_parser", f"Не удалось сохранить HTML-дамп: {e}", exc_info=True)

    def parse_series(self, url: str, last_known_torrents: Optional[List[Dict]] = None, debug_force_replace: bool = False) -> Dict:
        self.logger.info("rutracker_parser", f"Начало парсинга {url}")

        session = self.auth_manager.get_rutracker_session(url)
        if not session:
            return {"error": f"Не удалось получить аутентифицированную сессию для {url}"}

        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Referer': base_url + '/'
        }

        for attempt in range(self.MAX_RETRIES):
            try:
                if app.debug_manager.is_debug_enabled('rutracker_parser'):
                    self.logger.debug("rutracker_parser", f"Отправка запроса на {url} (попытка {attempt + 1}/{self.MAX_RETRIES})")
                
                response = session.get(url, headers=headers, timeout=15)
                response.raise_for_status()
                self.logger.info("rutracker_parser", f"Страница {url} успешно загружена (попытка {attempt + 1}).")

                html_content = response.content.decode('windows-1251', errors='replace')

                if app.debug_manager.is_debug_enabled('save_html_rutracker'):
                    self._save_html_dump(html_content)

                soup = BeautifulSoup(html_content, 'lxml')

                # Извлекаем заголовок
                title_tag = soup.find('h1', class_='maintitle')
                title_text = title_tag.get_text(strip=True) if title_tag else None
                title_ru = title_text

                # Ищем дату регистрации с более гибким подходом
                date_text = None
                
                # Попробуем разные возможные места и форматы для поиска даты
                
                # 1. Поиск в таблице с информацией о торренте
                attach_table = soup.find('table', class_='attach')
                if attach_table:
                    # Ищем строку с "Зарегистрирован:" или подобным
                    for row in attach_table.find_all('tr'):
                        row_text = row.get_text()
                        # Паттерн для даты в формате DD-MMM-YY HH:MM
                        date_match = re.search(r'(Зарегистрирован|[Зз]арег\.?|Registered):\s*([0-9]{2}-[а-яА-ЯёЁa-zA-Z]{3}-[0-9]{2}\s[0-9]{2}:[0-9]{2})', row_text)
                        if date_match:
                            date_str = date_match.group(2)
                            date_text = self._normalize_date(date_str)
                            if date_text:
                                break
                
                # 2. Если не нашли в таблице, ищем в других местах
                if not date_text:
                    # Ищем в списках, часто дата находится в элементе <li>
                    for li in soup.find_all('li'):
                        li_text = li.get_text(strip=True)
                        # Ищем формат даты DD-MMM-YY HH:MM в начале или конце текста
                        match = re.search(r'([0-9]{2}-[а-яА-ЯёЁa-zA-Z]{3}-[0-9]{2}\s[0-9]{2}:[0-9]{2})', li_text)
                        if match:
                            # Проверим, содержит ли родительский элемент или сам элемент упоминание о регистрации
                            parent = li.parent
                            context_text = (parent.get_text() if parent else "") + " " + li_text
                            if any(reg_keyword in context_text.lower() for reg_keyword in ['зарегистр', 'registered', 'reg', 'дата']):
                                date_str = match.group(1)
                                date_text = self._normalize_date(date_str)
                                if date_text:
                                    break
                
                # 3. Если все еще не нашли, ищем везде по паттерну даты
                if not date_text:
                    # Проверим все текстовые элементы на странице для поиска даты
                    all_text = soup.get_text()
                    # Ищем все возможные совпадения формата даты
                    all_date_matches = re.findall(r'([0-9]{2}-[а-яА-ЯёЁa-zA-Z]{3}-[0-9]{2}\s[0-9]{2}:[0-9]{2})', all_text)
                    for date_match in all_date_matches:
                        # Проверим, есть ли рядом ключевые слова
                        context_start = max(0, all_text.find(date_match) - 100)
                        context_end = min(len(all_text), all_text.find(date_match) + len(date_match) + 100)
                        context = all_text[context_start:context_end]
                        if any(keyword in context.lower() for keyword in ['зарегистр', 'registered', 'reg', 'дата', 'от', 'в']):
                            date_text = self._normalize_date(date_match)
                            if date_text:
                                break

                if not date_text:
                    raise ValueError("Дата регистрации торрента не найдена на странице")

                self.logger.info("rutracker_parser", f"Найдена и обработана дата: {date_text}")

                # Проверяем, нужно ли обновлять данные
                last_known_date = last_known_torrents[0].get('date_time') if last_known_torrents else None
                
                if last_known_date and last_known_date == date_text and not debug_force_replace:
                    self.logger.info("rutracker_parser", "Дата на сайте совпадает с известной. Обновление не требуется.")
                    return {"title": {"ru": title_ru, "en": None}, "torrents": [{"date_time": date_text, "link": None}]}

                # Ищем ссылку на торрент-файл - пробуем разные возможные селекторы
                # ОСНОВНОЙ ПРИОРИТЕТ: найти .torrent файл, а не магнет-ссылку
                torrent_link_tag = None
                
                # 1. Сначала ищем по классу 'dl-stub' (это обычно ссылка на торрент-файл)
                # В дампе HTML мы видим: <a href="dl.php?t=6494350" class="dl-stub dl-link dl-topic">
                dl_stub_tag = soup.find('a', class_='dl-stub')
                if dl_stub_tag:
                    # Проверяем, что это не магнет-ссылка
                    if not dl_stub_tag.get('href', '').startswith('magnet:'):
                        torrent_link_tag = dl_stub_tag
                
                if not torrent_link_tag:
                    # 2. Ищем по другим возможным признакам торрента, но исключаем магнет-ссылки
                    # В дампе мы видим, что магнет-ссылка имеет класс 'magnet-link'
                    for a_tag in soup.find_all('a', href=True):
                        href = a_tag.get('href', '')
                        # Проверяем, что это не магнет-ссылка и содержит признак торрента
                        if not href.startswith('magnet:') and ('dl.php?' in href or '/dl.php' in href or '.torrent' in href.lower()):
                            # Также проверим, что это не магнет-ссылка по классу
                            if 'magnet-link' not in a_tag.get('class', []):
                                torrent_link_tag = a_tag
                                break
                
                if not torrent_link_tag:
                    # 3. Ищем по тексту ссылки, исключая магнет-ссылки
                    for a_tag in soup.find_all('a', href=True):
                        href = a_tag.get('href', '')
                        link_text = a_tag.get_text().lower()
                        # Проверяем, что это не магнет-ссылка по содержимому и классу
                        if (not href.startswith('magnet:') and
                            'magnet-link' not in a_tag.get('class', []) and
                            ('скачать .torrent' in link_text or 'скачать торрент' in link_text or
                             'download .torrent' in link_text or 'download torrent' in link_text or
                             'torrent' in link_text)):
                            torrent_link_tag = a_tag
                            break
                
                if not torrent_link_tag:
                    raise ValueError("Ссылка на торрент не найдена")

                href = torrent_link_tag.get('href', '')
                
                # Проверяем, что это не магнет-ссылка
                if href.startswith('magnet:'):
                    raise ValueError("Найденная ссылка является магнет-ссылкой, а не торрент-файлом")
                
                # Формируем полную ссылку на торрент
                # Важно: RuTracker использует /forum/dl.php, а не /dl.php
                if 'dl.php' in href and not href.startswith('http'):
                    # Если ссылка указывает на dl.php, нужно добавить /forum/ к пути
                    if href.startswith('/'):
                        # Если href начинается с /, проверим, есть ли уже forum
                        if '/forum/' not in href:
                            href = href.replace('/dl.php', '/forum/dl.php')
                    else:
                        # Если href не начинается с /, добавим /forum/
                        if not href.startswith('forum/'):
                            href = f"forum/{href}"
                
                # Проверим, если href уже содержит полный URL
                if href.startswith('http'):
                    torrent_link = href
                else:
                    # Добавим base_url только если href не начинается с /
                    if href.startswith('/'):
                        torrent_link = f"{base_url}{href}"
                    else:
                        torrent_link = f"{base_url}/{href.lstrip('/')}"
                
                # Добавим проверку, что ссылка ведет на торрент-файл, а не на страницу
                if '/dl.php?' in torrent_link and not torrent_link.startswith('magnet:'):
                    # Убедимся, что это правильный путь для скачивания торрента
                    parsed_torrent_url = urlparse(torrent_link)
                    if parsed_torrent_url.path == '/forum/dl.php':
                        # Добавим необходимые заголовки для скачивания торрента
                        pass  # Заголовки будут добавлены в qbittorrent.py при скачивании

                # Ищем магнет-ссылку
                magnet_link_tag = soup.find('a', class_='magnet-link')
                magnet_link = magnet_link_tag.get('href') if magnet_link_tag else None

                # Ищем размер торрента
                size_element = soup.find('span', id='tor-size-humn')
                size = size_element.get_text(strip=True) if size_element else None

                # Ищем статистику (сиды/личи)
                seeders = leechers = None
                stats_container = soup.find('div', class_='mrg_4 pad_4')
                if stats_container:
                    seeders_element = stats_container.find('span', class_='seed')
                    leechers_element = stats_container.find('span', class_='leech')
                    if seeders_element:
                        seeders_match = re.search(r'\d+', seeders_element.get_text())
                        seeders = int(seeders_match.group()) if seeders_match else None
                    if leechers_element:
                        leechers_match = re.search(r'\d+', leechers_element.get_text())
                        leechers = int(leechers_match.group()) if leechers_match else None

                # Возвращаем информацию о торренте
                # Согласно требованиям, основная ссылка должна быть торрент-файлом, а не магнет-ссылкой
                torrent_info = {
                    "link": torrent_link,  # торрент-файл
                    "date_time": date_text,
                    "quality": None,
                    "episodes": None
                }

                # Добавляем магнет-ссылку как дополнительную информацию, если она доступна
                if magnet_link:
                    torrent_info["magnet_link"] = magnet_link
                if size:
                    torrent_info["size"] = size
                if seeders is not None:
                    torrent_info["seeders"] = seeders
                if leechers is not None:
                    torrent_info["leechers"] = leechers

                return {
                    "title": {"ru": title_ru, "en": None},
                    "torrents": [torrent_info]
                }

            except (Timeout, RequestException, UnicodeDecodeError, ValueError) as e:
                self.logger.warning("rutracker_parser", f"Ошибка при обработке {url} (попытка {attempt + 1}/{self.MAX_RETRIES}): {e}")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
            except Exception as e:
                self.logger.error("rutracker_parser", f"Непредвиденная ошибка парсинга {url} (попытка {attempt + 1}/{self.MAX_RETRIES}): {e}", exc_info=True)
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
        
        return {"error": f"Не удалось получить или распарсить страницу {url} после {self.MAX_RETRIES} попыток."}