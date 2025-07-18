import hashlib
import re
from flask import Blueprint, jsonify, request, current_app as app

from auth import AuthManager
from renamer import Renamer
from parsers.kinozal_parser import KinozalParser
from parsers.anilibria_parser import AnilibriaParser
from parsers.astar_parser import AstarParser
from parsers.anilibria_tv_parser import AnilibriaTvParser

settings_bp = Blueprint('settings_api', __name__, url_prefix='/api')

def generate_torrent_id(link, date_time):
    unique_string = f"{link}{date_time or ''}"
    return hashlib.md5(unique_string.encode()).hexdigest()[:16]

@settings_bp.route('/auth', methods=['GET'])
def get_all_auth():
    return jsonify({
        "qbittorrent": app.db.get_auth("qbittorrent"),
        "kinozal": app.db.get_auth("kinozal"),
        "vk": app.db.get_auth("vk")
    })

@settings_bp.route('/auth', methods=['POST'])
def save_all_auth():
    data = request.get_json()
    try:
        if qb_data := data.get('qbittorrent'):
            app.db.add_auth('qbittorrent', qb_data.get('username'), qb_data.get('password'), qb_data.get('url'))
        if kinozal_data := data.get('kinozal'):
            app.db.add_auth('kinozal', kinozal_data.get('username'), kinozal_data.get('password'))
        if vk_data := data.get('vk'):
            app.db.add_auth('vk', username='vk_token', password=vk_data.get('token'))
        return jsonify({"success": True})
    except Exception as e:
        app.logger.error("auth_api", "Ошибка сохранения данных авторизации", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@settings_bp.route('/rename/preview', methods=['POST'])
def rename_preview():
    data = request.get_json()
    files = data.get('files', [])
    series_id = data.get('series_id')
    if not all([files is not None, series_id]):
        return jsonify({"error": "Отсутствуют необходимые данные (files, series_id)"}), 400
    
    series = app.db.get_series(series_id)
    if not series:
        return jsonify({"error": f"Сериал с ID {series_id} не найден"}), 404

    renamer = Renamer(app.logger, app.db)
    preview = renamer.get_rename_preview(files, series)
    return jsonify(preview)

@settings_bp.route('/parse_url', methods=['POST'])
def parse_url():
    data = request.get_json()
    url = data['url']
    try:
        domain = url.split('/')[2]
        site = re.sub(r'^(www\.)', '', domain)
        
        parser_key = site
        if 'kinozal' in site:
            parser_key = 'kinozal.me'
        elif 'astar' in site:
            parser_key = 'astar.bz'

    except IndexError:
         return jsonify({"error": "Некорректный URL"}), 400
    
    auth_manager = AuthManager(app.db, app.logger)
    parsers = {
        'kinozal.me': KinozalParser(auth_manager, app.db, app.logger),
        'anilibria.top': AnilibriaParser(app.db, app.logger),
        'anilibria.tv': AnilibriaTvParser(app.db, app.logger),
        'astar.bz': AstarParser(app.db, app.logger)
    }
    parser = parsers.get(parser_key)
    if not parser:
        return jsonify({"error": f"Указан недопустимый сайт: {site}"}), 400

    result = parser.parse_series(url)
    if result.get('error'):
        return jsonify(result), 400
    
    for torrent in result.get("torrents", []):
        link_for_id = torrent.get('raw_link_for_id_gen', torrent.get('link'))
        if link_for_id:
            torrent["torrent_id"] = generate_torrent_id(link_for_id, torrent.get("date_time"))
    
    return jsonify({"success": True, **result})

@settings_bp.route('/settings/debug_flags', methods=['GET', 'POST'])
def handle_debug_flags():
    if request.method == 'POST':
        data = request.get_json()
        module_name = data.get('module')
        enabled = data.get('enabled')
        if not module_name:
            return jsonify({"success": False, "error": "Module name not specified"}), 400
        
        key = f"debug_enabled_{module_name}"
        app.db.set_setting(key, str(enabled).lower())
        app.debug_manager._refresh_cache()
        return jsonify({"success": True})
    
    flags = app.db.get_settings_by_prefix('debug_enabled_')
    processed_flags = {
        key.replace('debug_enabled_', ''): value == 'true'
        for key, value in flags.items()
    }
    return jsonify(processed_flags)

@settings_bp.route('/settings/force_replace', methods=['GET', 'POST'])
def handle_force_replace_setting():
    if request.method == 'POST':
        data = request.get_json()
        if 'enabled' in data:
            app.db.set_setting('debug_force_replace', str(data['enabled']).lower())
        return jsonify({"success": True})
    
    enabled = app.db.get_setting('debug_force_replace', 'false') == 'true'
    return jsonify({"enabled": enabled})

@settings_bp.route('/patterns', methods=['GET', 'POST'])
def handle_patterns():
    if request.method == 'GET':
        return jsonify(app.db.get_patterns())
    if request.method == 'POST':
        data = request.get_json()
        try:
            pattern_id = app.db.add_pattern(data['name'], data['pattern'])
            return jsonify({"success": True, "id": pattern_id})
        except Exception as e:
            return jsonify({"success": False, "error": f"Ошибка добавления паттерна: {str(e)}"}), 400

@settings_bp.route('/patterns/<int:pattern_id>', methods=['PUT', 'DELETE'])
def handle_single_pattern(pattern_id):
    if request.method == 'PUT':
        data = request.get_json()
        try:
            app.db.update_pattern(pattern_id, data)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": f"Ошибка обновления паттерна: {str(e)}"}), 400
    if request.method == 'DELETE':
        try:
            app.db.delete_pattern(pattern_id)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": f"Ошибка удаления паттерна: {str(e)}"}), 400

@settings_bp.route('/patterns/reorder', methods=['POST'])
def reorder_patterns():
    ordered_ids = request.get_json()
    try:
        app.db.update_patterns_order(ordered_ids)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": f"Ошибка изменения порядка: {str(e)}"}), 400

@settings_bp.route('/patterns/test-all', methods=['POST'])
def test_all_patterns():
    data = request.get_json()
    filename = data.get('filename')
    if not filename:
        return jsonify({"error": "Отсутствует 'filename'"}), 400
        
    renamer = Renamer(app.logger, app.db)
    result = renamer.find_episode_with_db_patterns(filename)
    return jsonify({"result": result})

@settings_bp.route('/season_patterns', methods=['GET', 'POST'])
def handle_season_patterns():
    if request.method == 'GET':
        return jsonify(app.db.get_season_patterns())
    if request.method == 'POST':
        data = request.get_json()
        try:
            pattern_id = app.db.add_season_pattern(data['name'], data['pattern'])
            return jsonify({"success": True, "id": pattern_id})
        except Exception as e:
            return jsonify({"success": False, "error": f"Ошибка добавления паттерна сезона: {str(e)}"}), 400

@settings_bp.route('/season_patterns/<int:pattern_id>', methods=['PUT', 'DELETE'])
def handle_single_season_pattern(pattern_id):
    if request.method == 'PUT':
        data = request.get_json()
        try:
            app.db.update_season_pattern(pattern_id, data)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": f"Ошибка обновления паттерна сезона: {str(e)}"}), 400
    if request.method == 'DELETE':
        try:
            app.db.delete_season_pattern(pattern_id)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": f"Ошибка удаления паттерна сезона: {str(e)}"}), 400

@settings_bp.route('/season_patterns/reorder', methods=['POST'])
def reorder_season_patterns():
    ordered_ids = request.get_json()
    try:
        app.db.update_season_patterns_order(ordered_ids)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": f"Ошибка изменения порядка: {str(e)}"}), 400

@settings_bp.route('/season_patterns/test-all', methods=['POST'])
def test_all_season_patterns():
    data = request.get_json()
    filename = data.get('filename')
    if not filename:
        return jsonify({"error": "Отсутствует 'filename'"}), 400
        
    renamer = Renamer(app.logger, app.db)
    result = renamer.find_season_with_db_patterns(filename)
    return jsonify({"result": result})

@settings_bp.route('/advanced_patterns', methods=['GET', 'POST'])
def handle_advanced_patterns():
    if request.method == 'GET':
        return jsonify(app.db.get_advanced_patterns())
    if request.method == 'POST':
        data = request.get_json()
        try:
            pattern_id = app.db.add_advanced_pattern(data)
            return jsonify({"success": True, "id": pattern_id})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

@settings_bp.route('/advanced_patterns/<int:pattern_id>', methods=['PUT', 'DELETE'])
def handle_single_advanced_pattern(pattern_id):
    if request.method == 'PUT':
        data = request.get_json()
        try:
            app.db.update_advanced_pattern(pattern_id, data)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400
    if request.method == 'DELETE':
        try:
            app.db.delete_advanced_pattern(pattern_id)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

@settings_bp.route('/advanced_patterns/reorder', methods=['POST'])
def reorder_advanced_patterns():
    ordered_ids = request.get_json()
    try:
        app.db.update_advanced_patterns_order(ordered_ids)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@settings_bp.route('/advanced_patterns/test-all', methods=['POST'])
def test_all_advanced_patterns():
    data = request.get_json()
    filename = data.get('filename')
    if not filename:
        return jsonify({"error": "Отсутствует 'filename'"}), 400
    
    renamer = Renamer(app.logger, app.db)
    processed_filename = renamer._apply_advanced_patterns(filename)
    
    if processed_filename != filename:
        return jsonify({"result": f"Успех! Результат: '{processed_filename}'"})
    else:
        return jsonify({"result": "Не найдено совпадений ни одним активным правилом."})

@settings_bp.route('/quality_patterns', methods=['GET', 'POST'])
def get_quality_patterns():
    if request.method == 'GET':
        return jsonify(app.db.get_quality_patterns())
    if request.method == 'POST':
        data = request.get_json()
        try:
            pattern_id = app.db.add_quality_pattern(data['standard_value'])
            return jsonify({"success": True, "id": pattern_id})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

@settings_bp.route('/quality_patterns/<int:pattern_id>', methods=['PUT', 'DELETE'])
def update_quality_pattern(pattern_id):
    if request.method == 'PUT':
        data = request.get_json()
        try:
            app.db.update_quality_pattern(pattern_id, data)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400
    if request.method == 'DELETE':
        try:
            app.db.delete_quality_pattern(pattern_id)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

@settings_bp.route('/quality_patterns/reorder', methods=['POST'])
def reorder_quality_patterns():
    ordered_ids = request.get_json()
    try:
        app.db.update_quality_patterns_order(ordered_ids)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@settings_bp.route('/quality_patterns/<int:quality_pattern_id>/search_patterns', methods=['POST'])
def add_quality_search_pattern(quality_pattern_id):
    data = request.get_json()
    try:
        app.db.add_quality_search_pattern(quality_pattern_id, data['pattern'])
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@settings_bp.route('/quality_search_patterns/<int:search_pattern_id>', methods=['DELETE'])
def delete_quality_search_pattern(search_pattern_id):
    try:
        app.db.delete_quality_search_pattern(search_pattern_id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@settings_bp.route('/quality_patterns/test', methods=['POST'])
def test_quality_patterns():
    data = request.get_json()
    renamer = Renamer(app.logger, app.db)
    result = renamer._extract_quality(data.get('filename'))
    return jsonify({"result": result if result else "Не найдено"})

@settings_bp.route('/resolution_patterns', methods=['GET', 'POST'])
def get_resolution_patterns():
    if request.method == 'GET':
        return jsonify(app.db.get_resolution_patterns())
    if request.method == 'POST':
        data = request.get_json()
        try:
            pattern_id = app.db.add_resolution_pattern(data['standard_value'])
            return jsonify({"success": True, "id": pattern_id})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

@settings_bp.route('/resolution_patterns/<int:pattern_id>', methods=['PUT', 'DELETE'])
def update_resolution_pattern(pattern_id):
    if request.method == 'PUT':
        data = request.get_json()
        try:
            app.db.update_resolution_pattern(pattern_id, data)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400
    if request.method == 'DELETE':
        try:
            app.db.delete_resolution_pattern(pattern_id)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

@settings_bp.route('/resolution_patterns/reorder', methods=['POST'])
def reorder_resolution_patterns():
    ordered_ids = request.get_json()
    try:
        app.db.update_resolution_patterns_order(ordered_ids)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@settings_bp.route('/resolution_patterns/<int:resolution_pattern_id>/search_patterns', methods=['POST'])
def add_resolution_search_pattern(resolution_pattern_id):
    data = request.get_json()
    try:
        app.db.add_resolution_search_pattern(resolution_pattern_id, data['pattern'])
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@settings_bp.route('/resolution_search_patterns/<int:search_pattern_id>', methods=['DELETE'])
def delete_resolution_search_pattern(search_pattern_id):
    try:
        app.db.delete_resolution_search_pattern(search_pattern_id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400
        
@settings_bp.route('/resolution_patterns/test', methods=['POST'])
def test_resolution_patterns():
    data = request.get_json()
    renamer = Renamer(app.logger, app.db)
    result = renamer._extract_resolution(data.get('filename'))
    return jsonify({"result": result if result else "Не найдено"})