import os
from flask import Blueprint, jsonify, request, current_app as app
import json
from utils.chapter_parser import get_chapters # Импортируем новый парсер

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

        # --- НАЧАЛО ИЗМЕНЕНИЯ ---
        expected_count = (item.get('episode_end', 0) - item.get('episode_start', 0) + 1)
        if chapters_list and len(chapters_list) == expected_count:
            app.db.update_media_item_slicing_status(unique_id, 'pending')
            app.logger.info("media_api", f"Количество глав ({len(chapters_list)}) совпало с ожидаемым. Статус нарезки для UID {unique_id} изменен на 'pending'.")
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---

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
        app.db.set_media_item_ignored_status(item_id, is_ignored)
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
        app.db.set_media_item_ignored_status_by_uid(unique_id, is_ignored)
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
        sliced_files = app.db.get_sliced_files_for_source(unique_id)
        if not sliced_files:
            # Если файлов в БД нет, но проверка вызвана, значит что-то не так. Сбрасываем.
            app.db.update_media_item_slicing_status_by_uid(unique_id, 'none')
            return jsonify({"status": "none", "message": "Записи о нарезанных файлах не найдены, статус сброшен."})

        has_missing_files = False
        for file_record in sliced_files:
            file_exists = os.path.exists(file_record['file_path'])
            
            if file_exists and file_record['status'] == 'missing':
                app.db.update_sliced_file_status(file_record['id'], 'completed')
            elif not file_exists and file_record['status'] == 'completed':
                app.db.update_sliced_file_status(file_record['id'], 'missing')
                has_missing_files = True
            elif not file_exists:
                has_missing_files = True

        # Обновляем статус родительского элемента
        final_status = 'completed_with_errors' if has_missing_files else 'completed'
        app.db.update_media_item_slicing_status_by_uid(unique_id, final_status)
        
        app.logger.info("media_api", f"Верификация для UID {unique_id} завершена. Итоговый статус: {final_status}")
        return jsonify({"status": final_status, "has_missing_files": has_missing_files})

    except Exception as e:
        app.logger.error("media_api", f"Ошибка верификации файлов для UID {unique_id}: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500