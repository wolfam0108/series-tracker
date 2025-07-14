from flask import send_from_directory, Blueprint

# Импортируем чертежи из каждого модуля
from .series import series_bp
from .settings import settings_bp
from .system import system_bp

def init_all_routes(app):
    """
    Регистрирует все чертежи маршрутов в приложении Flask.
    """
    # Создаем главный чертеж для статики и корневого маршрута
    main_bp = Blueprint('main', __name__)

    @main_bp.route('/')
    def index():
        return send_from_directory(app.template_folder, 'index.html')

    app.register_blueprint(main_bp)
    
    # Регистрируем чертежи для API
    app.register_blueprint(series_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(system_bp)