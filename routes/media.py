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
    Получает оглавление для видео, сохраняет его в БД и возвращает клиенту.
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