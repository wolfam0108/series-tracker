from datetime import datetime, timezone
from flask import current_app as app
from auth import AuthManager
from db import Database
from qbittorrent import QBittorrentClient
from parsers.kinozal_parser import KinozalParser
from parsers.anilibria_parser import AnilibriaParser
from parsers.astar_parser import AstarParser
from parsers.anilibria_tv_parser import AnilibriaTvParser
import hashlib
import json
import time

def generate_torrent_id(link, date_time):
    """Генерирует уникальный ID для торрента на основе его ссылки и даты."""
    unique_string = f"{link}{date_time or ''}"
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

        if not recovery_mode:
            if series['state'].startswith(('scanning', 'rechecking')) or series['state'].startswith('{'):
                app.logger.warning("scanner", f"Сканирование для series_id {series_id} пропущено: процесс уже запущен (статус: {series['state']}).")
                return {"success": False, "error": f"Процесс уже запущен: {series['state']}"}

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

                parsed_data = parser.parse_series(series['url'])
                if parsed_data.get('error'):
                    raise Exception(f"Ошибка парсера: {parsed_data['error']}")
                
                all_site_torrents = []
                for t in parsed_data.get("torrents", []):
                    t["torrent_id"] = generate_torrent_id(t["link"], t.get("date_time"))
                    all_site_torrents.append(t)
                
                site_torrents = []
                if series.get('quality'):
                    selected_qualities = {q.strip() for q in series['quality'].split(';') if q.strip()}
                    site_torrents = [t for t in all_site_torrents if t.get('quality') in selected_qualities]
                    if app.debug_manager.is_debug_enabled('scanner'):
                        app.logger.debug("scanner", f"Отфильтровано {len(site_torrents)} из {len(all_site_torrents)} торрентов по качеству: {selected_qualities}")
                else:
                    site_torrents = all_site_torrents
                
                all_db_torrents = app.db.get_torrents(series_id)
                db_hashes = [t['qb_hash'] for t in all_db_torrents if t.get('qb_hash')]
                torrents_in_qb = qb_client.get_torrents_info(db_hashes) if db_hashes else []
                hashes_in_qb = {t['hash'] for t in torrents_in_qb} if torrents_in_qb else set()
                active_qb_torrents = [t for t in all_db_torrents if t.get('qb_hash') in hashes_in_qb]

                if debug_force_replace:
                    app.logger.warning("scanner", "РЕЖИМ ОТЛАДКИ: Все активные торренты будут принудительно заменены.")
                    hashes_to_delete = [t['qb_hash'] for t in active_qb_torrents]
                    if hashes_to_delete:
                        qb_client.delete_torrents(hashes_to_delete, delete_files=False)
                        for t in active_qb_torrents:
                            app.db.update_torrent_by_id(t['id'], {'is_active': False})
                    active_qb_torrents = []

                torrents_to_process = []
                site_type = 'fixed' if series['site'].startswith('astar') else 'rolling'
                if app.debug_manager.is_debug_enabled('scanner'):
                    app.logger.debug("scanner", f"Стратегия обновления для сайта {series['site']}: {site_type}")

                for site_torrent in site_torrents:
                    existing_active_entry = next((t for t in active_qb_torrents if t['torrent_id'] == site_torrent['torrent_id']), None)
                    if existing_active_entry: continue

                    old_torrent_to_replace = None
                    if site_type == 'fixed':
                        old_torrent_to_replace = next((t for t in active_qb_torrents if t.get('episodes') == site_torrent.get('episodes')), None)
                    elif site_type == 'rolling' and len(active_qb_torrents) == 1:
                        old_torrent_to_replace = active_qb_torrents[0]
                    
                    torrents_to_process.append({
                        "site_torrent": site_torrent,
                        "old_torrent_to_replace": old_torrent_to_replace
                    })
                
                if not torrents_to_process:
                    app.logger.info("scanner", "Новых торрентов для добавления не найдено.")
                    app.db.set_series_state(series_id, 'waiting', datetime.now(timezone.utc))
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
                
                try:
                    tag_for_torrent = f"scantask-{task_id}-{index}"
                    new_hash, link_type = qb_client.add_torrent(site_torrent['link'], series['save_path'], site_torrent['torrent_id'], tag=tag_for_torrent)

                    if not new_hash:
                        raise Exception("qBittorrentClient не вернул хеш.")

                    results_data[str(index)] = {"hash": new_hash, "link_type": link_type}
                    app.db.update_scan_task_results(task_id, results_data)
                    if app.debug_manager.is_debug_enabled('scanner'):
                        app.logger.debug("scanner", f"Торрент {site_torrent['torrent_id']} добавлен. Hash: {new_hash[:8]}. Результат сохранен.")

                except Exception as e:
                    app.logger.warning("scanner", f"Не удалось обработать торрент {site_torrent['torrent_id']} в рамках задачи {task_id}: {e}. Пропуск.")
                    continue

            if not results_data:
                 raise Exception("Не удалось добавить ни одного торрента из списка.")
            
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

            app.db.update_series(series_id, {'last_scan_time': datetime.now(timezone.utc)})
            _broadcast_series_update(series_id)
            
            return {"success": True, "tasks_created": tasks_created}

        except Exception as e:
            app.logger.error("scanner", f"Ошибка в процессе сканирования для series_id {series_id}: {e}", exc_info=True)
            app.db.set_series_state(series_id, 'error')
            app.db.update_series(series_id, {'last_scan_time': datetime.now(timezone.utc)})
            _broadcast_series_update(series_id)
            return {"success": False, "error": str(e)}