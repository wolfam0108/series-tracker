from flask import Blueprint, jsonify, request, current_app as app

trackers_bp = Blueprint('trackers_api', __name__, url_prefix='/api/trackers')

@trackers_bp.route('', methods=['GET'])
def get_trackers():
    """Возвращает список всех трекеров и их настроек."""
    try:
        trackers = app.db.get_all_trackers()
        return jsonify(trackers)
    except Exception as e:
        app.logger.error("trackers_api", f"Ошибка получения списка трекеров: {e}", exc_info=True)
        return jsonify({"error": "Не удалось получить список трекеров"}), 500

@trackers_bp.route('/<int:tracker_id>', methods=['PUT'])
def update_tracker(tracker_id):
    """Обновляет данные для одного трекера (пока только зеркала)."""
    data = request.get_json()
    mirrors = data.get('mirrors')

    if mirrors is None:
        return jsonify({"error": "Список зеркал не предоставлен"}), 400
    
    try:
        app.db.update_tracker_mirrors(tracker_id, mirrors)
        return jsonify({"success": True, "message": "Список зеркал обновлен."})
    except Exception as e:
        app.logger.error("trackers_api", f"Ошибка обновления зеркал для трекера {tracker_id}: {e}", exc_info=True)
        return jsonify({"error": "Ошибка на сервере при обновлении зеркал"}), 500