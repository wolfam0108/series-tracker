from flask import Blueprint, jsonify, request, current_app as app
from rule_engine import RuleEngine
from scrapers.vk_scraper import VKScraper
import json

# Чертеж для управления профилями и получения/создания правил внутри профиля
profiles_bp = Blueprint('parser_profiles_api', __name__, url_prefix='/api/parser-profiles')

# Чертеж для управления отдельными правилами
rules_bp = Blueprint('parser_rules_api', __name__, url_prefix='/api/parser-rules')


@profiles_bp.route('', methods=['GET'])
def get_parser_profiles():
    profiles = app.db.get_parser_profiles()
    return jsonify(profiles)

@profiles_bp.route('', methods=['POST'])
def create_parser_profile():
    data = request.get_json()
    name = data.get('name')
    if not name:
        return jsonify({"success": False, "error": "Имя профиля не указано"}), 400
    try:
        profile_id = app.db.create_parser_profile(name)
        return jsonify({"success": True, "id": profile_id})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 409

@profiles_bp.route('/<int:profile_id>', methods=['DELETE'])
def delete_parser_profile(profile_id):
    try:
        app.db.delete_parser_profile(profile_id)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": f"Ошибка удаления: {e}"}), 500

@profiles_bp.route('/<int:profile_id>/rules', methods=['GET'])
def get_rules_for_profile(profile_id):
    rules = app.db.get_rules_for_profile(profile_id)
    return jsonify(rules)

@profiles_bp.route('/<int:profile_id>/rules', methods=['POST'])
def add_rule_to_profile(profile_id):
    data = request.get_json()
    try:
        # --- ИЗМЕНЕНИЕ: action_pattern теперь напрямую принимает JSON-строку с фронтенда ---
        rule_id = app.db.add_rule_to_profile(profile_id, data)
        return jsonify({"success": True, "id": rule_id})
    except Exception as e:
        app.logger.error("parser_api", f"POST /rules - Исключение при вызове db.add_rule_to_profile: {e}", exc_info=True)
        return jsonify({"success": False, "error": f"Ошибка добавления правила: {e}"}), 500
        
@profiles_bp.route('/scrape-titles', methods=['POST'])
def scrape_vk_titles():
    data = request.get_json()
    channel_url = data.get('channel_url')
    query = data.get('query')
    
    if not channel_url or not query:
        return jsonify({"error": "Необходимо указать и URL канала, и название для поиска"}), 400
    
    try:
        scraper = VKScraper(app.db, app.logger)
        titles_with_dates = scraper.scrape_video_data(channel_url, query)
        return jsonify(titles_with_dates)
    except Exception as e:
        app.logger.error("parser_api", f"Ошибка скрапинга VK: {e}", exc_info=True)
        return jsonify({"error": f"Ошибка на сервере при скрапинге: {str(e)}"}), 500


@rules_bp.route('/<int:rule_id>', methods=['PUT'])
def update_rule(rule_id):
    data = request.get_json()
    try:
        # --- ИЗМЕНЕНИЕ: action_pattern теперь напрямую принимает JSON-строку с фронтенда ---
        app.db.update_rule(rule_id, data)
        return jsonify({"success": True})
    except Exception as e:
        app.logger.error("parser_api", f"PUT /rules/{rule_id} - Исключение при вызове db.update_rule: {e}", exc_info=True)
        return jsonify({"success": False, "error": f"Ошибка обновления правила: {e}"}), 500

@rules_bp.route('/<int:rule_id>', methods=['DELETE'])
def delete_rule(rule_id):
    try:
        app.db.delete_rule(rule_id)
        return jsonify({"success": True})
    except Exception as e:
        app.logger.error("parser_api", f"DELETE /rules/{rule_id} - Исключение при вызове db.delete_rule: {e}", exc_info=True)
        return jsonify({"success": False, "error": f"Ошибка удаления правила: {e}"}), 500

@rules_bp.route('/reorder', methods=['POST'])
def reorder_rules():
    ordered_ids = request.get_json()
    try:
        app.db.update_rules_order(ordered_ids)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": f"Ошибка изменения порядка: {str(e)}"}), 500

@profiles_bp.route('/test', methods=['POST'])
def test_parser_rules():
    data = request.get_json()
    profile_id = data.get('profile_id')
    titles = data.get('titles', [])
    if not profile_id:
        return jsonify({"error": "profile_id не указан"}), 400
    
    engine = RuleEngine(app.db, app.logger)
    video_data = [{"title": title} for title in titles]
    results = engine.process_videos(profile_id, video_data)
    return jsonify(results)