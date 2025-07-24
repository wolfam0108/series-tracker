import subprocess
import os
# --- ИЗМЕНЕНИЕ: Импортируем новую функцию ---
from utils.path_finder import get_executable_path

class Downloader:
    """
    Инкапсулирует логику вызова yt-dlp для скачивания видео.
    """
    def __init__(self, logger):
        self.logger = logger

    # --- ИЗМЕНЕНИЕ: Этот метод больше не нужен, его заменит утилита ---
    # def _get_yt_dlp_path(self) -> str: ...

    def download_video(self, video_url: str, full_output_path: str) -> (bool, str):
        """
        Запускает yt-dlp для скачивания видео.
        Возвращает (True/False, сообщение_об_ошибке).
        """
        self.logger.info("downloader", f"Начало загрузки: {video_url} -> {full_output_path}")
        
        output_dir = os.path.dirname(full_output_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            self.logger.info("downloader", f"Создана директория: {output_dir}")

        if os.path.exists(full_output_path):
            self.logger.warning("downloader", f"Файл {full_output_path} уже существует. Пропуск загрузки.")
            return True, "File already exists"

        # --- ИЗМЕНЕНИЕ: Используем новую функцию ---
        yt_dlp_executable = get_executable_path('yt-dlp')

        try:
            command = [
                yt_dlp_executable, # <-- Используем переменную с путём
                '--quiet',
                '--no-warnings',
                '--merge-output-format', 'mp4',
                '-o', full_output_path,
                video_url
            ]
            
            result = subprocess.run(command, capture_output=True, text=True, check=False, encoding='utf-8')

            if result.returncode == 0:
                self.logger.info("downloader", f"Успешно скачан файл: {full_output_path}")
                return True, ""
            else:
                error_message = result.stderr.strip()
                self.logger.error("downloader", f"Ошибка yt-dlp при скачивании {video_url}. Код: {result.returncode}. Ошибка: {error_message}")
                if "Video unavailable" in error_message or "Private video" in error_message:
                    return False, "Video unavailable or private"
                return False, error_message

        except FileNotFoundError:
            self.logger.error("downloader", f"Команда '{yt_dlp_executable}' не найдена. Убедитесь, что yt-dlp установлен в venv.")
            return False, f"yt-dlp не найден по пути: {yt_dlp_executable}"
        except Exception as e:
            self.logger.error("downloader", f"Непредвиденная ошибка при запуске yt-dlp: {e}", exc_info=True)
            return False, str(e)
