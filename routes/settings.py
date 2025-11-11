import hashlib
import re
import json
from flask import Blueprint, jsonify, request, current_app as app

from auth import AuthManager
from parsers.kinozal_parser import KinozalParser
from parsers.anilibria_parser import AnilibriaParser
from parsers.astar_parser import AstarParser
from parsers.anilibria_tv_parser import AnilibriaTvParser
from parsers.rutracker_parser import RuTrackerParser
from utils.tracker_resolver import TrackerResolver

settings_bp = Blueprint('settings_api', __name__, url_prefix='/api')

def generate_torrent_id(link, date_time):
    unique_string = f"{link}{date_time or ''}"
    return hashlib.md5(unique_string.encode()).hexdigest()[:16]

LOGGING_MODULES = {
    "Ядро и Утилиты": [
        {'name': 'db', 'description': 'Операции с базой данных (миграции, ошибки).'},
        {'name': 'auth', 'description': 'Этапы аутентификации в qBittorrent и на сайтах.'},
        {'name': 'qbittorrent', 'description': 'Все взаимодействия с qBittorrent API.'},
        {'name': 'file_cache', 'description': 'Операции с кэшем .torrent файлов.'},
        {'name': 'chapter_parser', 'description': 'Процесс получения глав из видео через yt-dlp.'},
    ],
    "Агенты и Сканер": [
        {'name': 'scanner', 'description': 'Каждый этап сканирования сериала.'},
        {'name': 'agent', 'description': 'Жизненный цикл обработки торрента.'},
        {'name': 'monitoring_agent', 'description': 'Работа в фоновом режиме (плановые сканы, обновления).'},
        {'name': 'downloader_agent', 'description': 'Управление очередью и загрузкой видео.'},
    ],
    "API и Обработка запросов": [
        {'name': 'series_api', 'description': 'Запросы на добавление/изменение сериалов.'},
        {'name': 'parser_api', 'description': 'Работа API правил парсера и скрапинга VK.'},
        {'name': 'media_api', 'description': 'Ошибки при получении медиа-элементов и глав.'},
    ],
    "Парсеры и Обработчики данных": [
        {'name': 'vk_scraper', 'description': 'Получение данных из VK (ID канала, поиск видео).'},
        {'name': 'kinozal_parser', 'description': 'Парсинг Kinozal.'},
        {'name': 'anilibria_parser', 'description': 'Парсинг Anilibria.'},
        {'name': 'anilibria_parser_debug', 'description': 'Детальная отладка парсера Anilibria (время).'},
        {'name': 'anilibria_tv_parser', 'description': 'Парсинг Anilibria.TV.'},
        {'name': 'astar_parser', 'description': 'Парсинг Astar.'},
        {'name': 'rutracker_parser', 'description': 'Парсинг RuTracker.'},
    ]
}
FILE_DUMP_FLAGS = [
    {'name': 'save_html_kinozal', 'description': 'Kinozal (HTML)'},
    {'name': 'save_html_anilibria', 'description': 'Anilibria (HTML)'},
    {'name': 'save_html_anilibria_tv', 'description': 'Anilibria.TV (HTML)'},
    {'name': 'save_html_astar', 'description': 'Astar.bz (HTML)'},
    {'name': 'save_html_rutracker', 'description': 'RuTracker (HTML)'},
    {'name': 'save_json_vk_scraper', 'description': 'VK Scraper (JSON)'}
]

