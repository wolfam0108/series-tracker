import subprocess
import json
from typing import List, Dict
from flask import current_app as app
# --- ИЗМЕНЕНИЕ: Импортируем новую функцию ---
from .path_finder import get_executable_path

def _format_seconds(seconds: float) -> str:
    """Вспомогательная функция для преобразования секунд в формат HH:MM:SS."""
    if not isinstance(seconds, (int, float)):
        return "00:00:00"
    
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    return f"{hours:02}:{minutes:02}:{secs:02}"

def get_chapters(video_url: str) -> List[Dict]:
    """
    Запускает yt-dlp для получения глав в формате JSON и надежно обрабатывает результат.
    """
    # --- ИЗМЕНЕНИЕ: Получаем абсолютный путь к yt-dlp ---
    yt_dlp_executable = get_executable_path('yt-dlp')

    command = [
        yt_dlp_executable, # <-- Используем переменную с путём
        '--print', '%(chapters)j',
        '--no-warnings',
        '--no-progress',
        '--no-cache-dir',
        video_url
    ]
    
    app.logger.info("chapter_parser_debug", f"Executing command: {' '.join(command)}")

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            encoding='utf-8',
            timeout=180
        )

        if result.returncode != 0:
            app.logger.warning("chapter_parser_debug", f"yt-dlp exited with code {result.returncode}. STDERR:\n{result.stderr}")
            return []

        output = result.stdout.strip()

        if not output:
            app.logger.info("chapter_parser_debug", "Оглавление не найдено (yt-dlp вернул пустой результат).")
            return []

        try:
            chapters_data = json.loads(output)
        except json.JSONDecodeError:
            app.logger.warning("chapter_parser_debug", f"Не удалось распознать JSON. Вывод от yt-dlp: '{output}'")
            return []

        if not chapters_data:
            return []

        parsed_chapters = []
        for chap in chapters_data:
            parsed_chapters.append({
                "time": _format_seconds(chap.get("start_time")),
                "title": chap.get("title", "Без названия")
            })
        
        app.logger.info("chapter_parser_debug", f"Успешно найдено и обработано {len(parsed_chapters)} глав.")
        return parsed_chapters

    except subprocess.TimeoutExpired:
        app.logger.error("chapter_parser_debug", "Timeout! Процесс был принудительно завершен.")
        raise Exception("Превышено время ожидания от yt-dlp (180 секунд)")
    
    except Exception as e:
        # --- ИЗМЕНЕНИЕ: Улучшаем сообщение об ошибке ---
        if isinstance(e, FileNotFoundError):
             app.logger.error("chapter_parser_debug", f"Команда '{yt_dlp_executable}' не найдена. Убедитесь, что yt-dlp установлен в venv.", exc_info=True)
             raise Exception(f"yt-dlp не найден по пути: {yt_dlp_executable}")
        
        app.logger.error("chapter_parser_debug", f"Произошла непредвиденная ошибка: {e}", exc_info=True)
        raise Exception(f"Произошла ошибка при обработке в yt-dlp: {e}")
