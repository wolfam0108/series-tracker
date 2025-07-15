from datetime import datetime, timezone
from flask import current_app as app
from auth import AuthManager
from db import Database
from qbittorrent import QBittorrentClient
from parsers.kinozal_parser import KinozalParser
from parsers.anilibria_parser import AnilibriaParser
from parsers.astar_parser import AstarParser
from parsers.anilibria_tv_parser import AnilibriaTvParser
from scrapers.vk_scraper import VKScraper
from rule_engine import RuleEngine
from collectors.smart_collector import SmartCollector
import hashlib
import json
import time

def generate_torrent_id(link, date_time):
    """Генерирует уникальный ID для торрента на основе его ссылки и даты."""
    unique_string = f"{link}{date_time or ''}"
    return hashlib.md5(unique_string.encode()).hexdigest()[:16]

def generate_media_item_id(url: str, pub_date: datetime) -> str:
    """Генерирует уникальный ID для медиа-элемента на основе URL и даты."""
    date_str = pub_date.strftime('%Y-%m-%d %H:%M:%S')
    unique_string = f"{url}{date_str}"
    return hashlib.md5(unique_string.encode()).hexdigest()[:16]

def _broadcast_series_update(series_id):
    """Вспомогательная функция для трансляции обновлений сериала через SSE."""
    series_data = app.db.get_series(series_id)
    if series_data:
        if series_data.get('last_scan_time'):
            series_data['last_scan_time'] = series_data['last_scan_time'].isoformat()
        if 'state' in series_data:
            try:
                json.loads(series_data['state'])
            except (json.JSONDecodeError, TypeError):
                pass
        app.sse_broadcaster.broadcast('series_updated', series_data)

