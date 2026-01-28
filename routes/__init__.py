from flask import send_from_directory, Blueprint
import datetime

# Импортируем чертежи из каждого модуля
from .series import series_bp
from .settings import settings_bp
from .system import system_bp
from .parser import profiles_bp, rules_bp
# --- ИЗМЕНЕНИЕ: Импортируем новый чертеж ---
from .media import media_bp
from .trackers import trackers_bp
from .filebrowser import filebrowser_bp
from .test import test_bp
from .tmdb import tmdb_bp

def init_all_routes(app):
    """
    Регистрирует все чертежи маршрутов в приложении Flask.
    """
    main_bp = Blueprint('main', __name__)

    @main_bp.route('/')
    def index():
        return send_from_directory(app.template_folder, 'index.html')
    
    @main_bp.route('/directory-picker-test')
    def directory_picker_test():
        return send_from_directory(app.template_folder, 'directory_picker_test.html')
    
    @main_bp.route('/hello-world')
    def hello_world():
        return send_from_directory(app.template_folder, 'hello_world.html')
    
    @main_bp.route('/api/hello-info')
    def hello_info():
        from flask import request, jsonify
        return jsonify({
            'ip': request.remote_addr,
            'userAgent': request.headers.get('User-Agent', 'Unknown'),
            'timestamp': str(datetime.datetime.now())
        })

    app.register_blueprint(main_bp)
    
    app.register_blueprint(series_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(profiles_bp)
    app.register_blueprint(rules_bp)
    app.register_blueprint(media_bp)
    app.register_blueprint(trackers_bp)
    app.register_blueprint(filebrowser_bp)
    app.register_blueprint(test_bp)
    app.register_blueprint(tmdb_bp)