import hashlib
import os
import json
import threading
import time
from flask import Blueprint, jsonify, request, current_app as app

from auth import AuthManager
from qbittorrent import QBittorrentClient
from scanner import perform_series_scan, generate_media_item_id
from file_cache import delete_from_cache
from rule_engine import RuleEngine
from scrapers.vk_scraper import VKScraper
from smart_collector import SmartCollector
from filename_formatter import FilenameFormatter
from logic.metadata_processor import build_final_metadata
from utils.tracker_resolver import TrackerResolver

series_bp = Blueprint('series_api', __name__, url_prefix='/api/series')

@series_bp.route('', methods=['GET'])
def get_series():
    series_list = app.db.get_all_series()
    
    # --- НАЧАЛО ИЗМЕНЕНИЯ ---
    # Получаем ID всех сериалов, для которых есть активные задачи
    relocating_ids = {task['series_id'] for task in app.db.get_pending_relocation_task()}
    renaming_ids = {task['series_id'] for task in app.db.get_all_renaming_tasks()} # Получаем ВСЕ задачи переименования
    busy_ids = relocating_ids.union(renaming_ids) # Объединяем множества
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---

    for s in series_list:
        if s.get('last_scan_time'):
            s['last_scan_time'] = s['last_scan_time'].isoformat()
        # Добавляем новый ОБЩИЙ флаг занятости
        s['is_busy'] = s['id'] in busy_ids
            
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
    if series:
        if series.get('last_scan_time'):
            series['last_scan_time'] = series['last_scan_time'].isoformat()
        
        # --- НАЧАЛО ИЗМЕНЕНИЯ ---
        relocation_tasks = app.db.get_pending_relocation_task(series_id=series_id)
        renaming_tasks = app.db.get_all_renaming_tasks(series_id=series_id)
        # Сериал "занят", если есть хотя бы одна задача перемещения ИЛИ переименования
        series['is_busy'] = bool(relocation_tasks) or bool(renaming_tasks)
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---

        if series.get('source_type') == 'torrent':
            resolver = TrackerResolver(app.db)
            tracker_info = resolver.get_tracker_by_url(series['url'])
            series['tracker_info'] = tracker_info
        
    return jsonify(series) if series else (jsonify({"error": "Сериал не найден"}), 404)

