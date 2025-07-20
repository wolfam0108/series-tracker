import hashlib
import os
from flask import Blueprint, jsonify, request, current_app as app

from auth import AuthManager
from qbittorrent import QBittorrentClient
from renamer import Renamer
from scanner import perform_series_scan, generate_media_item_id
from file_cache import delete_from_cache
from rule_engine import RuleEngine
from scrapers.vk_scraper import VKScraper
from smart_collector import SmartCollector


series_bp = Blueprint('series_api', __name__, url_prefix='/api/series')

def generate_torrent_id(link, date_time):
    unique_string = f"{link}{date_time or ''}"
    return hashlib.md5(unique_string.encode()).hexdigest()[:16]

def _broadcast_series_update(series_id, event_type):
    series_data = app.db.get_series(series_id)
    if series_data:
        if series_data.get('last_scan_time'):
            series_data['last_scan_time'] = series_data['last_scan_time'].isoformat()
        app.sse_broadcaster.broadcast(event_type, series_data)

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
    Эндпоинт для построения и получения "умного" плана загрузки для VK-сериалов,
    обогащенного локальным статусом каждого файла.
    """
    series = app.db.get_series(series_id)
    if not series:
        return jsonify({"error": "Сериал не найден"}), 404

    if series.get('source_type') != 'vk_video':
        return jsonify([]), 200

    try:
        channel_url, query = series['url'].split('|')
        scraper = VKScraper(app.db, app.logger)
        scraped_videos = scraper.scrape_video_data(channel_url, query)

        engine = RuleEngine(app.db, app.logger)
        profile_id = series.get('parser_profile_id')
        if not profile_id:
            return jsonify({"error": "Для сериала не назначен профиль правил парсера."}), 400
        processed_videos = engine.process_videos(profile_id, scraped_videos)

        collector = SmartCollector(app.logger)
        download_plan = collector.collect(processed_videos)
        
        for item in download_plan:
            pub_date = item.get('source_data', {}).get('publication_date')
            url = item.get('source_data', {}).get('url')
            
            item['local_status'] = 'pending'

            if pub_date and url:
                unique_id = generate_media_item_id(url, pub_date, series_id)
                item['unique_id'] = unique_id
                
                db_item = app.db.get_media_item_by_uid(unique_id)
                if db_item and db_item.get('final_filename'):
                    if os.path.exists(db_item['final_filename']):
                        item['local_status'] = 'completed'
                
                item['source_data']['publication_date'] = pub_date.isoformat()
        
        return jsonify(download_plan)
        
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
    app.db.set_series_state(series_id, data.get('state'))
    _broadcast_series_update(series_id, 'series_updated')
    return jsonify({"success": True})

@series_bp.route('/<int:series_id>/scan', methods=['POST'])
def scan_series_route(series_id):
    debug_force_replace = app.db.get_setting('debug_force_replace', 'false') == 'true'
    
    result = perform_series_scan(series_id, debug_force_replace)
    
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
    """Возвращает все нарезанные файлы для указанного сериала."""
    try:
        items = app.db.get_all_sliced_files_for_series(series_id)
        return jsonify(items)
    except Exception as e:
        app.logger.error("series_api", f"Ошибка получения sliced_files для series_id {series_id}: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500