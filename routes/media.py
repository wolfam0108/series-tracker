import os
import threading
from flask import Blueprint, jsonify, request, current_app as app
import json
from utils.chapter_parser import get_chapters # Импортируем новый парсер
from utils.chapter_filter import ChapterFilter # Импортируем фильтр глав
from logic.metadata_processor import build_final_metadata
from filename_formatter import FilenameFormatter

media_bp = Blueprint('media_api', __name__, url_prefix='/api')

@media_bp.route('/series/<int:series_id>/media-items', methods=['GET'])
def get_media_items_for_series(series_id):
    """Возвращает все медиа-элементы для указанного сериала."""
    try:
        items = app.db.get_media_items_for_series(series_id)
        # Конвертируем datetime в ISO формат для JSON
        for item in items:
            if item.get('publication_date'):
                item['publication_date'] = item['publication_date'].isoformat()
        return jsonify(items)
    except Exception as e:
        app.logger.error("media_api", f"Ошибка получения media_items для series_id {series_id}: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@media_bp.route('/media-items/<string:unique_id>/chapters', methods=['POST'])
def fetch_and_save_chapters(unique_id):
    """
    Получает оглавление для видео, сохраняет его в БД и, если количество глав
    совпадает с ожидаемым, обновляет статус нарезки на 'pending'.
    """
    item = app.db.get_media_item_by_uid(unique_id)
    if not item:
        return jsonify({"error": "Медиа-элемент не найден"}), 404

    video_url = item.get('source_url')
    if not video_url:
        return jsonify({"error": "URL видео не найден"}), 400

    try:
        chapters_list = get_chapters(video_url)
        chapters_json = json.dumps(chapters_list)
        app.db.update_media_item_chapters(unique_id, chapters_json)

        expected_count = (item.get('episode_end', 0) - item.get('episode_start', 0) + 1)
        if chapters_list and len(chapters_list) == expected_count:
            app.db.update_media_item_slicing_status(unique_id, 'pending')
            app.logger.info("media_api", f"Количество глав ({len(chapters_list)}) совпало. Статус нарезки для UID {unique_id} изменен на 'pending'.")

        return jsonify(chapters_list)
    except Exception as e:
        app.logger.error("media_api", f"Ошибка получения глав для UID {unique_id}: {e}", exc_info=True)
        return jsonify({"error": "Не удалось получить оглавление"}), 500


@media_bp.route('/media-items/<int:item_id>/ignore', methods=['PUT'])
def set_item_ignored_status(item_id):
    data = request.get_json()
    is_ignored = data.get('is_ignored')

    if is_ignored is None:
        return jsonify({"success": False, "error": "Параметр is_ignored не указан"}), 400
    
    try:
        # Получаем информацию о медиа-элементе до изменения статуса
        with app.db.Session() as session:
            from models import MediaItem
            item = session.query(MediaItem).filter_by(id=item_id).first()
            if not item:
                return jsonify({"success": False, "error": "Медиа-элемент не найден"}), 404
                
            series_id = item.series_id
            
        # Обновляем статус игнорирования
        app.db.set_media_item_ignored_status(item_id, is_ignored)
        
        # Синхронизируем статусы VK-сериала после изменения
        app.status_manager.sync_vk_statuses(series_id)
        
        return jsonify({"success": True})
    except Exception as e:
        app.logger.error("media_api", f"Ошибка обновления статуса игнорирования для item_id {item_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500
    
@media_bp.route('/media-items/<string:unique_id>/ignore', methods=['PUT'])
def set_item_ignored_status_by_uid(unique_id):
    data = request.get_json()
    is_ignored = data.get('is_ignored')

    if is_ignored is None:
        return jsonify({"success": False, "error": "Параметр is_ignored не указан"}), 400

    try:
        # Получаем информацию о медиа-элементе до изменения статуса
        item = app.db.get_media_item_by_uid(unique_id)
        if not item:
            return jsonify({"success": False, "error": "Медиа-элемент не найден"}), 404
            
        series_id = item['series_id']
        
        # Обновляем статус игнорирования
        app.db.set_media_item_ignored_status_by_uid(unique_id, is_ignored)
        
        # Синхронизируем статусы VK-сериала после изменения
        app.status_manager.sync_vk_statuses(series_id)
        
        return jsonify({"success": True})
    except Exception as e:
        app.logger.error("media_api", f"Ошибка обновления статуса игнорирования для UID {unique_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500
    
@media_bp.route('/media-items/<string:unique_id>/slice', methods=['POST'])
def create_slice_task(unique_id):
    """Создает задачу на нарезку для указанного медиа-элемента."""
    try:
        item = app.db.get_media_item_by_uid(unique_id)
        if not item:
            return jsonify({"success": False, "error": "Медиа-элемент не найден"}), 404
        
        # --- ИЗМЕНЕНИЕ: Разрешаем повторный запуск из статуса 'error' ---
        allowed_statuses = ['none', 'completed_with_errors', 'error']
        if item.get('slicing_status') not in allowed_statuses:
            return jsonify({"success": False, "error": "Задача на нарезку уже в очереди или была успешно завершена без ошибок."}), 409

        # --- ИЗМЕНЕНИЕ: Удаляем старые записи о файлах И старую задачу на нарезку ---
        deleted_files_count = app.db.delete_sliced_files_for_source(unique_id)
        if deleted_files_count > 0:
            app.logger.info("media_api", f"Удалено {deleted_files_count} старых записей о нарезанных файлах для UID {unique_id} перед повторной нарезкой.")
        
        # Очищаем старую, возможно, неудачную задачу из очереди
        app.db.delete_slicing_task_by_uid(unique_id)

        # Создаем новую задачу в очереди и обновляем статус
        app.db.create_slicing_task(unique_id, item['series_id'])
        app.db.update_media_item_slicing_status(unique_id, 'pending')
        
        app.slicing_agent._broadcast_queue_update()
        
        return jsonify({"success": True, "message": "Задача на нарезку успешно создана."})
    except Exception as e:
        app.logger.error("media_api", f"Ошибка создания задачи на нарезку для UID {unique_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500
    
@media_bp.route('/media-items/<string:unique_id>/verify-sliced-files', methods=['POST'])
def verify_sliced_files(unique_id):
    """
    Проверяет наличие нарезанных файлов на диске, обновляет их статусы в БД
    и статус родительского media_item.
    """
    app.logger.info("media_api", f"Запуск верификации нарезанных файлов для UID {unique_id}")
    try:
        # --- НАЧАЛО ИЗМЕНЕНИЙ: Получаем родительский элемент и сериал, чтобы узнать базовый путь ---
        media_item = app.db.get_media_item_by_uid(unique_id)
        if not media_item:
            return jsonify({"error": "Родительский медиа-элемент не найден"}), 404
        
        series = app.db.get_series(media_item['series_id'])
        if not series:
            return jsonify({"error": "Сериал не найден"}), 404
        
        base_path = series['save_path']
        # --- КОНЕЦ ИЗМЕНЕНИЙ ---

        sliced_files = app.db.get_sliced_files_for_source(unique_id)
        if not sliced_files:
            app.db.update_media_item_slicing_status_by_uid(unique_id, 'none')
            return jsonify({"status": "none", "message": "Записи о нарезанных файлах не найдены, статус сброшен."})

        has_missing_files = False
        for file_record in sliced_files:
            # --- НАЧАЛО ИЗМЕНЕНИЙ: Собираем абсолютный путь из базового и относительного перед проверкой ---
            absolute_path = os.path.join(base_path, file_record['file_path'])
            file_exists = os.path.exists(absolute_path)
            # --- КОНЕЦ ИЗМЕНЕНИЙ ---
            
            if file_exists and file_record['status'] == 'missing':
                app.db.update_sliced_file_status(file_record['id'], 'completed')
            elif not file_exists and file_record['status'] == 'completed':
                app.db.update_sliced_file_status(file_record['id'], 'missing')
                has_missing_files = True
            elif not file_exists:
                has_missing_files = True

        final_status = 'completed_with_errors' if has_missing_files else 'completed'
        app.db.update_media_item_slicing_status_by_uid(unique_id, final_status)
        
        app.logger.info("media_api", f"Верификация для UID {unique_id} завершена. Итоговый статус: {final_status}")
        return jsonify({"status": final_status, "has_missing_files": has_missing_files})

    except Exception as e:
        app.logger.error("media_api", f"Ошибка верификации файлов для UID {unique_id}: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500
    
def _run_deep_adoption_task(app, series_id):
    """
    Фоновая задача для выполнения глубокого усыновления.
    Содержит логику, которую мы убрали из MonitoringAgent.
    """
    with app.app_context():
        logger = app.logger
        db = app.db
        
        logger.info("deep_adoption", f"Запуск глубокого усыновления для series_id: {series_id}")
        series = db.get_series(series_id)
        if not series:
            logger.error("deep_adoption", f"Сериал {series_id} не найден.")
            return

        formatter = FilenameFormatter(logger)
        items_to_check = db.get_media_items_for_series(series_id)
        changed = False

        for item in items_to_check:
            # Ищем компиляции, для которых еще не было проверки глав
            is_potential_compilation = (
                bool(item.get('episode_end')) and
                item.get('status') == 'pending' and
                not item.get('chapters') and
                item.get('plan_status') == 'in_plan_compilation'
            )

            if not is_potential_compilation:
                continue

            logger.info("deep_adoption", f"Проверка глав для компиляции UID {item['unique_id']}...")
            try:
                chapters = get_chapters(item['source_url'])
                if not chapters:
                    logger.warning("deep_adoption", f"Не удалось получить оглавление для UID {item['unique_id']}.")
                    continue

                db.update_media_item_chapters(item['unique_id'], json.dumps(chapters))
                
                expected_children_count = len(chapters)
                found_children_count = 0
                
                compilation_metadata = build_final_metadata(series, item, {})
                
                for i, chapter in enumerate(chapters):
                    episode_number = item['episode_start'] + i
                    
                    child_metadata = compilation_metadata.copy()
                    child_metadata['episode'] = episode_number
                    child_metadata.pop('start', None); child_metadata.pop('end', None)

                    expected_filename = formatter.format_filename(series, child_metadata)
                    expected_path = os.path.join(series['save_path'], expected_filename)

                    if os.path.exists(expected_path):
                        db.add_sliced_file_if_not_exists(series_id, item['unique_id'], episode_number, expected_filename)
                        found_children_count += 1
                
                if found_children_count == expected_children_count and expected_children_count > 0:
                    logger.info("deep_adoption", f"УСПЕХ! Все {found_children_count} нарезанных файлов для UID {item['unique_id']} найдены. Усыновляем компиляцию.")
                    db.update_media_item_slicing_status(item['unique_id'], 'completed')
                    db.set_media_item_ignored_status_by_uid(item['unique_id'], True)
                    db.update_media_item_download_status(item['unique_id'], 'completed')
                    db.update_media_item_filename(item['unique_id'], None)
                    changed = True
            
            except Exception as e:
                logger.error("deep_adoption", f"Ошибка во время усыновления для UID {item['unique_id']}: {e}", exc_info=True)

        if changed:
            app.status_manager.sync_vk_statuses(series_id)
        
        logger.info("deep_adoption", f"Глубокое усыновление для series_id: {series_id} завершено.")


@media_bp.route('/series/<int:series_id>/deep-adoption', methods=['POST'])
def deep_adoption(series_id):
    """
    Запускает разовую задачу глубокого усыновления в фоновом потоке.
    """
    try:
        flask_app = app._get_current_object()
        thread = threading.Thread(target=_run_deep_adoption_task, args=(flask_app, series_id))
        thread.start()
        return jsonify({"success": True, "message": "Процесс глубокого усыновления запущен в фоновом режиме."})
    except Exception as e:
        app.logger.error("media_api", f"Ошибка запуска глубокого усыновления: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@media_bp.route('/media-items/<string:unique_id>/chapters/filtered', methods=['POST'])
def get_filtered_chapters(unique_id):
    """
    Получает оглавление для видео и применяет фильтрацию мусорных глав.
    Возвращает как отфильтрованные главы, так и информацию о мусорных.
    """
    item = app.db.get_media_item_by_uid(unique_id)
    if not item:
        return jsonify({"error": "Медиа-элемент не найден"}), 404

    video_url = item.get('source_url')
    if not video_url:
        return jsonify({"error": "URL видео не найден"}), 400

    try:
        # Получаем главы
        chapters_list = get_chapters(video_url)
        if not chapters_list:
            return jsonify({"chapters": [], "filtered_chapters": [], "garbage_chapters": []})
        
        # Применяем фильтрацию
        filtered_chapters = ChapterFilter.filter_chapters(chapters_list)
        garbage_chapters = ChapterFilter.get_garbage_chapters(chapters_list)
        
        # Сохраняем оригинальные главы в БД
        chapters_json = json.dumps(chapters_list)
        app.db.update_media_item_chapters(unique_id, chapters_json)
        
        # Сохраняем отфильтрованные главы в БД
        filtered_chapters_json = json.dumps(filtered_chapters)
        app.db.update_media_item_filtered_chapters(unique_id, filtered_chapters_json)
        
        # Проверяем совпадение количества отфильтрованных глав с ожидаемым
        expected_count = (item.get('episode_end', 0) - item.get('episode_start', 0) + 1)
        if len(filtered_chapters) == expected_count:
            app.db.update_media_item_slicing_status(unique_id, 'pending')
            status_message = f"Количество отфильтрованных глав ({len(filtered_chapters)}) совпало с ожидаемым."
        else:
            status_message = f"Количество отфильтрованных глав ({len(filtered_chapters)}) НЕ совпадает с ожидаемым ({expected_count})."
        
        return jsonify({
            "chapters": chapters_list,
            "filtered_chapters": filtered_chapters,
            "garbage_chapters": garbage_chapters,
            "expected_count": expected_count,
            "status_message": status_message
        })
    except Exception as e:
        app.logger.error("media_api", f"Ошибка фильтрации глав для UID {unique_id}: {e}", exc_info=True)
        return jsonify({"error": "Не удалось отфильтровать оглавление"}), 500

@media_bp.route('/media-items/<string:unique_id>/chapters/mark-garbage', methods=['POST'])
def mark_garbage_chapters(unique_id):
    """
    Позволяет пользователю вручную отметить главы как мусорные.
    """
    item = app.db.get_media_item_by_uid(unique_id)
    if not item:
        return jsonify({"error": "Медиа-элемент не найден"}), 404
    
    data = request.get_json()
    garbage_indices = data.get('garbage_indices', [])
    
    if not isinstance(garbage_indices, list):
        return jsonify({"error": "garbage_indices должен быть списком"}), 400
    
    try:
        # Получаем текущие главы из БД
        chapters_json = item.get('chapters')
        if not chapters_json:
            return jsonify({"error": "Главы не найдены в БД. Сначала получите главы."}), 400
        
        chapters_list = json.loads(chapters_json)
        
        # Применяем ручную разметку
        marked_chapters = ChapterFilter.mark_chapters_manually(chapters_list, garbage_indices)
        
        # Разделяем на хорошие и мусорные
        filtered_chapters = [ch for ch in marked_chapters if not ch.get('is_garbage')]
        garbage_chapters = [ch for ch in marked_chapters if ch.get('is_garbage')]
        
        # Сохраняем отфильтрованные главы в БД
        filtered_chapters_json = json.dumps(filtered_chapters)
        app.db.update_media_item_filtered_chapters(unique_id, filtered_chapters_json)
        
        # Проверяем совпадение с ожидаемым количеством
        expected_count = (item.get('episode_end', 0) - item.get('episode_start', 0) + 1)
        if len(filtered_chapters) == expected_count:
            app.db.update_media_item_slicing_status(unique_id, 'pending')
            status_message = f"После ручной разметки количество глав ({len(filtered_chapters)}) совпадает с ожидаемым."
        else:
            status_message = f"После ручной разметки количество глав ({len(filtered_chapters)}) НЕ совпадает с ожидаемым ({expected_count})."
        
        return jsonify({
            "chapters": marked_chapters,
            "filtered_chapters": filtered_chapters,
            "garbage_chapters": garbage_chapters,
            "expected_count": expected_count,
            "status_message": status_message
        })
    except Exception as e:
        app.logger.error("media_api", f"Ошибка ручной разметки глав для UID {unique_id}: {e}", exc_info=True)
        return jsonify({"error": "Не удалось разметить главы"}), 500

@media_bp.route('/media-items/<string:unique_id>/slice-with-filter', methods=['POST'])
def create_slice_task_with_filter(unique_id):
    """
    Создает задачу на нарезку для указанного медиа-элемента с учетом фильтрации глав.
    """
    data = request.get_json() or {}
    garbage_indices = data.get('garbage_indices', [])
    
    try:
        item = app.db.get_media_item_by_uid(unique_id)
        if not item:
            return jsonify({"success": False, "error": "Медиа-элемент не найден"}), 404
        
        allowed_statuses = ['none', 'completed_with_errors', 'error']
        if item.get('slicing_status') not in allowed_statuses:
            return jsonify({"success": False, "error": "Задача на нарезку уже в очереди или была успешно завершена без ошибок."}), 409

        # Получаем главы
        chapters_json = item.get('chapters')
        if not chapters_json:
            return jsonify({"success": False, "error": "Главы не найдены. Сначала получите главы."}), 400
        
        chapters_list = json.loads(chapters_json)
        
        # Применяем фильтрацию, если указаны индексы
        if garbage_indices:
            marked_chapters = ChapterFilter.mark_chapters_manually(chapters_list, garbage_indices)
            filtered_chapters = [ch for ch in marked_chapters if not ch.get('is_garbage')]
        else:
            # Автоматическая фильтрация
            filtered_chapters = ChapterFilter.filter_chapters(chapters_list)
        
        # Проверяем, что количество глав совпадает с ожидаемым
        expected_count = (item.get('episode_end', 0) - item.get('episode_start', 0) + 1)
        if len(filtered_chapters) != expected_count:
            return jsonify({
                "success": False,
                "error": f"Количество отфильтрованных глав ({len(filtered_chapters)}) не совпадает с ожидаемым ({expected_count}).",
                "filtered_chapters": filtered_chapters,
                "expected_count": expected_count
            }), 400
        
        # Обновляем главы в БД (только отфильтрованные)
        filtered_chapters_json = json.dumps(filtered_chapters)
        app.db.update_media_item_chapters(unique_id, filtered_chapters_json)
        app.db.update_media_item_filtered_chapters(unique_id, filtered_chapters_json)
        
        # Удаляем старые записи о файлах и старую задачу
        deleted_files_count = app.db.delete_sliced_files_for_source(unique_id)
        if deleted_files_count > 0:
            app.logger.info("media_api", f"Удалено {deleted_files_count} старых записей о нарезанных файлах для UID {unique_id} перед повторной нарезкой.")
        
        app.db.delete_slicing_task_by_uid(unique_id)

        # Создаем новую задачу в очереди и обновляем статус
        app.db.create_slicing_task(unique_id, item['series_id'])
        app.db.update_media_item_slicing_status(unique_id, 'pending')
        
        app.slicing_agent._broadcast_queue_update()
        
        return jsonify({
            "success": True,
            "message": "Задача на нарезку с фильтрацией успешно создана.",
            "filtered_chapters_count": len(filtered_chapters)
        })
    except Exception as e:
        app.logger.error("media_api", f"Ошибка создания задачи на нарезку с фильтрацией для UID {unique_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500