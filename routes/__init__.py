from flask import send_from_directory, Blueprint

# Импортируем чертежи из каждого модуля
from .series import series_bp
from .settings import settings_bp
from .system import system_bp
# --- ИЗМЕНЕНИЕ: Импортируем ОБА новых чертежа ---
from .parser import profiles_bp, rules_bp

def init_all_routes(app):
    """
    Регистрирует все чертежи маршрутов в приложении Flask.
    """
    main_bp = Blueprint('main', __name__)

    @main_bp.route('/')
    def index():
        return send_from_directory(app.template_folder, 'index.html')

    app.register_blueprint(main_bp)
    
    # Регистрируем чертежи для API
    app.register_blueprint(series_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(system_bp)
    # --- ИЗМЕНЕНИЕ: Регистрируем ОБА новых чертежа ---
    app.register_blueprint(profiles_bp)
    app.register_blueprint(rules_bp)