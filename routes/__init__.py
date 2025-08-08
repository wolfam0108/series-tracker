from flask import send_from_directory, Blueprint

# Импортируем чертежи из каждого модуля
from .series import series_bp
from .settings import settings_bp
from .system import system_bp
from .parser import profiles_bp, rules_bp
# --- ИЗМЕНЕНИЕ: Импортируем новый чертеж ---
from .media import media_bp
from .trackers import trackers_bp

def init_all_routes(app):
    """
    Регистрирует все чертежи маршрутов в приложении Flask.
    """
    main_bp = Blueprint('main', __name__)

    @main_bp.route('/')
    def index():
        return send_from_directory(app.template_folder, 'index.html')

    app.register_blueprint(main_bp)
    
    app.register_blueprint(series_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(profiles_bp)
    app.register_blueprint(rules_bp)
    app.register_blueprint(media_bp)
    app.register_blueprint(trackers_bp)