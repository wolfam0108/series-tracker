import json
import os
from flask import Blueprint, jsonify, request, Response, current_app as app

system_bp = Blueprint('system_api', __name__, url_prefix='/api')

@system_bp.route('/stream')
def stream():
    # --- ИЗМЕНЕНИЕ: Захватываем реальный объект приложения, пока контекст еще жив ---
    the_real_app = app._get_current_object()

    # --- ИЗМЕНЕНИЕ: Генератор теперь принимает реальный объект приложения как аргумент ---
    def event_stream(flask_app):
        # --- ИЗМЕНЕНИЕ: Контекст создается от реального объекта, а не от прокси ---
        with flask_app.app_context():
            scanner_status = flask_app.scanner_agent.get_status()
            yield f"event: scanner_status_update\ndata: {json.dumps(scanner_status)}\n\n"
            
            # --- ИЗМЕНЕНИЕ: Используем переданный объект ---
            q = flask_app.sse_broadcaster.subscribe()
            try:
                while True:
                    message = q.get()
                    yield message
            except GeneratorExit:
                # --- ИЗМЕНЕНИЕ: Используем переданный объект ---
                flask_app.sse_broadcaster.unsubscribe(q)

    # --- ИЗМЕНЕНИЕ: Передаем реальный объект в генератор при создании Response ---
    return Response(event_stream(the_real_app), mimetype='text/event-stream')

@system_bp.route('/database/clear', methods=['POST'])
def clear_database():
    app.logger.info("database", "Получен запрос на полную очистку БД")
    try:
        app.db.clear_all_data_except_auth()
        return jsonify({"success": True, "message": "База данных успешно очищена."})
    except Exception as e:
        app.logger.error("database", f"Ошибка при очистке базы данных: {e}", exc_info=True)
        return jsonify({"success": False, "error": f"Ошибка на сервере: {e}"}), 500

@system_bp.route('/database/tables', methods=['GET'])
def get_db_tables():
    try:
        tables = app.db.get_table_names()
        excluded_tables = {'auth'}
        safe_tables = [t for t in tables if t not in excluded_tables]
        return jsonify(safe_tables)
    except Exception as e:
        app.logger.error("database_api", f"Ошибка получения списка таблиц: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Не удалось получить список таблиц"}), 500

@system_bp.route('/database/clear_table', methods=['POST'])
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

@system_bp.route('/logs', methods=['GET'])
def get_logs():
    """
    Читает логи из файлов, фильтрует их на лету и отдает с пагинацией.
    """
    LOG_DIR = 'logs'
    
    # 1. Получаем параметры фильтрации из запроса
    group_filter = request.args.get('group')
    level_filter = request.args.get('level')
    try:
        limit = int(request.args.get('limit', 200))
    except (ValueError, TypeError):
        limit = 200

    # 2. Определяем, какие файлы нужно читать
    files_to_read = []
    if level_filter:
        # Если задан уровень, читаем только один конкретный файл
        files_to_read.append(f'{level_filter.lower()}.log')
    else:
        # Иначе - читаем все файлы
        files_to_read = ['error.log', 'warning.log', 'info.log', 'debug.log']

    all_logs = []
    
    # 3. Читаем и фильтруем каждый файл
    for filename in files_to_read:
        filepath = os.path.join(LOG_DIR, filename)
        if not os.path.exists(filepath):
            continue

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                # Читаем строки в обратном порядке, чтобы новые были первыми
                for line in reversed(f.readlines()):
                    try:
                        log_entry = json.loads(line)
                        
                        # Применяем фильтр по группе, если он есть
                        if group_filter and log_entry.get('group') != group_filter:
                            continue
                        
                        all_logs.append(log_entry)
                    except (json.JSONDecodeError, KeyError):
                        # Пропускаем поврежденные строки JSON
                        continue
        except Exception as e:
            app.logger.error("system_api", f"Ошибка чтения лог-файла {filepath}: {e}")

    # 4. Сортируем все найденные записи по времени (от новых к старым)
    # Это особенно важно, когда читаем из нескольких файлов
    all_logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

    # 5. Отдаем только запрошенное количество записей (пагинация)
    return jsonify(all_logs[:limit])

