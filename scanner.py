import os
import time
import json
import hashlib
from datetime import datetime, timezone
from flask import current_app as app
from urllib.parse import urlparse # <-- Добавлен импорт

from auth import AuthManager
from db import Database
from qbittorrent import QBittorrentClient
from parsers.kinozal_parser import KinozalParser
from parsers.anilibria_parser import AnilibriaParser
from parsers.astar_parser import AstarParser
from parsers.anilibria_tv_parser import AnilibriaTvParser
from scrapers.vk_scraper import VKScraper
from rule_engine import RuleEngine
from smart_collector import SmartCollector
from filename_formatter import FilenameFormatter
from status_manager import StatusManager
from logic.task_creator import create_renaming_tasks_for_series
from logic.metadata_processor import build_final_metadata
from utils.tracker_resolver import TrackerResolver

def generate_torrent_id(link, date_time):
    """Генерирует уникальный ID для торрента на основе его ссылки и даты."""
    unique_string = f"{link}{date_time or ''}"
    return hashlib.md5(unique_string.encode()).hexdigest()[:16]

def generate_media_item_id(url: str, pub_date: datetime, series_id: int) -> str:
    """Генерирует уникальный ID для медиа-элемента на основе URL, даты и ID сериала."""
    if pub_date.tzinfo is None:
        pub_date = pub_date.replace(tzinfo=timezone.utc)
    else:
        pub_date = pub_date.astimezone(timezone.utc)
        
    date_str = pub_date.strftime('%Y-%m-%d %H:%M:%S')
    unique_string = f"{url}{date_str}{series_id}"
    return hashlib.md5(unique_string.encode()).hexdigest()[:16]