@series_bp.route('/<int:series_id>/rename_preview', methods=['GET'])
def get_rename_preview(series_id):
    """
    Возвращает предпросмотр переименований для UI, используя объединенные метаданные.
    """
    try:
        series = app.db.get_series(series_id)
        if not series or not series.get('parser_profile_id'):
            return jsonify({"preview": [], "needs_rename_count": 0})

        engine = RuleEngine(app.db, app.logger)
        formatter = FilenameFormatter(app.logger)
        profile_id = series.get('parser_profile_id')

        preview_list = []
        needs_rename_count = 0

        media_items = app.db.get_media_items_for_series(series_id)
        for item in media_items:
            source_title = item.get('source_title')
            current_filename = item.get('final_filename')
            if not source_title:
                continue

            # --- НАЧАЛО ИЗМЕНЕНИЙ ---
            
            # 1. Получаем данные от движка правил
            processed_result = engine.process_videos(profile_id, [{'title': source_title}])[0]
            rule_engine_data = processed_result.get('result', {}).get('extracted', {})

            # 2. Используем централизованную функцию для сборки метаданных с правильным приоритетом
            final_metadata = build_final_metadata(series, item, rule_engine_data)
            
            # 3. Генерируем новое имя на основе правильных метаданных
            new_filename_preview = formatter.format_filename(series, final_metadata, current_filename)

            # 4. Добавляем запрошенное логирование
            if app.debug_manager.is_debug_enabled('series_api'):
                app.logger.debug(
                    "series_api",
                    f"Preview for UID {item['unique_id']}: "
                    f"Metadata={final_metadata}, "
                    f"New Filename='{new_filename_preview}'"
                )
            # --- КОНЕЦ ИЗМЕНЕНИЙ ---

            if current_filename and current_filename != new_filename_preview:
                needs_rename_count += 1

            preview_list.append({
                'unique_id': item['unique_id'],
                'type': 'media_item',
                'current_filename': current_filename,
                'new_filename_preview': new_filename_preview
            })

            sliced_children = app.db.get_sliced_files_for_source(item['unique_id'])
            if not sliced_children:
                continue

            for child in sliced_children:
                child_old_path = child.get('file_path')
                child_metadata = final_metadata.copy()
                child_metadata['episode'] = child.get('episode_number')
                # Удаляем поля, нерелевантные для дочерних файлов
                child_metadata.pop('start', None)
                child_metadata.pop('end', None)
                child_new_path_preview = formatter.format_filename(series, child_metadata, child_old_path)

                if child_old_path and child_old_path != child_new_path_preview:
                    needs_rename_count += 1

                preview_list.append({
                    'unique_id': f"sliced-{child['id']}",
                    'type': 'sliced_file',
                    'current_filename': child_old_path,
                    'new_filename_preview': child_new_path_preview
                })

        return jsonify({"preview": preview_list, "needs_rename_count": needs_rename_count})
    except Exception as e:
        app.logger.error("series_api", f"Ошибка предпросмотра для series_id {series_id}: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@series_bp.route('/<int:series_id>/reprocess_vk_files', methods=['POST'])
def reprocess_vk_files_route(series_id):
    """Создает одну задачу на переобработку и переименование всех файлов для VK-сериала."""
    try:
        task_data = {
            'series_id': series_id,
            'task_type': 'mass_vk_reprocess' # Новый тип задачи
        }
        
        task_created = app.db.create_renaming_task(task_data)
        
        if task_created:
            app.renaming_agent.trigger()
            return jsonify({"success": True, "message": "Задача на переобработку файлов VK-сериала создана."})
        else:
            return jsonify({"success": False, "error": "Активная задача на переобработку уже выполняется."}), 409
            
    except Exception as e:
        app.logger.error("series_api", f"Ошибка запуска переименования для series_id {series_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@series_bp.route('/<int:series_id>/composition', methods=['GET'])
def get_series_composition(series_id):
    try:
        series = app.db.get_series(series_id)
        if not series:
            return jsonify({"error": "Сериал не найден"}), 404

        reconstructed_plan = []

        if series.get('source_type') == 'vk_video':
            force_refresh = request.args.get('refresh', 'false').lower() == 'true'

            if force_refresh:
                app.logger.info("series_api", f"Запрошено полное обновление композиции для series_id: {series_id}")
                channel_url, query = series['url'].split('|', 1)
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

                    source_info = video_data.get('source_data', {})
                    pub_date = source_info.get('publication_date')
                    url = source_info.get('url')
                    title = source_info.get('title')

                    if not all([pub_date, url, title]): continue

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
                    app.db.add_or_update_media_items(candidates_to_save)
                    app.logger.info("series_api", f"Сохранено/обновлено {len(candidates_to_save)} кандидатов в БД во время построения композиции.")

            # --- ГЛАВНОЕ ИЗМЕНЕНИЕ: SmartCollector теперь запускается всегда ---
            # Это гарантирует, что у всех элементов будет правильный plan_status ПЕРЕД усыновлением.
            app.db.reset_plan_status_for_series(series_id)

            collector = SmartCollector(app.logger, app.db)
            collector.collect(series_id)

            all_db_items = app.db.get_media_items_for_series(series_id)
            obsolete_compilations = [
                item for item in all_db_items 
                if bool(item.get('episode_end')) and item.get('plan_status') in ['replaced', 'redundant']
            ]

            if obsolete_compilations:
                app.logger.info("series_api", f"Найдено {len(obsolete_compilations)} устаревших компиляций. Очистка связанных нарезанных файлов...")
                for comp in obsolete_compilations:
                    deleted_count = app.db.delete_sliced_files_for_source(comp['unique_id'])
                    if deleted_count > 0:
                        app.logger.info("series_api", f"  -> Удалено {deleted_count} записей о нарезке для UID {comp['unique_id']}.")

            app.scanner_agent.sync_single_series_filesystem(series_id)
            app.scanner_agent.verify_sliced_files_for_series(series_id)
            
            reconstructed_plan = []
            db_items = app.db.get_media_items_for_series(series_id)
            
            # Инициализируем RuleEngine один раз
            engine = RuleEngine(app.db, app.logger)
            profile_id = series.get('parser_profile_id')

            for item in db_items:
                source_title = item.get('source_title')
                
                # Создаем "сырые" данные для RuleEngine
                video_data_for_engine = {
                    'title': source_title,
                    'url': item.get('source_url'),
                    'publication_date': item.get('publication_date'),
                    'resolution': item.get('resolution')
                }

                # Получаем канонический объект результата от RuleEngine
                # Если нет source_title или профиля, result будет пустым
                if source_title and profile_id:
                    processed_result = engine.process_videos(profile_id, [video_data_for_engine])[0]
                else:
                    processed_result = {
                        "source_data": video_data_for_engine,
                        "match_events": [],
                        "result": {'extracted': {}}
                    }
                
                # Явно проверяем и конвертируем дату в строку перед отправкой
                source_data = processed_result.get('source_data', {})
                if source_data.get('publication_date'):
                    source_data['publication_date'] = source_data['publication_date'].isoformat()

                reconstructed_item = {
                    **processed_result,
                    'season': item.get('season'),
                    'plan_status': item.get('plan_status'),
                    'status': item.get('status'),
                    'unique_id': item.get('unique_id'),
                    'final_filename': item.get('final_filename'),
                    'slicing_status': item.get('slicing_status', 'none'),
                    'is_ignored_by_user': item.get('is_ignored_by_user', False),
                    'source_title': source_title
                }
                reconstructed_plan.append(reconstructed_item)
            
            return jsonify(reconstructed_plan)
        
        elif series.get('source_type') == 'torrent':
            profile_id = series.get('parser_profile_id')
            if not profile_id:
                app.logger.warning("series_api", f"Для торрент-сериала {series_id} не назначен профиль правил. Предпросмотр может быть неактуален.")
                # Возвращаем старую логику, если профиля нет
                torrent_files = app.db.get_torrent_files_for_series(series_id)
                for item in torrent_files:
                    reconstructed_plan.append({
                        'id': item['id'], 'original_path': item['original_path'], 'renamed_path_preview': item.get('renamed_path') or item.get('original_path'),
                        'status': item['status'], 'extracted_metadata': json.loads(item['extracted_metadata']) if item['extracted_metadata'] else {},
                        'is_file_present': os.path.exists(os.path.join(series['save_path'], item.get('renamed_path') or item.get('original_path'))),
                        'qb_hash': item['qb_hash']
                    })
                return jsonify(reconstructed_plan)

            engine = RuleEngine(app.db, app.logger)
            formatter = FilenameFormatter(app.logger)
            
            torrent_files = app.db.get_torrent_files_for_series(series_id)
            
            for item in torrent_files:
                original_path = item['original_path']
                basename = os.path.basename(original_path)
                
                # 1. Заново применяем правила
                processed_result = engine.process_videos(profile_id, [{'title': basename}])[0]
                new_extracted_data = processed_result.get('result', {}).get('extracted', {})
                
                # 2. Генерируем новое имя на основе свежих метаданных
                new_renamed_path_preview = formatter.format_filename(series, new_extracted_data, original_path)
                
                # 3. Определяем текущий путь на диске и его наличие
                current_path_on_disk = item.get('renamed_path') or original_path
                is_file_present = os.path.exists(os.path.join(series['save_path'], current_path_on_disk))
                
                if app.debug_manager.is_debug_enabled('series_api'):
                    app.logger.debug(
                        "series_api",
                        f"Torrent Composition Preview for file ID {item['id']}: "
                        f"Original='{basename}', "
                        f"New Metadata={new_extracted_data}, "
                        f"New Filename='{os.path.basename(new_renamed_path_preview)}'"
                    )

                # 4. Собираем итоговый объект для UI
                reconstructed_item = {
                    'id': item['id'],
                    'original_path': original_path,
                    'renamed_path_preview': new_renamed_path_preview,
                    'status': item['status'],
                    'extracted_metadata': new_extracted_data, # Отправляем свежие метаданные
                    'is_file_present': is_file_present,
                    'qb_hash': item['qb_hash'],
                    'is_mismatch': current_path_on_disk != new_renamed_path_preview
                }
                reconstructed_plan.append(reconstructed_item)
            
            return jsonify(reconstructed_plan)

    except Exception as e:
        app.logger.error("series_api", f"Ошибка при построении композиции для series_id {series_id}: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@series_bp.route('/<int:series_id>/reprocess', methods=['POST'])
def reprocess_series_torrents_route(series_id):
    """
    Создает одну задачу на переобработку и переименование всех файлов
    для торрент-сериала.
    """
    try:
        task_data = {
            'series_id': series_id,
            'task_type': 'mass_torrent_reprocess'
        }
        # Пытаемся создать задачу. db.create_renaming_task вернет False, если активная задача уже есть.
        task_created = app.db.create_renaming_task(task_data)
        
        if task_created:
            # "Пробуждаем" агента, чтобы он немедленно начал работу
            app.renaming_agent.trigger()
            return jsonify({"success": True, "message": "Задача на переобработку файлов создана и запущена в фоновом режиме."})
        else:
            return jsonify({"success": False, "error": "Задача на переобработку уже выполняется."}), 409
    except Exception as e:
        app.logger.error("series_api", f"Ошибка при запуске переобработки для series_id {series_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@series_bp.route('/<int:series_id>', methods=['POST'])
def update_series(series_id):
    """
    Принимает все изменения из UI, выполняет их в строгом порядке:
    1. Обновляет простые данные в БД.
    2. Создает задачу на перемещение (если нужно).
    3. Создает задачу на переименование/переобработку (если нужно).
    """
    data = request.get_json()
    app.logger.info("series_api", f"Получен запрос на комплексное обновление для series_id: {series_id}")

    try:
        series = app.db.get_series(series_id)
        if not series:
            return jsonify({"success": False, "error": "Сериал не найден"}), 404

        # --- ШАГ 1: Обновляем "быстрые" данные в БД ---
        original_save_path = series.get('save_path')
        payload = data.copy()
        payload.pop('save_path', None)
        payload.pop('last_scan_time', None)
        app.db.update_series(series_id, payload)
        app.logger.info("series_api", f"Базовые свойства для series_id {series_id} обновлены.")

        # --- ШАГ 2: Создаем задачу на перемещение (если путь изменился) ---
        new_path = data.get('save_path')
        relocation_task_created = False  # Флаг для отслеживания

        if new_path and new_path != original_save_path:
            app.logger.info("series_api", f"Обнаружено изменение пути для series_id {series_id}. Создание задачи на перемещение.")
            if os.path.exists(original_save_path) and os.path.exists(os.path.dirname(new_path)):
                if os.stat(original_save_path).st_dev != os.stat(os.path.dirname(new_path)).st_dev:
                    return jsonify({"success": False, "error": "Перемещение между разными дисками не поддерживается."}), 400
            
            task_created = app.db.create_relocation_task(series_id, new_path)
            if not task_created:
                return jsonify({"success": False, "error": "Активная задача на перемещение уже выполняется."}), 409
            
            app.scanner_agent.trigger_relocation_check()
            relocation_task_created = True

        # --- ШАГ 3: Создаем задачу на переименование/переобработку ---
        app.logger.info("series_api", f"Создание задачи на переобработку файлов для series_id: {series_id}.")
        task_type = 'mass_vk_reprocess' if series.get('source_type') == 'vk_video' else 'mass_torrent_reprocess'
        
        renaming_task_created = app.db.create_renaming_task({
            'series_id': series_id,
            'task_type': task_type
        })
        
        # Запускаем агент переименования напрямую, ТОЛЬКО ЕСЛИ не было задачи на перемещение
        if renaming_task_created and not relocation_task_created:
            app.logger.info("series_api", "Изменения не требуют перемещения. Прямой запуск агента переименования.")
            app.renaming_agent.trigger()
        elif not renaming_task_created:
             app.logger.warning("series_api", f"Активная задача на переименование для series_id {series_id} уже существует.")

        return jsonify({"success": True, "message": "Задача на обновление принята в обработку."})

    except Exception as e:
        app.logger.error("series_api", f"Ошибка при комплексном обновлении series_id {series_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

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
    app.db.set_viewing_status(series_id, is_viewing)
    app.status_manager._update_and_broadcast(series_id)
    return jsonify({"success": True})

@series_bp.route('/<int:series_id>/viewing_heartbeat', methods=['POST'])
def viewing_heartbeat(series_id):
    app.db.set_viewing_status(series_id, True)
    return jsonify({"success": True})

@series_bp.route('/<int:series_id>/scan', methods=['POST'])
def scan_series_route(series_id):
    debug_force_replace = app.db.get_setting('debug_force_replace', 'false') == 'true'
    result = perform_series_scan(series_id, app.status_manager, app, debug_force_replace=debug_force_replace)
    if result["success"]:
        return jsonify(result)
    else:
        status_code = 409 if "уже запущен" in result.get("error", "") else 500
        return jsonify(result), status_code

@series_bp.route('/<int:series_id>/torrents/history', methods=['GET'])
def get_series_torrents_history(series_id):
    all_torrents = app.db.get_torrents(series_id)
    return jsonify(all_torrents)

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
    try:
        tasks = app.db.get_all_active_torrent_tasks()
        return jsonify(tasks)
    except Exception as e:
        app.logger.error("series_api", f"Ошибка получения задач мониторинга торрентов: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@series_bp.route('/<int:series_id>/reset_torrents', methods=['POST'])
def reset_torrents(series_id):
    """
    Удаляет все активные торренты для сериала из qBittorrent (с файлами)
    и из базы данных, готовя его к повторной загрузке с новыми параметрами.
    """
    app.logger.warning("series_api", f"Получен запрос на полный сброс торрентов для series_id: {series_id}")
    try:
        # 1. Получаем все активные торренты ПЕРЕД удалением из БД
        torrents_to_delete = app.db.get_torrents(series_id, is_active=True)
        if not torrents_to_delete:
            return jsonify({"success": True, "message": "Активных торрентов для удаления не найдено."})

        # 2. Удаляем из qBittorrent
        hashes_to_delete = [t['qb_hash'] for t in torrents_to_delete if t.get('qb_hash')]
        if hashes_to_delete:
            qb_client = QBittorrentClient(AuthManager(app.db, app.logger), app.db, app.logger)
            qb_client.delete_torrents(hashes_to_delete, delete_files=True)
            app.logger.info("series_api", f"Удалено {len(hashes_to_delete)} торрентов из qBittorrent для series_id {series_id}.")

        # 3. Очищаем кэш .torrent файлов
        for torrent in torrents_to_delete:
            if torrent.get('torrent_id'):
                delete_from_cache(torrent['torrent_id'])

        # 4. Удаляем записи из таблиц torrents и torrent_files в БД
        deleted_db_count = app.db.delete_torrents_for_series(series_id)
        app.logger.info("series_api", f"Удалено {deleted_db_count} записей о торрентах из БД для series_id {series_id}.")
        
        return jsonify({"success": True, "message": "Старые торренты и файлы успешно удалены."})

    except Exception as e:
        app.logger.error("series_api", f"Ошибка при сбросе торрентов для series_id {series_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

def _broadcast_series_update(series_id, event_name):
    series_data = app.db.get_series(series_id)
    if series_data:
        if series_data.get('last_scan_time'):
            series_data['last_scan_time'] = series_data['last_scan_time'].isoformat()
        app.sse_broadcaster.broadcast(event_name, series_data)

@series_bp.route('/<int:series_id>/source-filenames', methods=['GET'])
def get_series_source_filenames(series_id):
    try:
        filenames = app.db.get_source_filenames_for_series(series_id)
        return jsonify(filenames)
    except Exception as e:
        app.logger.error("series_api", f"Ошибка получения имён файлов для series_id {series_id}: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@series_bp.route('/<int:series_id>/relocate', methods=['POST'])
def relocate_series(series_id):
    """
    Создает задачу на перемещение сериала в новую директорию.
    """
    data = request.get_json()
    new_path = data.get('new_path')

    if not new_path:
        return jsonify({"success": False, "error": "Новый путь не указан"}), 400

    series = app.db.get_series(series_id)
    if not series:
        return jsonify({"success": False, "error": "Сериал не найден"}), 404

    old_path = series['save_path']
    if old_path == new_path:
        return jsonify({"success": True, "message": "Новый путь совпадает со старым."})
    
    try:
        # Предварительная проверка возможности перемещения
        if os.path.exists(old_path) and os.path.exists(os.path.dirname(new_path)):
             if os.stat(old_path).st_dev != os.stat(os.path.dirname(new_path)).st_dev:
                return jsonify({"success": False, "error": "Перемещение между разными дисками не поддерживается."}), 400

        task_created = app.db.create_relocation_task(series_id, new_path)
        if not task_created:
            return jsonify({"success": False, "error": "Активная задача на перемещение уже выполняется для этого сериала."}), 409
        
        # "Будим" агента для немедленной обработки
        app.scanner_agent.trigger_relocation_check()
        
        return jsonify({"success": True, "message": "Задача на перемещение принята в обработку."}), 202

    except Exception as e:
        app.logger.error("series_api", f"Ошибка создания задачи на перемещение для series_id {series_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500