@system_bp.route('/agent/queue', methods=['GET'])
def get_agent_queue():
    if not hasattr(app, 'agent'): return jsonify([])
    return jsonify(app.agent.get_queue_info())

@system_bp.route('/agent/reset', methods=['POST'])
def reset_agent():
    app.logger.info("agent_api", "Получен запрос на сброс состояния агента и зависших задач.")
    if hasattr(app, 'agent'):
        app.agent.clear_queue()
    
    stuck_states = ['scanning', 'rechecking', '{"%']
    reset_count = app.db.reset_stuck_series_states(stuck_states)
    
    all_series = app.db.get_all_series()
    for s in all_series:
        series_data = app.db.get_series(s['id'])
        if series_data:
            if series_data.get('last_scan_time'):
                series_data['last_scan_time'] = series_data['last_scan_time'].isoformat()
            app.sse_broadcaster.broadcast('series_updated', series_data)

    app.logger.info("agent_api", f"Сброс завершен. Очищена очередь агента, сброшено {reset_count} статусов сериалов в БД.")
    return jsonify({"success": True, "message": f"Очередь очищена, статусы {reset_count} сериалов сброшены."})
    
@system_bp.route('/scanner/status', methods=['GET'])
def get_scanner_status():
    return jsonify(app.scanner_agent.get_status())

@system_bp.route('/scanner/settings', methods=['POST'])
def update_scanner_settings():
    data = request.get_json()
    if 'enabled' in data:
        app.db.set_setting('scanner_agent_enabled', str(data['enabled']).lower())
    if 'interval' in data:
        app.db.set_setting('scan_interval_minutes', str(data['interval']))
    
    if 'interval' in data and app.scanner_agent.get_status()['scanner_enabled']:
         app.scanner_agent.trigger_scan_all()

    return jsonify({"success": True})

@system_bp.route('/scanner/scan_all', methods=['POST'])
def scan_all_now():
    data = request.get_json() or {}
    debug_force_replace = data.get('debug_force_replace', False)

    status = app.scanner_agent.get_status()
    if status['is_scanning']:
        return jsonify({"success": False, "error": "Сканирование уже запущено."}), 409
    
    app.scanner_agent.trigger_scan_all(debug_force_replace=debug_force_replace)
    return jsonify({"success": True, "message": "Сканирование всех сериалов запущено."})

@system_bp.route('/downloads/queue', methods=['GET'])
def get_download_queue():
    """Возвращает текущую очередь задач для yt-dlp."""
    if not hasattr(app, 'db'):
        return jsonify([])
    tasks = app.db.get_active_download_tasks()
    return jsonify(tasks)

@system_bp.route('/downloads/queue/clear', methods=['POST'])
def clear_download_queue():
    """Удаляет все задачи в статусе pending и error из очереди загрузок."""
    try:
        deleted_count = app.db.clear_download_queue()
        return jsonify({"success": True, "message": f"Удалено {deleted_count} задач из очереди."})
    except Exception as e:
        app.logger.error("system_api", f"Ошибка при очистке очереди загрузок: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500
    
@system_bp.route('/database/table/<string:table_name>', methods=['GET'])
def get_table_content(table_name):
    # Получаем список разрешенных таблиц для безопасности
    allowed_tables = app.db.get_table_names()
    excluded_tables = {'auth', 'logs'}
    
    if table_name in excluded_tables or table_name not in allowed_tables:
        return jsonify({"error": "Доступ к этой таблице запрещен"}), 403
    
    try:
        # Нужен новый метод в db.py для получения сырых данных
        content = app.db.get_raw_table_content(table_name)
        return jsonify(content)
    except Exception as e:
        app.logger.error("database_api", f"Ошибка получения данных из таблицы '{table_name}': {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500
    