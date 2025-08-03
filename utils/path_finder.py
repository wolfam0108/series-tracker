# Файл: utils/path_finder.py

import os
import sys
import shutil
from flask import current_app as app

def get_executable_path(name: str) -> str:
    """
    Находит полный путь к исполняемому файлу, принудительно проверяя стандартные
    системные пути, чтобы обойти проблемы с окружением сервисов.
    """
    try:
        # 1. Приоритет для исполняемого файла в виртуальном окружении
        venv_executable_path = os.path.join(os.path.dirname(sys.executable), name)
        if os.path.exists(venv_executable_path):
            app.logger.info("path_finder", f"'{name}' найден в venv: {venv_executable_path}")
            return venv_executable_path
        
        # --- ГЛАВНОЕ ИЗМЕНЕНИЕ ---
        # 2. Создаем расширенный список путей для поиска, включая стандартные системные.
        current_path = os.environ.get('PATH', '')
        # Стандартные пути, где обычно лежат бинарные файлы в Linux
        system_paths = ['/usr/bin', '/bin', '/usr/local/bin']
        
        # Объединяем пути из окружения и стандартные, убирая дубликаты
        search_paths_list = current_path.split(os.pathsep)
        for p in system_paths:
            if p not in search_paths_list:
                search_paths_list.append(p)
        
        final_search_path = os.pathsep.join(search_paths_list)
        app.logger.info("path_finder", f"Поиск '{name}' в расширенном PATH: {final_search_path}")
        
        # 3. Ищем программу в расширенном списке путей
        system_path_executable = shutil.which(name, path=final_search_path)
        if system_path_executable:
            app.logger.info("path_finder", f"'{name}' найден через shutil.which: {system_path_executable}")
            return system_path_executable
        
        # 4. Фоллбэк, если ничего не найдено
        app.logger.error("path_finder", f"'{name}' не найден. Возвращаем просто имя '{name}'.")
        return name
        
    except Exception as e:
        app.logger.error("path_finder", f"Критическая ошибка при поиске '{name}': {e}")
        return name