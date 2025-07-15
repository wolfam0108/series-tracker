from flask import Blueprint, jsonify, request, current_app as app

media_bp = Blueprint('media_api', __name__, url_prefix='/api/media-items')

@media_bp.route('/<int:item_id>/ignore', methods=['PUT'])
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