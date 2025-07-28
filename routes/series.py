# Файл: series.py

import hashlib
import os
import json
from flask import Blueprint, jsonify, request, current_app as app

from auth import AuthManager
from qbittorrent import QBittorrentClient
from renamer import Renamer
from scanner import perform_series_scan, generate_media_item_id
from file_cache import delete_from_cache
from rule_engine import RuleEngine
from scrapers.vk_scraper import VKScraper
from smart_collector import SmartCollector
from filename_formatter import FilenameFormatter


series_bp = Blueprint('series_api', __name__, url_prefix='/api/series')

def generate_torrent_id(link, date_time):
    unique_string = f"{link}{date_time or ''}"
    return hashlib.md5(unique_string.encode()).hexdigest()[:16]

@series_bp.route('', methods=['GET'])
def get_series():
    series_list = app.db.get_all_series()
    for s in series_list:
        if s.get('last_scan_time'):
            s['last_scan_time'] = s['last_scan_time'].isoformat()
    return jsonify(series_list)

@series_bp.route('', methods=['POST'])
def add_series():
    data = request.get_json()
    app.logger.info("series_api", f"Добавление нового сериала: {data.get('name')}")
    series_id = app.db.add_series(data)
    
    if data.get('source_type', 'torrent') == 'torrent':
        if torrents := data.get('torrents'):
            for torrent in torrents:
                if torrent.get('link'):
                    app.db.add_torrent(series_id, torrent)
    
    new_series_data = app.db.get_series(series_id)
    if new_series_data:
        if new_series_data.get('last_scan_time'):
            new_series_data['last_scan_time'] = new_series_data['last_scan_time'].isoformat()
        app.sse_broadcaster.broadcast('series_added', new_series_data)

    return jsonify({"success": True, "series_id": series_id})

@series_bp.route('/<int:series_id>', methods=['GET'])
def get_series_details(series_id):
    series = app.db.get_series(series_id)
    if series and series.get('last_scan_time'):
        series['last_scan_time'] = series['last_scan_time'].isoformat()
    return jsonify(series) if series else (jsonify({"error": "Сериал не найден"}), 404)