def perform_series_scan(series_id: int, debug_force_replace: bool = False, recovery_mode: bool = False, existing_task: dict = None) -> dict:
    """
    Выполняет полное сканирование для одного сериала, используя транзакционный подход.
    """
    with app.app_context():
        series = app.db.get_series(series_id)
        if not series:
            app.logger.error("scanner", f"Ошибка сканирования: Сериал с ID {series_id} не найден.")
            return {"success": False, "error": "Сериал не найден"}

        # --- НАЧАЛО БЛОКА ЛОГИКИ ДЛЯ РАЗНЫХ ИСТОЧНИКОВ ---
        if series.get('source_type') == 'vk_video':
            app.logger.info("scanner", f"Запуск сканирования для VK-сериала: {series['name']}")
            
            try:
                # URL для VK хранится в формате "url_канала|поисковый_запрос"
                channel_url, query = series['url'].split('|')
            except ValueError:
                 app.logger.error("scanner", f"Неверный формат URL для VK-сериала ID {series_id}. Ожидается 'канал|запрос'")
                 return {"success": False, "error": "Неверный формат URL для VK-сериала. Ожидается 'канал|запрос'"}

            # 1. Скрапинг данных с VK
            scraper = VKScraper(app.db, app.logger)
            scraped_videos = scraper.scrape_video_data(channel_url, query)

            # 2. Обработка движком правил
            engine = RuleEngine(app.db, app.logger)
            profile_id = series.get('parser_profile_id')
            if not profile_id:
                app.logger.error("scanner", f"Для VK-сериала ID {series_id} не назначен профиль правил парсера.")
                return {"success": False, "error": "Для сериала не назначен профиль правил парсера."}
            
            processed_videos = engine.process_videos(profile_id, scraped_videos)

            # 3. Сборка оптимального плейлиста
            collector = SmartCollector(app.logger)
            existing_items = app.db.get_media_items_for_series(series_id)
            
            profiles = app.db.get_parser_profiles()
            profile = next((p for p in profiles if p['id'] == profile_id), None)
            preferred_voiceovers = profile.get('preferred_voiceovers', '') if profile else ''

            final_plan = collector.collect(processed_videos, existing_items, preferred_voiceovers)
            
            # 4. Сохранение результата в БД
            items_to_save_in_db = []
            tasks_for_downloader = []

            for item in final_plan:
                db_item = {
                    "series_id": series_id,
                    "unique_id": generate_media_item_id(item['source_data']['url'], item['source_data']['publication_date']),
                    "status": item['status'],
                    "source_url": item['source_data']['url'],
                    "publication_date": item['source_data']['publication_date'],
                }
                
                if item['result']['action'] in ['extract_single', 'assign_episode_number']:
                    db_item["episode_start"] = item['result']['extracted']['episode']
                elif item['result']['action'] == 'extract_range':
                    db_item["episode_start"] = item['result']['extracted']['start']
                    db_item["episode_end"] = item['result']['extracted']['end']
                
                if 'voiceover' in item['result']['extracted']:
                    db_item['voiceover_tag'] = item['result']['extracted']['voiceover']

                items_to_save_in_db.append(db_item)
                
                existing = next((i for i in existing_items if i['unique_id'] == db_item['unique_id']), None)
                if item['status'] in ['new', 'new_compilation'] and not (existing and existing.get('is_ignored_by_user')):
                    tasks_for_downloader.append(db_item)
            
            if items_to_save_in_db:
                app.logger.info("scanner", f"Обнаружено {len(items_to_save_in_db)} медиа-элементов для обновления/добавления в БД.")
                app.db.add_or_update_media_items(items_to_save_in_db)

            app.logger.info("scanner", f"Сформировано {len(tasks_for_downloader)} задач для загрузчика (реализация на Этапе 3).")

            app.db.set_series_state(series_id, 'waiting', scan_time=datetime.now(timezone.utc))
            _broadcast_series_update(series_id)
            return {"success": True, "message": "Сканирование VK-сериала завершено."}


        # --- НАЧАЛО СТАРОЙ ЛОГИКИ ДЛЯ ТОРРЕНТОВ ---
        if not recovery_mode:
            state_str = series['state']
            is_busy = False

            if state_str.startswith(('scanning', 'rechecking')):
                is_busy = True
            elif state_str.startswith('{'):
                try:
                    state_obj = json.loads(state_str)
                    blocking_agent_stages = {'metadata', 'renaming', 'checking', 'activating'}
                    
                    current_stages = set(state_obj.values())
                    if not blocking_agent_stages.isdisjoint(current_stages):
                        is_busy = True
                except (json.JSONDecodeError, TypeError):
                    pass
            
            if is_busy:
                app.logger.warning("scanner", f"Сканирование для series_id {series_id} пропущено: процесс уже запущен (статус: {state_str}).")
                return {"success": False, "error": f"Процесс уже запущен: {state_str}"}

        app.db.set_series_state(series_id, 'scanning')
        _broadcast_series_update(series_id)

        auth_manager = AuthManager(app.db, app.logger)
        qb_client = QBittorrentClient(auth_manager, app.db, app.logger)

        task_id = None
        task_data_torrents = []
        results_data = {}

        try:
            if recovery_mode and existing_task:
                app.logger.info("scanner", f"Восстановление задачи сканирования ID {existing_task['id']} для сериала {series_id}")
                task_id = existing_task['id']
                task_data_torrents = existing_task.get('task_data', [])
                results_data = existing_task.get('results_data', {})
            else:
                app.logger.info("scanner", f"Начало сканирования для series_id: {series_id}. Режим отладки: {'ВКЛ' if debug_force_replace else 'ВЫКЛ'}")
                
                site_key = series['site']
                if 'kinozal' in site_key:
                    site_key = 'kinozal.me'
                elif 'astar' in site_key:
                    site_key = 'astar.bz'

                parsers = {
                    'kinozal.me': KinozalParser(auth_manager, app.db, app.logger),
                    'aniliberty.top': AnilibriaParser(app.db, app.logger),
                    'anilibria.tv': AnilibriaTvParser(app.db, app.logger),
                    'astar.bz': AstarParser(app.db, app.logger)
                }
                
                parser = parsers.get(site_key)
                if not parser:
                    raise Exception(f"Парсер для сайта {series['site']} (ключ: {site_key}) не найден")

                all_db_torrents = app.db.get_torrents(series_id)
                db_hashes = [t['qb_hash'] for t in all_db_torrents if t.get('qb_hash')]
                torrents_in_qb = qb_client.get_torrents_info(db_hashes) if db_hashes else []
                hashes_in_qb = {t['hash'] for t in torrents_in_qb} if torrents_in_qb else set()
                active_db_torrents = [t for t in all_db_torrents if t.get('qb_hash') in hashes_in_qb]
                
                parsed_data = parser.parse_series(series['url'], last_known_torrents=active_db_torrents)

                if parsed_data.get('error'):
                    raise Exception(f"Ошибка парсера: {parsed_data['error']}")
                
                all_site_torrents = []
                for t in parsed_data.get("torrents", []):
                    link_for_id = t.get('raw_link_for_id_gen', t.get('link'))
                    if link_for_id:
                        t["torrent_id"] = generate_torrent_id(link_for_id, t.get("date_time"))
                    all_site_torrents.append(t)
                
                new_or_updated_torrents = [t for t in all_site_torrents if t.get('link')]

                if not new_or_updated_torrents:
                    app.logger.info("scanner", "Парсер не вернул новых или обновленных торрентов.")
                    app.db.set_series_state(series_id, 'waiting')
                    _broadcast_series_update(series_id)
                    return {"success": True, "tasks_created": 0}

                site_torrents = []
                if series.get('quality'):
                    selected_qualities = {q.strip() for q in series['quality'].split(';') if q.strip()}
                    site_torrents = [t for t in new_or_updated_torrents if t.get('quality') in selected_qualities]
                    if app.debug_manager.is_debug_enabled('scanner'):
                        app.logger.debug("scanner", f"Отфильтровано {len(site_torrents)} из {len(new_or_updated_torrents)} новых торрентов по качеству: {selected_qualities}")
                else:
                    site_torrents = new_or_updated_torrents
                
                if debug_force_replace:
                    app.logger.warning("scanner", "РЕЖИМ ОТЛАДКИ: Все активные торренты будут принудительно заменены.")
                    hashes_to_delete = [t['qb_hash'] for t in active_db_torrents]
                    if hashes_to_delete:
                        qb_client.delete_torrents(hashes_to_delete, delete_files=False)
                        for t in active_db_torrents:
                            app.db.update_torrent_by_id(t['id'], {'is_active': False})
                    active_db_torrents = []

                torrents_to_process = []
                site_type = 'fixed' if series['site'].startswith('astar') else 'rolling'
                if app.debug_manager.is_debug_enabled('scanner'):
                    app.logger.debug("scanner", f"Стратегия обновления для сайта {series['site']}: {site_type}")

                for site_torrent in site_torrents:
                    existing_active_entry = next((t for t in active_db_torrents if t['torrent_id'] == site_torrent['torrent_id']), None)
                    if existing_active_entry: continue

                    old_torrent_to_replace = None
                    if site_type == 'fixed':
                        old_torrent_to_replace = next((t for t in active_db_torrents if t.get('episodes') == site_torrent.get('episodes')), None)
                    elif site_type == 'rolling' and len(active_db_torrents) == 1:
                        old_torrent_to_replace = active_db_torrents[0]
                    
                    torrents_to_process.append({
                        "site_torrent": site_torrent,
                        "old_torrent_to_replace": old_torrent_to_replace
                    })
                
                if not torrents_to_process:
                    app.logger.info("scanner", "Новых торрентов для добавления не найдено.")
                    app.db.set_series_state(series_id, 'waiting')
                    _broadcast_series_update(series_id)
                    return {"success": True, "tasks_created": 0}

                task_id = app.db.create_scan_task(series_id, torrents_to_process)
                task_data_torrents = torrents_to_process
                app.logger.info("scanner", f"Создана задача сканирования ID {task_id} с {len(task_data_torrents)} торрентами.")

            for index, task_item in enumerate(task_data_torrents):
                site_torrent = task_item['site_torrent']
                
                if str(index) in results_data:
                    if app.debug_manager.is_debug_enabled('scanner'):
                        app.logger.debug("scanner", f"Пропуск торрента {index + 1}/{len(task_data_torrents)} (уже обработан).")
                    continue
                
                if app.debug_manager.is_debug_enabled('scanner'):
                    app.logger.debug("scanner", f"Обработка торрента {index + 1}/{len(task_data_torrents)}: {site_torrent['torrent_id']}")
                
                new_hash, link_type = qb_client.add_torrent(site_torrent['link'], series['save_path'], site_torrent['torrent_id'])

                if new_hash:
                    results_data[str(index)] = {"hash": new_hash, "link_type": link_type}
                    app.db.update_scan_task_results(task_id, results_data)
                    if app.debug_manager.is_debug_enabled('scanner'):
                        app.logger.debug("scanner", f"Торрент {site_torrent['torrent_id']} добавлен. Hash: {new_hash[:8]}. Результат сохранен.")
                else:
                    app.logger.warning("scanner", f"Не удалось добавить торрент {site_torrent['torrent_id']} в рамках задачи {task_id}. Пропуск.")
                    continue

            if not results_data:
                error_message = "Не удалось добавить ни одного торрента из списка."
                app.logger.error("scanner", f"Ошибка в процессе сканирования для series_id {series_id}: {error_message}")
                app.db.set_series_state(series_id, 'error')
                _broadcast_series_update(series_id)
                if task_id:
                    app.db.delete_scan_task(task_id)
                return {"success": False, "error": error_message}
            
            app.logger.info("scanner", f"Всего {len(results_data)} торрентов из ScanTask ID {task_id} успешно добавлены.")
            tasks_created = 0
            for index_str, result_item in results_data.items():
                index = int(index_str)
                task_item = task_data_torrents[index]
                site_torrent = task_item['site_torrent']
                old_torrent_to_replace = task_item['old_torrent_to_replace']
                new_hash = result_item['hash']
                link_type = result_item['link_type']
                
                existing_db_entry = next((t for t in app.db.get_torrents(series_id) if t['torrent_id'] == site_torrent['torrent_id']), None)
                if existing_db_entry:
                    app.db.update_torrent_by_id(existing_db_entry['id'], {'is_active': False, 'qb_hash': new_hash})
                else:
                    app.db.add_torrent(series_id, site_torrent, is_active=False, qb_hash=new_hash)

                if old_torrent_to_replace:
                    app.db.update_torrent_by_id(old_torrent_to_replace['id'], {'is_active': False})
                    qb_client.delete_torrents([old_torrent_to_replace['qb_hash']], delete_files=False)

                app.agent.add_task(
                    torrent_hash=new_hash, 
                    series_id=series_id, 
                    torrent_id=site_torrent['torrent_id'], 
                    old_torrent_id=old_torrent_to_replace['torrent_id'] if old_torrent_to_replace else 'None',
                    link_type=link_type
                )
                tasks_created += 1
            
            app.logger.info("scanner", f"Создано задач для агента: {tasks_created}.")
            
            if tasks_created == 0:
                app.db.set_series_state(series_id, 'waiting')
            
            app.db.delete_scan_task(task_id)
            if app.debug_manager.is_debug_enabled('scanner'):
                app.logger.debug("scanner", f"Задача сканирования ID {task_id} успешно завершена и удалена.")

            _broadcast_series_update(series_id)
            
            return {"success": True, "tasks_created": tasks_created}

        except Exception as e:
            app.logger.error("scanner", f"Ошибка в процессе сканирования для series_id {series_id}: {e}", exc_info=True)
            app.db.set_series_state(series_id, 'error')
            _broadcast_series_update(series_id)
            return {"success": False, "error": str(e)}