def perform_series_scan(series_id: int, status_manager: StatusManager, flask_app, debug_force_replace: bool = False, recovery_mode: bool = False, existing_task: dict = None) -> dict:
    """
    Выполняет полное сканирование для одного сериала.
    """
    with flask_app.app_context():
        series = flask_app.db.get_series(series_id)
        if not series:
            flask_app.logger.error("scanner", f"Ошибка сканирования: Сериал с ID {series_id} не найден.")
            return {"success": False, "error": "Сериал не найден"}

        if series.get('source_type') == 'torrent' and not series.get('parser_profile_id'):
            error_msg = f"Сканирование прервано: для торрент-сериала '{series.get('name')}' не назначен профиль правил."
            flask_app.logger.error("scanner", error_msg)
            return {"success": False, "error": error_msg}
        
        status_manager.set_status(series_id, 'error', False)
        status_manager.set_status(series_id, 'scanning', True)

        try:
            # --- ЭТАП 1: ЗАПУСК ЗАДАЧИ НА ПЕРЕОБРАБОТКУ (если необходимо) ---
            task_type = 'mass_torrent_reprocess' if series['source_type'] == 'torrent' else 'mass_vk_reprocess'
            task_data = {'series_id': series_id, 'task_type': task_type}
            
            task_id = None
            existing_pending_task = flask_app.db.get_pending_renaming_task(series_id, task_type)
            
            if existing_pending_task:
                task_id = existing_pending_task['id']
                flask_app.logger.info("scanner", f"Обнаружена существующая задача на переобработку ID {task_id}. Ожидание её завершения.")
            else:
                task_created = flask_app.db.create_renaming_task(task_data)
                if task_created:
                    newly_created_task = flask_app.db.get_pending_renaming_task(series_id, task_type)
                    task_id = newly_created_task['id']
                    flask_app.logger.info("scanner", f"Создана задача на переобработку ID {task_id} перед сканированием.")
                    flask_app.renaming_agent.trigger()
            
            # --- ЭТАП 2: АКТИВНОЕ ОЖИДАНИЕ ЗАВЕРШЕНИЯ ---
            if task_id:
                wait_timeout = 600
                start_time = time.time()
                while True:
                    time.sleep(3)
                    task = flask_app.db.get_renaming_task(task_id)
                    if not task:
                        flask_app.logger.info("scanner", f"Задача на переобработку ID {task_id} завершена. Продолжение сканирования.")
                        break
                    if task.get('status') == 'error':
                        raise Exception(f"Задача на переобработку ID {task_id} завершилась с ошибкой: {task.get('error_message')}")
                    if time.time() - start_time > wait_timeout:
                        raise Exception(f"Таймаут ожидания завершения задачи на переобработку ID {task_id}.")
           
            if series.get('source_type') == 'vk_video':
                # ... (весь блок для vk_video остается без изменений) ...
                flask_app.logger.info("scanner", f"VK-Сериал ID {series_id}: Этап 1 - Сбор кандидатов.")
                channel_url, query = series['url'].split('|', 1)
                search_mode = series.get('vk_search_mode', 'search')
                scraper = VKScraper(flask_app.db, flask_app.logger)
                scraped_videos = scraper.scrape_video_data(channel_url, query, search_mode)

                engine = RuleEngine(flask_app.db, flask_app.logger)
                profile_id = series.get('parser_profile_id')
                if not profile_id:
                    raise ValueError("Для сериала не назначен профиль правил парсера.")
                
                processed_videos = engine.process_videos(profile_id, scraped_videos)

                candidates_to_save = []
                for video_data in processed_videos:
                    extracted = video_data.get('result', {}).get('extracted', {})
                    if extracted.get('episode') is None and extracted.get('start') is None:
                        continue
                    
                    source_info = video_data.get('source_data', {})
                    pub_date = source_info.get('publication_date')
                    url = source_info.get('url')
                    title = source_info.get('title')

                    if not all([pub_date, url, title]):
                        continue

                    unique_id = generate_media_item_id(url, pub_date, series_id)
                    db_item = {
                        "series_id": series_id, "unique_id": unique_id,
                        "source_url": url, "publication_date": pub_date,
                        "resolution": source_info.get('resolution'),
                        "source_title": title 
                    }
                    if 'season' in extracted: db_item['season'] = extracted['season']
                    if 'episode' in extracted:
                        db_item["episode_start"] = extracted['episode']
                    elif 'start' in extracted:
                        db_item["episode_start"] = extracted['start']
                        if 'end' in extracted: db_item["episode_end"] = extracted['end']
                    if 'voiceover' in extracted: db_item['voiceover_tag'] = extracted['voiceover']
                    
                    candidates_to_save.append(db_item)
                
                if candidates_to_save:
                    flask_app.db.add_or_update_media_items(candidates_to_save)
                    flask_app.logger.info("scanner", f"Сохранено/обновлено {len(candidates_to_save)} кандидатов в БД.")

                flask_app.logger.info("scanner", f"VK-Сериал ID {series_id}: Этап 2 - Запуск SmartCollector для обновления плана.")
                collector = SmartCollector(flask_app.logger, flask_app.db) 
                collector.collect(series_id)

                flask_app.logger.info("scanner", f"VK-Сериал ID {series_id}: Этап 2.5 - Усыновление существующих файлов.")
                flask_app.scanner_agent.sync_single_series_filesystem(series_id)

                flask_app.logger.info("scanner", f"VK-Сериал ID {series_id}: Этап 3 - Создание задач на загрузку.")
                planned_items = flask_app.db.get_media_items_by_plan_statuses(series_id, ['in_plan_single', 'in_plan_compilation'])
                tasks_created = 0
                formatter = FilenameFormatter(flask_app.logger)

                for item in planned_items:
                    if item['status'] == 'pending':
                        if flask_app.db.get_download_task_by_uid(item['unique_id']):
                            continue

                        metadata = build_final_metadata(series, item, {})
                        final_filename = formatter.format_filename(series, metadata)
                        
                        save_path = os.path.join(series['save_path'], final_filename)
                        
                        task_data = {
                            "unique_id": item['unique_id'],
                            "series_id": series_id,
                            "video_url": item['source_url'],
                            "save_path": save_path
                        }
                        flask_app.db.add_download_task(task_data)
                        tasks_created += 1
                
                if tasks_created > 0:
                    flask_app.logger.info("scanner", f"Создано {tasks_created} новых задач на загрузку.")
                    flask_app.downloader_agent._broadcast_queue_update()

                create_renaming_tasks_for_series(series_id, flask_app)

                status_manager.sync_vk_statuses(series_id)
                return {"success": True, "message": "Сканирование и планирование для VK-сериала завершены."}
            
            else:
                # --- Логика для торрент-сериалов ---
                auth_manager = AuthManager(flask_app.db, flask_app.logger)
                if flask_app.debug_manager.is_debug_enabled('auth'):
                    flask_app.logger.debug("auth", f"[Scanner] Создан ЕДИНЫЙ AuthManager ID: {id(auth_manager)} для всего сканирования.")

                resolver = TrackerResolver(flask_app.db)
                tracker_info = resolver.get_tracker_by_url(series['url'])

                if not tracker_info:
                    raise Exception(f"Не удалось определить трекер для URL: {series['url']}")

                parser_class_name = tracker_info['parser_class']
                parser_classes = {
                    'KinozalParser': KinozalParser,
                    'AnilibriaParser': AnilibriaParser,
                    'AnilibriaTvParser': AnilibriaTvParser,
                    'AstarParser': AstarParser
                }

                parser_class = parser_classes.get(parser_class_name)
                if not parser_class:
                    raise Exception(f"Парсер с классом '{parser_class_name}' не найден")

                if parser_class_name == 'KinozalParser':
                    parser = parser_class(auth_manager, flask_app.db, flask_app.logger)
                else:
                    parser = parser_class(flask_app.db, flask_app.logger)

                qb_client = QBittorrentClient(auth_manager, flask_app.db, flask_app.logger)

                files_in_db = flask_app.db.get_torrent_files_for_series(series_id)
                missing_files = [f for f in files_in_db if f.get('status') == 'missing']

                if missing_files:
                    hashes_to_recheck = {f['qb_hash'] for f in missing_files if f.get('qb_hash')}
                    for qb_hash in hashes_to_recheck:
                        torrent_db_entry = flask_app.db.get_torrent_by_hash(qb_hash)
                        if torrent_db_entry:
                            flask_app.logger.info("scanner", f"Обнаружен отсутствующий файл для торрента {qb_hash[:8]}. Создание задачи для Агента на перепроверку.")
                            flask_app.agent.add_recheck_task(
                                torrent_hash=qb_hash,
                                series_id=series_id,
                                torrent_id=torrent_db_entry['torrent_id']
                            )
                        else:
                            flask_app.logger.warning("scanner", f"Не удалось найти торрент в БД по хешу {qb_hash} для создания задачи на recheck.")
                
                task_id = None
                task_data_torrents = []
                results_data = {}

                if recovery_mode and existing_task:
                    flask_app.logger.info("scanner", f"Восстановление задачи сканирования ID {existing_task['id']} для сериала {series_id}")
                    task_id = existing_task['id']
                    task_data_torrents = existing_task.get('task_data', [])
                    results_data = existing_task.get('results_data', {})
                else:
                    flask_app.logger.info("scanner", f"Начало сканирования для series_id: {series_id}. Режим отладки: {'ВКЛ' if debug_force_replace else 'ВЫКЛ'}")
                    
                    all_db_torrents = flask_app.db.get_torrents(series_id)
                    db_hashes = [t['qb_hash'] for t in all_db_torrents if t.get('qb_hash')]
                    torrents_in_qb = qb_client.get_torrents_info(db_hashes) if db_hashes else []
                    hashes_in_qb = {t['hash'] for t in torrents_in_qb} if torrents_in_qb else set()
                    active_db_torrents = [t for t in all_db_torrents if t.get('qb_hash') in hashes_in_qb]
                    
                    # --- НАЧАЛО НОВОЙ ЛОГИКИ ПЕРЕБОРА ЗЕРКАЛ ---
                    primary_url = series['url']
                    flask_app.logger.info("scanner", f"Попытка парсинга основного URL: {primary_url}")
                    
                    # 1. Сначала пробуем основной URL, сохраненный для сериала
                    parsed_data = parser.parse_series(primary_url, last_known_torrents=active_db_torrents, debug_force_replace=debug_force_replace)
                    
                    # 2. Если парсинг основного URL НЕ удался, пробуем другие зеркала
                    if parsed_data.get('error'):
                        flask_app.logger.warning(f"scanner", f"Основной URL не сработал: {parsed_data.get('error')}. Пробуем зеркала...")
                        
                        original_parsed_url = urlparse(primary_url)
                        failed_domain = original_parsed_url.netloc
                        
                        # Получаем список всех зеркал и убираем из него то, что уже пробовали
                        all_mirrors = tracker_info.get('mirrors', [])
                        fallback_mirrors = [m for m in all_mirrors if m != failed_domain]
                        
                        if not fallback_mirrors:
                            flask_app.logger.warning("scanner", "Других зеркал для переключения не найдено.")
                        else:
                            for mirror in fallback_mirrors:
                                # Собираем новый URL на основе зеркала
                                new_url = original_parsed_url._replace(netloc=mirror).geturl()
                                flask_app.logger.info("scanner", f"Попытка парсинга зеркала: {new_url}")
                                
                                current_result = parser.parse_series(new_url, last_known_torrents=active_db_torrents, debug_force_replace=debug_force_replace)
                                
                                if not current_result.get('error'):
                                    parsed_data = current_result # Сохраняем успешный результат
                                    flask_app.logger.info("scanner", f"Зеркало {mirror} успешно распарсено.")
                                    break # Успех, выходим из цикла по зеркалам
                                else:
                                    flask_app.logger.warning("scanner", f"Ошибка парсинга зеркала {mirror}: {current_result.get('error')}")

                    # --- КОНЕЦ НОВОЙ ЛОГИКИ ПЕРЕБОРА ЗЕРКАЛ ---

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
                        flask_app.logger.info("scanner", "Парсер не вернул новых или обновленных торрентов.")
                        status_manager.set_status(series_id, 'scanning', False)
                        return {"success": True, "tasks_created": 0}

                    site_torrents = []
                    if series.get('quality'):
                        selected_qualities = {q.strip() for q in series['quality'].split(';') if q.strip()}
                        site_torrents = [t for t in new_or_updated_torrents if t.get('quality') in selected_qualities]
                    else:
                        site_torrents = new_or_updated_torrents
                    
                    if debug_force_replace:
                        flask_app.logger.warning("scanner", "РЕЖИМ ОТЛАДКИ: Все активные торренты будут принудительно заменены.")
                        hashes_to_delete = [t['qb_hash'] for t in active_db_torrents]
                        if hashes_to_delete:
                            qb_client.delete_torrents(hashes_to_delete, delete_files=False)
                            for t in active_db_torrents:
                                flask_app.db.update_torrent_by_id(t['id'], {'is_active': False})
                        active_db_torrents = []

                    torrents_to_process = []
                    site_type = 'fixed' if 'astar' in tracker_info.get('canonical_name', '') else 'rolling'
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
                        flask_app.logger.info("scanner", "Новых торрентов для добавления не найдено.")
                        status_manager.set_status(series_id, 'scanning', False)
                        return {"success": True, "tasks_created": 0}

                    task_id = flask_app.db.create_scan_task(series_id, torrents_to_process)
                    task_data_torrents = torrents_to_process
                    flask_app.logger.info("scanner", f"Создана задача сканирования ID {task_id} с {len(task_data_torrents)} торрентами.")

                for index, task_item in enumerate(task_data_torrents):
                    site_torrent = task_item['site_torrent']
                    if str(index) in results_data:
                        continue
                    
                    new_hash, link_type = qb_client.add_torrent(site_torrent['link'], series['save_path'], site_torrent['torrent_id'])

                    if new_hash:
                        results_data[str(index)] = {"hash": new_hash, "link_type": link_type}
                        flask_app.db.update_scan_task_results(task_id, results_data)
                    else:
                        flask_app.logger.warning("scanner", f"Не удалось добавить торрент {site_torrent['torrent_id']} в рамках задачи {task_id}. Пропуск.")
                        continue

                if not results_data:
                    raise Exception("Не удалось добавить ни одного торрента из списка.")
                
                tasks_created = 0
                for index_str, result_item in results_data.items():
                    index = int(index_str)
                    task_item = task_data_torrents[index]
                    site_torrent = task_item['site_torrent']
                    old_torrent_to_replace = task_item['old_torrent_to_replace']
                    new_hash = result_item['hash']
                    link_type = result_item['link_type']
                    
                    existing_db_entry = next((t for t in flask_app.db.get_torrents(series_id) if t['torrent_id'] == site_torrent['torrent_id']), None)
                    if existing_db_entry:
                        flask_app.db.update_torrent_by_id(existing_db_entry['id'], {'is_active': True, 'qb_hash': new_hash})
                    else:
                        flask_app.db.add_torrent(series_id, site_torrent, is_active=True, qb_hash=new_hash)

                    if old_torrent_to_replace:
                        flask_app.db.deactivate_torrent_and_clear_files(old_torrent_to_replace['id'])
                        qb_client.delete_torrents([old_torrent_to_replace['qb_hash']], delete_files=False)

                    flask_app.agent.add_task(
                        torrent_hash=new_hash, 
                        series_id=series_id, 
                        torrent_id=site_torrent['torrent_id'], 
                        old_torrent_id=old_torrent_to_replace['torrent_id'] if old_torrent_to_replace else 'None',
                        link_type=link_type
                    )
                    tasks_created += 1
                
                flask_app.logger.info("scanner", f"Создано задач для агента: {tasks_created}.")
                
                if tasks_created == 0:
                     status_manager.set_status(series_id, 'scanning', False)
                
                flask_app.db.delete_scan_task(task_id)
                return {"success": True, "tasks_created": tasks_created}

        except Exception as e:
            flask_app.logger.error("scanner", f"Ошибка в процессе сканирования для series_id {series_id}: {e}", exc_info=True)
            status_manager.set_status(series_id, 'error', True)
            return {"success": False, "error": str(e)}
        finally:
            status_manager.set_status(series_id, 'scanning', False)