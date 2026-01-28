import os
from flask import Blueprint, jsonify, request

filebrowser_bp = Blueprint('filebrowser', __name__)

def get_system_root():
    """Определяет реальную корневую директорию файловой системы"""
    # Возвращаем корневой каталог файловой системы
    return '/'

@filebrowser_bp.route('/api/directories', methods=['GET'])
def get_directories():
    """Получить список директорий для указанного пути"""
    path = request.args.get('path', '/')
    
    # Безопасность: ограничиваем доступ только к определенным директориям
    allowed_roots = ['/', '/nas', '/home', '/tmp']
    
    # Если путь пустой или только '/', устанавливаем реальную корневую директорию
    if not path or path == '/':
        path = get_system_root()
    
    # Проверяем, что путь начинается с разрешенного корня
    if not any(path.startswith(root) for root in allowed_roots):
        return jsonify({'error': 'Доступ к этому пути запрещен'}), 403
    
    # Нормализуем путь
    path = os.path.normpath(path)
    
    # Проверяем существование пути
    if not os.path.exists(path):
        return jsonify({'error': 'Путь не существует'}), 404
    
    # Проверяем, что это директория
    if not os.path.isdir(path):
        return jsonify({'error': 'Указанный путь не является директорией'}), 400
    
    try:
        # Получаем список элементов в директории
        items = []
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            
            # Добавляем только директории
            if os.path.isdir(item_path):
                items.append({
                    'name': item,
                    'path': item_path,
                    'type': 'directory'
                })
        
        # Сортируем по имени
        items.sort(key=lambda x: x['name'].lower())
        
        return jsonify({
            'path': path,
            'items': items
        })
    
    except PermissionError:
        return jsonify({'error': 'Нет доступа к этой директории'}), 403
    except Exception as e:
        return jsonify({'error': f'Ошибка при чтении директории: {str(e)}'}), 500