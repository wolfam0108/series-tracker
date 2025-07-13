import hashlib
import json
import re
from flask import Blueprint, jsonify, request, Response, send_from_directory, current_app as app

# Импорты из других наших модулей
from parsers.kinozal_parser import KinozalParser
from parsers.anilibria_parser import AnilibriaParser
from parsers.astar_parser import AstarParser
from parsers.anilibria_tv_parser import AnilibriaTvParser
from qbittorrent import QBittorrentClient
from auth import AuthManager
from renamer import Renamer
from scanner import perform_series_scan
from file_cache import delete_from_cache

# Создаем единую функцию для инициализации всех маршрутов
def init_routes(app):
    # Создаем чертежи ВНУТРИ функции. Теперь они не глобальные.
    main_bp = Blueprint('main', __name__)
    api_bp = Blueprint('api', __name__, url_prefix='/api')

    # Обертка для трансляции обновлений сериалов
    def broadcast_series_update(series_id, event_type):
        series_data = app.db.get_series(series_id)
        if series_data:
            if series_data.get('last_scan_time'):
                series_data['last_scan_time'] = series_data['last_scan_time'].isoformat()
            # Для доступа к sse_broadcaster используем app из аргумента функции
            app.sse_broadcaster.broadcast(event_type, series_data)

    def generate_torrent_id(link, date_time):
        unique_string = f"{link}{date_time or ''}"
        return hashlib.md5(unique_string.encode()).hexdigest()[:16]

    # --- Все маршруты теперь используют локальные main_bp и api_bp ---

    @main_bp.route('/')
    def index():
        return send_from_directory(app.template_folder, 'index.html')

    @api_bp.route('/stream')
    def stream():
        def event_stream():
            scanner_status = app.scanner_agent.get_status()
            yield f"event: scanner_status_update\ndata: {json.dumps(scanner_status)}\n\n"
            
            q = app.sse_broadcaster.subscribe()
            try:
                while True:
                    message = q.get()
                    yield message
            except GeneratorExit:
                app.sse_broadcaster.unsubscribe(q)
        return Response(event_stream(), mimetype='text/event-stream')

    @api_bp.route('/database/clear', methods=['POST'])
    def clear_database():
        app.logger.info("database", "Получен запрос на полную очистку БД")
        try:
            app.db.clear_all_data_except_auth()
            return jsonify({"success": True, "message": "База данных успешно очищена."})
        except Exception as e:
            app.logger.error("database", f"Ошибка при очистке базы данных: {e}", exc_info=True)
            return jsonify({"success": False, "error": f"Ошибка на сервере: {e}"}), 500

    @api_bp.route('/database/tables', methods=['GET'])
    def get_db_tables():
        try:
            tables = app.db.get_table_names()
            safe_tables = [t for t in tables if t != 'auth']
            return jsonify(safe_tables)
        except Exception as e:
            app.logger.error("database_api", f"Ошибка получения списка таблиц: {e}", exc_info=True)
            return jsonify({"success": False, "error": "Не удалось получить список таблиц"}), 500

    @api_bp.route('/database/clear_table', methods=['POST'])
    def clear_table():
        data = request.get_json()
        table_name = data.get('table_name')
        if not table_name:
            return jsonify({"success": False, "error": "Имя таблицы не указано"}), 400
        
        app.logger.warning("database_api", f"Получен запрос на очистку таблицы: '{table_name}'")
        try:
            success = app.db.clear_table(table_name)
            if success:
                return jsonify({"success": True, "message": f"Таблица '{table_name}' успешно очищена."})
            else:
                return jsonify({"success": False, "error": f"Не удалось очистить таблицу '{table_name}'."}), 500
        except Exception as e:
            app.logger.error("database_api", f"Критическая ошибка при очистке таблицы '{table_name}': {e}", exc_info=True)
            return jsonify({"success": False, "error": f"Ошибка на сервере: {e}"}), 500

    @api_bp.route('/auth', methods=['GET'])
    def get_all_auth():
        return jsonify({
            "qbittorrent": app.db.get_auth("qbittorrent"),
            "kinozal": app.db.get_auth("kinozal")
        })

    @api_bp.route('/auth', methods=['POST'])
    def save_all_auth():
        data = request.get_json()
        try:
            if qb_data := data.get('qbittorrent'):
                app.db.add_auth('qbittorrent', qb_data.get('username'), qb_data.get('password'), qb_data.get('url'))
            if kinozal_data := data.get('kinozal'):
                app.db.add_auth('kinozal', kinozal_data.get('username'), kinozal_data.get('password'))
            return jsonify({"success": True})
        except Exception as e:
            app.logger.error("auth_api", "Ошибка сохранения данных авторизации", exc_info=True)
            return jsonify({"success": False, "error": str(e)}), 500

    @api_bp.route('/series', methods=['GET'])
    def get_series():
        series_list = app.db.get_all_series()
        for s in series_list:
            if s.get('last_scan_time'):
                s['last_scan_time'] = s['last_scan_time'].isoformat()
        return jsonify(series_list)

    @api_bp.route('/series', methods=['POST'])
    def add_series():
        data = request.get_json()
        app.logger.info("series_api", f"Добавление нового сериала: {data.get('name')}")
        series_id = app.db.add_series(data)
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

    @api_bp.route('/series/<int:series_id>', methods=['GET'])
    def get_series_details(series_id):
        series = app.db.get_series(series_id)
        if series and series.get('last_scan_time'):
            series['last_scan_time'] = series['last_scan_time'].isoformat()
        return jsonify(series) if series else (jsonify({"error": "Сериал не найден"}), 404)

    @api_bp.route('/series/<int:series_id>', methods=['POST'])
    def update_series(series_id):
        data = request.get_json()
        app.db.update_series(series_id, data)
        broadcast_series_update(series_id, 'series_updated')
        return jsonify({"success": True})
        
    @api_bp.route('/series/<int:series_id>/toggle_auto_scan', methods=['POST'])
    def toggle_auto_scan(series_id):
        data = request.get_json()
        enabled = data.get('enabled')
        if enabled is None:
            return jsonify({"success": False, "error": "Параметр 'enabled' не указан"}), 400
        
        app.db.update_series(series_id, {'auto_scan_enabled': bool(enabled)})
        broadcast_series_update(series_id, 'series_updated')
        return jsonify({"success": True})


    @api_bp.route('/series/<int:series_id>', methods=['DELETE'])
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
        
    @api_bp.route('/series/<int:series_id>/state', methods=['POST'])
    def set_series_state_route(series_id):
        data = request.get_json()
        app.db.set_series_state(series_id, data.get('state'))
        broadcast_series_update(series_id, 'series_updated')
        return jsonify({"success": True})

    @api_bp.route('/series/<int:series_id>/scan', methods=['POST'])
    def scan_series_route(series_id):
        debug_force_replace = app.db.get_setting('debug_force_replace', 'false') == 'true'
        
        result = perform_series_scan(series_id, debug_force_replace)
        
        if result["success"]:
            return jsonify(result)
        else:
            status_code = 409 if "уже запущен" in result.get("error", "") else 500
            return jsonify(result), status_code

    @api_bp.route('/series/<int:series_id>/torrents', methods=['GET'])
    def get_series_torrents(series_id):
        torrents = app.db.get_torrents(series_id, is_active=True)
        return jsonify(torrents)
    
    @api_bp.route('/series/<int:series_id>/torrents/history', methods=['GET'])
    def get_series_torrents_history(series_id):
        all_torrents = app.db.get_torrents(series_id)
        return jsonify(all_torrents)

    @api_bp.route('/series/<int:series_id>/qb_info', methods=['GET'])
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

    @api_bp.route('/series/<int:series_id>/torrents/<string:qb_hash>/rename', methods=['POST'])
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
    
    @api_bp.route('/rename/preview', methods=['POST'])
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

    @api_bp.route('/logs', methods=['GET'])
    def get_logs():
        return jsonify(app.db.get_logs(group=request.args.get('group'), level=request.args.get('level')))
    
    @api_bp.route('/parse_url', methods=['POST'])
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
            'aniliberty.top': AnilibriaParser(app.db, app.logger),
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
    
    @api_bp.route('/agent/queue', methods=['GET'])
    def get_agent_queue():
        if not hasattr(app, 'agent'): return jsonify([])
        return jsonify(app.agent.get_queue_info())

    @api_bp.route('/agent/reset', methods=['POST'])
    def reset_agent():
        app.logger.info("agent_api", "Получен запрос на сброс состояния агента и зависших задач.")
        if hasattr(app, 'agent'):
            app.agent.clear_queue()
        
        stuck_states = ['scanning', 'rechecking', '{"%']
        reset_count = app.db.reset_stuck_series_states(stuck_states)
        
        all_series = app.db.get_all_series()
        for s in all_series:
            broadcast_series_update(s['id'], 'series_updated')

        app.logger.info("agent_api", f"Сброс завершен. Очищена очередь агента, сброшено {reset_count} статусов сериалов в БД.")
        return jsonify({"success": True, "message": f"Очередь очищена, статусы {reset_count} сериалов сброшены."})
        
    @api_bp.route('/scanner/status', methods=['GET'])
    def get_scanner_status():
        return jsonify(app.scanner_agent.get_status())

    @api_bp.route('/scanner/settings', methods=['POST'])
    def update_scanner_settings():
        data = request.get_json()
        if 'enabled' in data:
            app.db.set_setting('scanner_agent_enabled', str(data['enabled']).lower())
        if 'interval' in data:
            app.db.set_setting('scan_interval_minutes', str(data['interval']))
        
        if 'interval' in data and app.scanner_agent.get_status()['scanner_enabled']:
             app.scanner_agent.trigger_scan_all()

        return jsonify({"success": True})

    @api_bp.route('/scanner/scan_all', methods=['POST'])
    def scan_all_now():
        data = request.get_json() or {}
        debug_force_replace = data.get('debug_force_replace', False)

        status = app.scanner_agent.get_status()
        if status['is_scanning']:
            return jsonify({"success": False, "error": "Сканирование уже запущено."}), 409
        
        app.scanner_agent.trigger_scan_all(debug_force_replace=debug_force_replace)
        return jsonify({"success": True, "message": "Сканирование всех сериалов запущено."})

    @api_bp.route('/settings/debug_flags', methods=['GET', 'POST'])
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

    @api_bp.route('/settings/force_replace', methods=['GET', 'POST'])
    def handle_force_replace_setting():
        if request.method == 'POST':
            data = request.get_json()
            if 'enabled' in data:
                app.db.set_setting('debug_force_replace', str(data['enabled']).lower())
            return jsonify({"success": True})
        
        enabled = app.db.get_setting('debug_force_replace', 'false') == 'true'
        return jsonify({"enabled": enabled})

    @api_bp.route('/patterns', methods=['GET'])
    def get_patterns():
        return jsonify(app.db.get_patterns())

    @api_bp.route('/patterns', methods=['POST'])
    def add_pattern():
        data = request.get_json()
        try:
            pattern_id = app.db.add_pattern(data['name'], data['pattern'])
            return jsonify({"success": True, "id": pattern_id})
        except Exception as e:
            return jsonify({"success": False, "error": f"Ошибка добавления паттерна: {str(e)}"}), 400

    @api_bp.route('/patterns/<int:pattern_id>', methods=['PUT'])
    def update_pattern(pattern_id):
        data = request.get_json()
        try:
            app.db.update_pattern(pattern_id, data)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": f"Ошибка обновления паттерна: {str(e)}"}), 400

    @api_bp.route('/patterns/<int:pattern_id>', methods=['DELETE'])
    def delete_pattern(pattern_id):
        try:
            app.db.delete_pattern(pattern_id)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": f"Ошибка удаления паттерна: {str(e)}"}), 400

    @api_bp.route('/patterns/reorder', methods=['POST'])
    def reorder_patterns():
        ordered_ids = request.get_json()
        try:
            app.db.update_patterns_order(ordered_ids)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": f"Ошибка изменения порядка: {str(e)}"}), 400

    @api_bp.route('/patterns/test-all', methods=['POST'])
    def test_all_patterns():
        data = request.get_json()
        filename = data.get('filename')
        if not filename:
            return jsonify({"error": "Отсутствует 'filename'"}), 400
            
        renamer = Renamer(app.logger, app.db)
        result = renamer.find_episode_with_db_patterns(filename)
        return jsonify({"result": result})

    @api_bp.route('/season_patterns', methods=['GET'])
    def get_season_patterns():
        return jsonify(app.db.get_season_patterns())

    @api_bp.route('/season_patterns', methods=['POST'])
    def add_season_pattern():
        data = request.get_json()
        try:
            pattern_id = app.db.add_season_pattern(data['name'], data['pattern'])
            return jsonify({"success": True, "id": pattern_id})
        except Exception as e:
            return jsonify({"success": False, "error": f"Ошибка добавления паттерна сезона: {str(e)}"}), 400

    @api_bp.route('/season_patterns/<int:pattern_id>', methods=['PUT'])
    def update_season_pattern(pattern_id):
        data = request.get_json()
        try:
            app.db.update_season_pattern(pattern_id, data)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": f"Ошибка обновления паттерна сезона: {str(e)}"}), 400

    @api_bp.route('/season_patterns/<int:pattern_id>', methods=['DELETE'])
    def delete_season_pattern(pattern_id):
        try:
            app.db.delete_season_pattern(pattern_id)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": f"Ошибка удаления паттерна сезона: {str(e)}"}), 400

    @api_bp.route('/season_patterns/reorder', methods=['POST'])
    def reorder_season_patterns():
        ordered_ids = request.get_json()
        try:
            app.db.update_season_patterns_order(ordered_ids)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": f"Ошибка изменения порядка: {str(e)}"}), 400
            
    @api_bp.route('/season_patterns/test-all', methods=['POST'])
    def test_all_season_patterns():
        data = request.get_json()
        filename = data.get('filename')
        if not filename:
            return jsonify({"error": "Отсутствует 'filename'"}), 400
            
        renamer = Renamer(app.logger, app.db)
        result = renamer.find_season_with_db_patterns(filename)
        return jsonify({"result": result})

    @api_bp.route('/advanced_patterns', methods=['GET'])
    def get_advanced_patterns():
        patterns = app.db.get_advanced_patterns()
        return jsonify(patterns)

    @api_bp.route('/advanced_patterns', methods=['POST'])
    def add_advanced_pattern():
        data = request.get_json()
        try:
            pattern_id = app.db.add_advanced_pattern(data)
            return jsonify({"success": True, "id": pattern_id})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    @api_bp.route('/advanced_patterns/<int:pattern_id>', methods=['PUT'])
    def update_advanced_pattern(pattern_id):
        data = request.get_json()
        try:
            app.db.update_advanced_pattern(pattern_id, data)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    @api_bp.route('/advanced_patterns/<int:pattern_id>', methods=['DELETE'])
    def delete_advanced_pattern(pattern_id):
        try:
            app.db.delete_advanced_pattern(pattern_id)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    @api_bp.route('/advanced_patterns/reorder', methods=['POST'])
    def reorder_advanced_patterns():
        ordered_ids = request.get_json()
        try:
            app.db.update_advanced_patterns_order(ordered_ids)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    @api_bp.route('/advanced_patterns/test-all', methods=['POST'])
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

    @api_bp.route('/quality_patterns', methods=['GET'])
    def get_quality_patterns():
        return jsonify(app.db.get_quality_patterns())

    @api_bp.route('/quality_patterns', methods=['POST'])
    def add_quality_pattern():
        data = request.get_json()
        try:
            pattern_id = app.db.add_quality_pattern(data['standard_value'])
            return jsonify({"success": True, "id": pattern_id})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    @api_bp.route('/quality_patterns/<int:pattern_id>', methods=['PUT'])
    def update_quality_pattern(pattern_id):
        data = request.get_json()
        try:
            app.db.update_quality_pattern(pattern_id, data)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    @api_bp.route('/quality_patterns/<int:pattern_id>', methods=['DELETE'])
    def delete_quality_pattern(pattern_id):
        try:
            app.db.delete_quality_pattern(pattern_id)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    @api_bp.route('/quality_patterns/reorder', methods=['POST'])
    def reorder_quality_patterns():
        ordered_ids = request.get_json()
        try:
            app.db.update_quality_patterns_order(ordered_ids)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    @api_bp.route('/quality_patterns/<int:quality_pattern_id>/search_patterns', methods=['POST'])
    def add_quality_search_pattern(quality_pattern_id):
        data = request.get_json()
        try:
            app.db.add_quality_search_pattern(quality_pattern_id, data['pattern'])
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    @api_bp.route('/quality_search_patterns/<int:search_pattern_id>', methods=['DELETE'])
    def delete_quality_search_pattern(search_pattern_id):
        try:
            app.db.delete_quality_search_pattern(search_pattern_id)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    @api_bp.route('/quality_patterns/test', methods=['POST'])
    def test_quality_patterns():
        data = request.get_json()
        renamer = Renamer(app.logger, app.db)
        result = renamer._extract_quality(data.get('filename'))
        return jsonify({"result": result if result else "Не найдено"})

    @api_bp.route('/resolution_patterns', methods=['GET'])
    def get_resolution_patterns():
        return jsonify(app.db.get_resolution_patterns())

    @api_bp.route('/resolution_patterns', methods=['POST'])
    def add_resolution_pattern():
        data = request.get_json()
        try:
            pattern_id = app.db.add_resolution_pattern(data['standard_value'])
            return jsonify({"success": True, "id": pattern_id})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    @api_bp.route('/resolution_patterns/<int:pattern_id>', methods=['PUT'])
    def update_resolution_pattern(pattern_id):
        data = request.get_json()
        try:
            app.db.update_resolution_pattern(pattern_id, data)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    @api_bp.route('/resolution_patterns/<int:pattern_id>', methods=['DELETE'])
    def delete_resolution_pattern(pattern_id):
        try:
            app.db.delete_resolution_pattern(pattern_id)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    @api_bp.route('/resolution_patterns/reorder', methods=['POST'])
    def reorder_resolution_patterns():
        ordered_ids = request.get_json()
        try:
            app.db.update_resolution_patterns_order(ordered_ids)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    @api_bp.route('/resolution_patterns/<int:resolution_pattern_id>/search_patterns', methods=['POST'])
    def add_resolution_search_pattern(resolution_pattern_id):
        data = request.get_json()
        try:
            app.db.add_resolution_search_pattern(resolution_pattern_id, data['pattern'])
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    @api_bp.route('/resolution_search_patterns/<int:search_pattern_id>', methods=['DELETE'])
    def delete_resolution_search_pattern(search_pattern_id):
        try:
            app.db.delete_resolution_search_pattern(search_pattern_id)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400
            
    @api_bp.route('/resolution_patterns/test', methods=['POST'])
    def test_resolution_patterns():
        data = request.get_json()
        renamer = Renamer(app.logger, app.db)
        result = renamer._extract_resolution(data.get('filename'))
        return jsonify({"result": result if result else "Не найдено"})
        
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)