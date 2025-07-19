import subprocess
import json
from typing import List, Dict
from flask import current_app as app

def _format_seconds(seconds: float) -> str:
    """Вспомогательная функция для преобразования секунд в формат HH:MM:SS."""
    if seconds is None:
        return "00:00:00"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(round(s)):02d}"

def get_chapters(video_url: str) -> List[Dict]:
    """
    Запускает yt-dlp с корректной командой для получения глав в формате JSON.
    """
    try:
        # --- ФИНАЛЬНАЯ ИСПРАВЛЕННАЯ КОМАНДА ---
        command = [
            'yt-dlp',
            '--print', '%(chapters)j', # Правильный синтаксис для вывода глав в JSON
            '--no-warnings',
            '--no-progress',
            '--no-cache-dir',
            video_url
        ]
        # --- КОНЕЦ ИСПРАВЛЕНИЯ ---
        
        app.logger.info("chapter_parser_debug", f"Executing command: {' '.join(command)}")

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
        if not output or output == 'null': # yt-dlp выведет 'null', если глав нет
            app.logger.info("chapter_parser_debug", "No chapters found (yt-dlp returned empty or null output).")
            return []

        chapters_data = json.loads(output)
        
        if not chapters_data:
            return []

        parsed_chapters = []
        for chap in chapters_data:
            parsed_chapters.append({
                "time": _format_seconds(chap.get("start_time")),
                "title": chap.get("title", "Без названия")
            })
        
        app.logger.info("chapter_parser_debug", f"Successfully found and parsed {len(parsed_chapters)} chapters.")
        return parsed_chapters

    except subprocess.TimeoutExpired:
        app.logger.error("chapter_parser_debug", "Timeout! The process was forcibly terminated.")
        raise Exception("Превышено время ожидания от yt-dlp (180 секунд)")
        
    except Exception as e:
        app.logger.error("chapter_parser_debug", f"An unexpected error occurred: {e}", exc_info=True)
        raise Exception(f"An error occurred while processing with yt-dlp: {e}")