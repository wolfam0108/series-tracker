import os
from flask import current_app as app

# --- ИЗМЕНЕНИЕ: Создаем новый модуль для управления кэшем ---

CACHE_DIR = "torrent_cache"

def _ensure_cache_dir():
    """Проверяет и создает директорию для кэша, если ее нет."""
    if not os.path.exists(CACHE_DIR):
        try:
            os.makedirs(CACHE_DIR)
            app.logger.info("file_cache", f"Создана директория для кэша: {CACHE_DIR}")
        except OSError as e:
            app.logger.error("file_cache", f"Не удалось создать директорию для кэша {CACHE_DIR}: {e}")

def get_cache_path(torrent_id: str) -> str:
    """Возвращает полный путь к кэш-файлу."""
    return os.path.join(CACHE_DIR, f"{torrent_id}.torrent")

def save_to_cache(torrent_id: str, content: bytes):
    """Сохраняет содержимое торрент-файла в кэш."""
    _ensure_cache_dir()
    file_path = get_cache_path(torrent_id)
    try:
        with open(file_path, 'wb') as f:
            f.write(content)
        if app.debug_manager.is_debug_enabled('qbittorrent'): # Используем флаг qbittorrent для логирования
            app.logger.debug("file_cache", f"Торрент ID {torrent_id} сохранен в кэш: {file_path}")
    except IOError as e:
        app.logger.error("file_cache", f"Не удалось сохранить торрент ID {torrent_id} в кэш: {e}")

def read_from_cache(torrent_id: str) -> bytes | None:
    """Читает содержимое торрент-файла из кэша. Возвращает None, если файла нет."""
    file_path = get_cache_path(torrent_id)
    if os.path.exists(file_path):
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            if app.debug_manager.is_debug_enabled('qbittorrent'):
                app.logger.debug("file_cache", f"Торрент ID {torrent_id} загружен из кэша.")
            return content
        except IOError as e:
            app.logger.error("file_cache", f"Не удалось прочитать торрент ID {torrent_id} из кэша: {e}")
            return None
    return None

def delete_from_cache(torrent_id: str):
    """Удаляет торрент-файл из кэша."""
    file_path = get_cache_path(torrent_id)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            if app.debug_manager.is_debug_enabled('qbittorrent'):
                app.logger.debug("file_cache", f"Торрент ID {torrent_id} удален из кэша.")
        except OSError as e:
            app.logger.error("file_cache", f"Не удалось удалить торрент ID {torrent_id} из кэша: {e}")