@series_bp.route('/<int:series_id>/composition', methods=['GET'])
def get_series_composition(series_id):
    """
    Универсальный эндпоинт для получения композиции. Принимает параметр ?refresh=true
    для запуска полного обновления, а также выполняет ручную синхронизацию файлов.
    """
    try:
        series = app.db.get_series(series_id)
        if not series:
            return jsonify({"error": "Сериал не найден"}), 404
        if series.get('source_type') != 'vk_video':
            return jsonify([]), 200
        
        # Вызываем публичный метод агента для немедленной синхронизации файлов ("ручной" запуск).
        app.scanner_agent.sync_single_series_filesystem(series_id)
        
        force_refresh = request.args.get('refresh', 'false').lower() == 'true'

        if force_refresh:
            app.logger.info("series_api", f"Запрошено полное обновление композиции для series_id: {series_id}")
            # Этап 1: Сбор и сохранение кандидатов
            channel_url, query = series['url'].split('|')
            search_mode = series.get('vk_search_mode', 'search')
            scraper = VKScraper(app.db, app.logger)
            scraped_videos = scraper.scrape_video_data(channel_url, query, search_mode)

            engine = RuleEngine(app.db, app.logger)
            profile_id = series.get('parser_profile_id')
            if not profile_id:
                raise ValueError("Для сериала не назначен профиль правил парсера.")
            processed_videos = engine.process_videos(profile_id, scraped_videos)

            candidates_to_save = []
            for video_data in processed_videos:
                extracted = video_data.get('result', {}).get('extracted', {})
                if extracted.get('episode') is None and extracted.get('start') is None: continue
                pub_date = video_data.get('source_data', {}).get('publication_date')
                url = video_data.get('source_data', {}).get('url')
                if not pub_date or not url: continue
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

            # Этап 2: Запуск SmartCollector для обновления plan_status в БД
            collector = SmartCollector(app.logger, app.db)
            collector.collect(series_id)
            
            # После полного обновления сразу синхронизируем статусы
            app.status_manager.sync_vk_statuses(series_id)

        # Этап 4: Возвращаем актуальные данные из БД
        db_items = app.db.get_media_items_for_series(series_id)
        reconstructed_plan = []
        for item in db_items:
            extracted_data = {'season': item.get('season'), 'voiceover': item.get('voiceover_tag')}
            if item.get('episode_end'):
                extracted_data['start'] = item.get('episode_start')
                extracted_data['end'] = item.get('episode_end')
            else:
                extracted_data['episode'] = item.get('episode_start')

            reconstructed_item = {
                'source_data': {
                    'title': item.get('final_filename') or item.get('source_url'),
                    'url': item.get('source_url'),
                    'publication_date': item.get('publication_date').isoformat() if item.get('publication_date') else None,
                    'resolution': item.get('resolution')
                },
                'result': {'extracted': extracted_data},
                'plan_status': item.get('plan_status'),
                'status': item.get('status'),
                'unique_id': item.get('unique_id'),
                'slicing_status': item.get('slicing_status', 'none'),
                'is_ignored_by_user': item.get('is_ignored_by_user', False),
            }
            reconstructed_plan.append(reconstructed_item)
        
        return jsonify(reconstructed_plan)

    except Exception as e:
        app.logger.error("series_api", f"Ошибка при построении композиции для series_id {series_id}: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@series_bp.route('/<int:series_id>', methods=['POST'])
def update_series(series_id):
    data = request.get_json()
    app.db.update_series(series_id, data)
    _broadcast_series_update(series_id, 'series_updated')
    return jsonify({"success": True})

@series_bp.route('/<int:series_id>/toggle_auto_scan', methods=['POST'])
def toggle_auto_scan(series_id):
    data = request.get_json()
    enabled = data.get('enabled')
    if enabled is None:
        return jsonify({"success": False, "error": "Параметр 'enabled' не указан"}), 400
    
    app.db.update_series(series_id, {'auto_scan_enabled': bool(enabled)})
    _broadcast_series_update(series_id, 'series_updated')
    return jsonify({"success": True})

@series_bp.route('/<int:series_id>', methods=['DELETE'])
def delete_series(series_id):
    delete_from_qb = request.args.get('delete_from_qb', 'false').lower() == 'true'
    
    torrents_to_delete = app.db.get_torrents(series_id) 

    if delete_from_qb:
        app.logger.warning("routes", f"Удаление записей торрентов для сериала {series_id} из qBittorrent.")
        hashes_to_delete = [t['qb_hash'] for t in torrents_to_delete if t.get('qb_hash')]
        if hashes_to_delete:
            qb_client = QBittorrentClient(AuthManager(app.db, app.logger), app.db, app.logger)
            qb_client.delete_torrents(hashes_to_delete, delete_files=False)
            app.logger.info("routes", f"Удалено {len(hashes_to_delete)} записей торрентов из qBittorrent для сериала {series_id}.")

    if torrents_to_delete:
        app.logger.info("routes", f"Очистка кэша .torrent файлов для сериала {series_id}.")
        for torrent in torrents_to_delete:
            if torrent.get('torrent_id'):
                delete_from_cache(torrent['torrent_id'])

    app.db.delete_series(series_id)
    app.sse_broadcaster.broadcast('series_deleted', {'id': series_id})
    return jsonify({"success": True})
    
@series_bp.route('/<int:series_id>/state', methods=['POST'])
def set_series_state_route(series_id):
    data = request.get_json()
    state_list = data.get('state', [])
    
    is_viewing = 'viewing' in state_list
    # Напрямую вызываем метод БД
    app.db.set_viewing_status(series_id, is_viewing)
    # И просим StatusManager просто обновить UI
    app.status_manager._update_and_broadcast(series_id)
    
    return jsonify({"success": True})

@series_bp.route('/<int:series_id>/viewing_heartbeat', methods=['POST'])
def viewing_heartbeat(series_id):
    """Обновляет временную метку, подтверждая, что окно статуса все еще открыто."""
    app.db.set_viewing_status(series_id, True) # Просто обновляем время на текущее
    return jsonify({"success": True})

@series_bp.route('/<int:series_id>/scan', methods=['POST'])
def scan_series_route(series_id):
    debug_force_replace = app.db.get_setting('debug_force_replace', 'false') == 'true'
    
    result = perform_series_scan(series_id, app.status_manager, debug_force_replace)
    
    if result["success"]:
        return jsonify(result)
    else:
        status_code = 409 if "уже запущен" in result.get("error", "") else 500
        return jsonify(result), status_code

@series_bp.route('/<int:series_id>/torrents', methods=['GET'])
def get_series_torrents(series_id):
    torrents = app.db.get_torrents(series_id, is_active=True)
    return jsonify(torrents)

@series_bp.route('/<int:series_id>/torrents/history', methods=['GET'])
def get_series_torrents_history(series_id):
    all_torrents = app.db.get_torrents(series_id)
    return jsonify(all_torrents)

@series_bp.route('/<int:series_id>/qb_info', methods=['GET'])
def get_series_qb_info(series_id):
    torrents_in_db = [t for t in app.db.get_torrents(series_id) if t.get('qb_hash')]
    if not torrents_in_db:
        return jsonify([])
        
    qb_hashes = [t['qb_hash'] for t in torrents_in_db]
    
    qb_client = QBittorrentClient(AuthManager(app.db, app.logger), app.db, app.logger)
    all_torrents_info = qb_client.get_torrents_info(qb_hashes)
    
    if all_torrents_info is None:
        return jsonify({"error": "Не удалось получить информацию из qBittorrent"}), 500
        
    results = []
    for db_torrent in torrents_in_db:
        qb_info = next((info for info in all_torrents_info if info['hash'] == db_torrent['qb_hash']), None)
        if qb_info:
            files = qb_client.get_torrent_files_by_hash(db_torrent['qb_hash'])
            results.append({
                "torrent_id": db_torrent['torrent_id'], "qb_hash": db_torrent['qb_hash'], "progress": qb_info.get("progress", 0),
                "state": qb_info.get("state", "unknown"), "file_paths": files or [] 
            })
    return jsonify(results)

@series_bp.route('/<int:series_id>/torrents/<string:qb_hash>/rename', methods=['POST'])
def rename_torrent_files(series_id, qb_hash):
    series = app.db.get_series(series_id)
    if not series:
        return jsonify({"success": False, "error": "Сериал не найден"}), 404

    qb_client = QBittorrentClient(AuthManager(app.db, app.logger), app.db, app.logger)
    files = qb_client.get_torrent_files_by_hash(qb_hash)
    if files is None:
        return jsonify({"success": False, "error": "Не удалось получить список файлов из qBittorrent"}), 500

    renamer = Renamer(app.logger, app.db)
    preview_list = renamer.get_rename_preview(files, series)

    errors = []
    success_count = 0
    for item in preview_list:
        original_path = item.get('original')
        new_path = item.get('renamed')
        if new_path and "Ошибка" not in new_path and original_path != new_path:
            if qb_client.rename_file(qb_hash, original_path, new_path):
                success_count += 1
            else:
                errors.append(f"Не удалось переименовать '{original_path}'")
    
    if errors:
        return jsonify({"success": False, "error": f"Переименовано {success_count} файлов. Ошибки: {'; '.join(errors)}"}), 500
        
    return jsonify({"success": True, "message": f"Успешно переименовано {success_count} файлов."})

@series_bp.route('/<int:series_id>/ignored-seasons', methods=['POST'])
def update_ignored_seasons(series_id):
    data = request.get_json()
    seasons = data.get('seasons')
    if seasons is None:
        return jsonify({"success": False, "error": "Параметр 'seasons' не указан"}), 400

    try:
        app.db.update_series_ignored_seasons(series_id, seasons)
        return jsonify({"success": True})
    except Exception as e:
        app.logger.error("series_api", f"Ошибка обновления игнорируемых сезонов для series_id {series_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500
    
@series_bp.route('/<int:series_id>/sliced-files', methods=['GET'])
def get_sliced_files_for_series(series_id):
    try:
        items = app.db.get_all_sliced_files_for_series(series_id)
        
        media_items_cache = {}
        for item in items:
            uid = item.get('source_media_item_unique_id')
            if uid not in media_items_cache:
                media_items_cache[uid] = app.db.get_media_item_by_uid(uid)
            
            parent_item = media_items_cache.get(uid)
            if parent_item:
                item['parent_filename'] = parent_item.get('final_filename', 'Источник не найден')
                item['season'] = parent_item.get('season', 1)
            else:
                item['parent_filename'] = 'Источник не найден'
                item['season'] = 1
        
        return jsonify(items)
    except Exception as e:
        app.logger.error("series_api", f"Ошибка получения sliced_files для series_id {series_id}: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500
    
@series_bp.route('/<int:series_id>/vk-quality-priority', methods=['PUT'])
def set_vk_quality_priority(series_id):
    data = request.get_json()
    priority_list = data.get('priority')
    
    if not isinstance(priority_list, list):
        return jsonify({"success": False, "error": "Приоритет должен быть списком"}), 400

    try:
        app.db.update_series(series_id, {'vk_quality_priority': json.dumps(priority_list)})
        return jsonify({"success": True, "message": "Приоритет качества сохранен."})
    except Exception as e:
        app.logger.error("series_api", f"Ошибка обновления vk_quality_priority для series {series_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@series_bp.route('/active_torrents', methods=['GET'])
def get_active_torrents_monitoring():
    """Возвращает список всех активных торрентов для мониторинга в UI."""
    try:
        tasks = app.db.get_all_active_torrent_tasks()
        return jsonify(tasks)
    except Exception as e:
        app.logger.error("series_api", f"Ошибка получения задач мониторинга торрентов: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

def _broadcast_series_update(series_id, event_name):
    series_data = app.db.get_series(series_id)
    if series_data:
        if series_data.get('last_scan_time'):
            series_data['last_scan_time'] = series_data['last_scan_time'].isoformat()
        app.sse_broadcaster.broadcast(event_name, series_data)