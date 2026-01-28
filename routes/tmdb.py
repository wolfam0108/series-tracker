from flask import Blueprint, request, jsonify, current_app
from utils.tmdb_client import TMDBClient

tmdb_bp = Blueprint('tmdb', __name__, url_prefix='/api/tmdb')

def get_client():
    return TMDBClient(current_app.db, current_app.logger)

@tmdb_bp.route('/search', methods=['POST'])
def search():
    data = request.get_json()
    query = data.get('query')
    if not query:
        return jsonify({"success": False, "error": "Query is required"}), 400
    
    client = get_client()
    if not client.token:
        return jsonify({"success": False, "error": "Токен TMDB не настроен"}), 400
        
    results = client.search_series(query)
    
    # Format results for frontend
    formatted = []
    for res in results:
        formatted.append({
            "id": res.get('id'),
            "name": res.get('name'),
            "original_name": res.get('original_name'),
            "year": (res.get('first_air_date') or "")[:4],
            "poster_path": res.get('poster_path'),
            "overview": res.get('overview') or ""
        })
        
    return jsonify({"success": True, "results": formatted})

@tmdb_bp.route('/details/<int:tmdb_id>', methods=['GET'])
def details(tmdb_id):
    client = get_client()
    data = client.get_series_details(tmdb_id)
    if not data:
        return jsonify({"success": False, "error": "Not found"}), 404
        
    seasons = []
    for s in data.get('seasons', []):
        seasons.append({
            "season_number": s.get('season_number'),
            "episode_count": s.get('episode_count'),
            "air_date": s.get('air_date'),
            "name": s.get('name')
        })
        
    return jsonify({
        "success": True, 
        "seasons": seasons,
        "name": data.get('name'),
        "poster_path": data.get('poster_path'),
        "status": data.get('status')
    })