@settings_bp.route('/auth', methods=['GET'])
def get_all_auth():
    return jsonify({
        "qbittorrent": app.db.get_auth("qbittorrent"),
        "kinozal": app.db.get_auth("kinozal"),
        "vk": app.db.get_auth("vk"),
        "rutracker": app.db.get_auth("rutracker")
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
        if rutracker_data := data.get('rutracker'):
            app.db.add_auth('rutracker', rutracker_data.get('username'), rutracker_data.get('password'))
        return jsonify({"success": True})
    except Exception as e:
        app.logger.error("auth_api", "Ошибка сохранения данных авторизации", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@settings_bp.route('/parse_url', methods=['POST'])
def parse_url():
    data = request.get_json()
    url = data['url']
    
    try:
        auth_manager = AuthManager(app.db, app.logger)

        resolver = TrackerResolver(app.db)
        tracker_info = resolver.get_tracker_by_url(url)
        
        if not tracker_info:
            return jsonify({"error": f"Не удалось определить трекер для URL: {url}"}), 400

        parser_class_name = tracker_info['parser_class']
        parser_classes = {
            'KinozalParser': KinozalParser,
            'AnilibriaParser': AnilibriaParser,
            'AnilibriaTvParser': AnilibriaTvParser,
            'AstarParser': AstarParser,
            'RuTrackerParser': RuTrackerParser
        }
        
        parser_class = parser_classes.get(parser_class_name)
        if not parser_class:
            return jsonify({"error": f"Парсер с классом '{parser_class_name}' не найден"}), 500
        
        # Создаем экземпляр парсера, УЧИТЫВАЯ РАЗНЫЕ АРГУМЕНТЫ
        if parser_class_name in ['KinozalParser', 'RuTrackerParser']:
            parser = parser_class(auth_manager, app.db, app.logger)
        else:
            parser = parser_class(app.db, app.logger)

    except Exception as e:
         return jsonify({"error": f"Ошибка при инициализации парсера: {e}"}), 500

    # Запускаем парсинг
    result = parser.parse_series(url)
    if result.get('error'):
        return jsonify(result), 400
    
    # Генерируем ID для найденных торрентов
    for torrent in result.get("torrents", []):
        link_for_id = torrent.get('raw_link_for_id_gen', torrent.get('link'))
        if link_for_id:
            torrent["torrent_id"] = generate_torrent_id(link_for_id, torrent.get("date_time"))
    
    # Добавляем в ответ информацию о трекере для UI
    result['tracker_info'] = tracker_info
    
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
    
    saved_flags = app.db.get_settings_by_prefix('debug_enabled_')
    
    logging_structure = json.loads(json.dumps(LOGGING_MODULES))
    for group in logging_structure:
        for module in logging_structure[group]:
            key = f"debug_enabled_{module['name']}"
            module['enabled'] = saved_flags.get(key, 'false') == 'true'

    file_dump_structure = json.loads(json.dumps(FILE_DUMP_FLAGS))
    for flag in file_dump_structure:
        key = f"debug_enabled_{flag['name']}"
        flag['enabled'] = saved_flags.get(key, 'false') == 'true'
            
    return jsonify({
        "logging_modules": logging_structure,
        "file_dump_flags": file_dump_structure
    })

@settings_bp.route('/settings/force_replace', methods=['GET', 'POST'])
def handle_force_replace_setting():
    if request.method == 'POST':
        data = request.get_json()
        if 'enabled' in data:
            app.db.set_setting('debug_force_replace', str(data['enabled']).lower())
        return jsonify({"success": True})
    
    enabled = app.db.get_setting('debug_force_replace', 'false') == 'true'
    return jsonify({"enabled": enabled})

@settings_bp.route('/settings/parallel_downloads', methods=['GET', 'POST'])
def handle_parallel_downloads():
    if request.method == 'POST':
        data = request.get_json()
        if 'value' in data:
            app.db.set_setting('max_parallel_downloads', str(data['value']))
        return jsonify({"success": True})
    
    value = app.db.get_setting('max_parallel_downloads', 2)
    return jsonify({"value": int(value)})

@settings_bp.route('/settings/less_strict_scan', methods=['GET', 'POST'])
def handle_less_strict_scan_setting():
    setting_key = 'debug_less_strict_scan'
    if request.method == 'POST':
        data = request.get_json()
        if 'enabled' in data:
            app.db.set_setting(setting_key, str(data['enabled']).lower())
        return jsonify({"success": True})
    
    enabled = app.db.get_setting(setting_key, 'false') == 'true'
    return jsonify({"enabled": enabled})

@settings_bp.route('/settings/slicing_delete_source', methods=['GET', 'POST'])
def handle_slicing_delete_source():
    setting_key = 'slicing_delete_source_file'
    if request.method == 'POST':
        data = request.get_json()
        if 'enabled' in data:
            app.db.set_setting(setting_key, str(data['enabled']).lower())
        return jsonify({"success": True})
    
    enabled = app.db.get_setting(setting_key, 'false') == 'true'
    return jsonify({"enabled": enabled})