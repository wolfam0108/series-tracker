import os
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
from smart_collector import SmartCollector
import hashlib
import json
import time
from filename_formatter import FilenameFormatter
from status_manager import StatusManager

def generate_torrent_id(link, date_time):
    """Генерирует уникальный ID для торрента на основе его ссылки и даты."""
    unique_string = f"{link}{date_time or ''}"
    return hashlib.md5(unique_string.encode()).hexdigest()[:16]

def generate_media_item_id(url: str, pub_date: datetime, series_id: int) -> str:
    """Генерирует уникальный ID для медиа-элемента на основе URL, даты и ID сериала."""
    # Убедимся, что дата в UTC для консистентности
    if pub_date.tzinfo is None:
        pub_date = pub_date.replace(tzinfo=timezone.utc)
    else:
        pub_date = pub_date.astimezone(timezone.utc)
        
    date_str = pub_date.strftime('%Y-%m-%d %H:%M:%S')
    unique_string = f"{url}{date_str}{series_id}"
    return hashlib.md5(unique_string.encode()).hexdigest()[:16]

def perform_series_scan(series_id: int, status_manager: StatusManager, debug_force_replace: bool = False, recovery_mode: bool = False, existing_task: dict = None) -> dict:
    """
    Выполняет полное сканирование для одного сериала. 
    """
    with app.app_context():
        series = app.db.get_series(series_id)
        if not series:
            app.logger.error("scanner", f"Ошибка сканирования: Сериал с ID {series_id} не найден.")
            return {"success": False, "error": "Сериал не найден"}

        if series.get('source_type') == 'torrent' and not series.get('parser_profile_id'):
            error_msg = f"Сканирование прервано: для торрент-сериала '{series.get('name')}' не назначен профиль правил."
            app.logger.error("scanner", error_msg)
            return {"success": False, "error": error_msg}

        status_manager.set_status(series_id, 'scanning', True)

        try:
            if series.get('source_type') == 'vk_video':
                app.logger.info("scanner", f"VK-Сериал ID {series_id}: Этап 1 - Сбор кандидатов.")
                channel_url, query = series['url'].split('|', 1)
                search_mode = series.get('vk_search_mode', 'search')
                scraper = VKScraper(app.db, app.logger)
                scraped_videos = scraper.scrape_video_data(channel_url, query, search_mode)

                engine = RuleEngine(app.db, app.logger)
                profile_id = series.get('parser_profile_id')
                if not profile_id:
                    raise ValueError("Для сериала не назначен профиль правил парсера.")
                
                processed_videos = engine.process_videos(profile_id, scraped_videos)

                app.db.reset_plan_status_for_series(series_id)

                candidates_to_save = []
                for video_data in processed_videos:
                    extracted = video_data.get('result', {}).get('extracted', {})
                    if extracted.get('episode') is None and extracted.get('start') is None:
                        continue
                    pub_date = video_data.get('source_data', {}).get('publication_date')
                    url = video_data.get('source_data', {}).get('url')
                    unique_id = generate_media_item_id(url, pub_date, series_id)
                    db_item = {
                        "series_id": series_id, "unique_id": unique_id,
                        "source_url": url, "publication_date": pub_date,
                        "resolution": video_data.get('source_data', {}).get('resolution'),
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
                    app.db.add_or_update_media_items(candidates_to_save)
                    app.logger.info("scanner", f"Сохранено/обновлено {len(candidates_to_save)} кандидатов в БД.")

                app.logger.info("scanner", f"VK-Сериал ID {series_id}: Этап 2 - Запуск SmartCollector для обновления плана.")
                collector = SmartCollector(app.logger, app.db) 
                collector.collect(series_id)

                app.logger.info("scanner", f"VK-Сериал ID {series_id}: Этап 3 - Создание задач на загрузку.")
                planned_items = app.db.get_media_items_by_plan_statuses(series_id, ['in_plan_single', 'in_plan_compilation'])
                tasks_created = 0
                formatter = FilenameFormatter(app.logger)

                for item in planned_items:
                    if item['status'] == 'pending':
                        if app.db.get_download_task_by_uid(item['unique_id']):
                            continue

                        extracted_data = {
                            'season': item.get('season'),
                            'voiceover': item.get('voiceover_tag')
                        }
                        if item.get('episode_end'):
                            extracted_data['start'] = item.get('episode_start')
                            extracted_data['end'] = item.get('episode_end')
                        else:
                            extracted_data['episode'] = item.get('episode_start')
                        
                        final_filename = formatter.format_filename(series, extracted_data)
                        save_path = os.path.join(series['save_path'], final_filename)
                        
                        
                        task_data = {
                            "unique_id": item['unique_id'],
                            "series_id": series_id,
                            "video_url": item['source_url'],
                            "save_path": save_path
                        }
                        app.db.add_download_task(task_data)
                        tasks_created += 1
                
                if tasks_created > 0:
                    app.logger.info("scanner", f"Создано {tasks_created} новых задач на загрузку.")
                    app.downloader_agent._broadcast_queue_update()

                status_manager.sync_vk_statuses(series_id)
                return {"success": True, "message": "Сканирование и планирование для VK-сериала завершены."}
            
            # --- Логика для торрентов ---
            else:
                auth_manager = AuthManager(app.db, app.logger)
                qb_client = QBittorrentClient(auth_manager, app.db, app.logger)
                task_id = None
                task_data_torrents = []
                results_data = {}

                if recovery_mode and existing_task:
                    app.logger.info("scanner", f"Восстановление задачи сканирования ID {existing_task['id']} для сериала {series_id}")
                    task_id = existing_task['id']
                    task_data_torrents = existing_task.get('task_data', [])
                    results_data = existing_task.get('results_data', {})
                else:
                    app.logger.info("scanner", f"Начало сканирования для series_id: {series_id}. Режим отладки: {'ВКЛ' if debug_force_replace else 'ВЫКЛ'}")
                    
                    site_key = series['site']
                    if 'anilibria.tv' in site_key:
                        site_key = 'anilibria.tv'
                    elif 'anilibria' in site_key or 'aniliberty' in site_key:
                        site_key = 'anilibria.top'
                    elif 'kinozal' in site_key:
                        site_key = 'kinozal.me'
                    elif 'astar' in site_key:
                        site_key = 'astar.bz'

                    parsers = {
                        'kinozal.me': KinozalParser(auth_manager, app.db, app.logger),
                        'anilibria.top': AnilibriaParser(app.db, app.logger),
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
                    
                    parsed_data = parser.parse_series(series['url'], last_known_torrents=active_db_torrents, debug_force_replace=debug_force_replace)

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
                        status_manager.set_status(series_id, 'scanning', False)
                        return {"success": True, "tasks_created": 0}

                    site_torrents = []
                    if series.get('quality'):
                        selected_qualities = {q.strip() for q in series['quality'].split(';') if q.strip()}
                        site_torrents = [t for t in new_or_updated_torrents if t.get('quality') in selected_qualities]
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
                        status_manager.set_status(series_id, 'scanning', False)
                        return {"success": True, "tasks_created": 0}

                    task_id = app.db.create_scan_task(series_id, torrents_to_process)
                    task_data_torrents = torrents_to_process
                    app.logger.info("scanner", f"Создана задача сканирования ID {task_id} с {len(task_data_torrents)} торрентами.")

                for index, task_item in enumerate(task_data_torrents):
                    site_torrent = task_item['site_torrent']
                    if str(index) in results_data:
                        continue
                    
                    new_hash, link_type = qb_client.add_torrent(site_torrent['link'], series['save_path'], site_torrent['torrent_id'])

                    if new_hash:
                        results_data[str(index)] = {"hash": new_hash, "link_type": link_type}
                        app.db.update_scan_task_results(task_id, results_data)
                    else:
                        app.logger.warning("scanner", f"Не удалось добавить торрент {site_torrent['torrent_id']} в рамках задачи {task_id}. Пропуск.")
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
                    
                    existing_db_entry = next((t for t in app.db.get_torrents(series_id) if t['torrent_id'] == site_torrent['torrent_id']), None)
                    if existing_db_entry:
                        # Обновляем существующую запись, делая её активной
                        app.db.update_torrent_by_id(existing_db_entry['id'], {'is_active': True, 'qb_hash': new_hash})
                    else:
                        # Добавляем новый торрент, и он ОБЯЗАТЕЛЬНО должен быть активным
                        app.db.add_torrent(series_id, site_torrent, is_active=True, qb_hash=new_hash)

                    if old_torrent_to_replace:
                        app.db.deactivate_torrent_and_clear_files(old_torrent_to_replace['id'])
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
                     status_manager.set_status(series_id, 'scanning', False)
                
                app.db.delete_scan_task(task_id)
                return {"success": True, "tasks_created": tasks_created}

        except Exception as e:
            app.logger.error("scanner", f"Ошибка в процессе сканирования для series_id {series_id}: {e}", exc_info=True)
            status_manager.set_status(series_id, 'error', True)
            return {"success": False, "error": str(e)}
        finally:
            status_manager.set_status(series_id, 'scanning', False)