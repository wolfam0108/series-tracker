import subprocess
import os
import sys

class Downloader:
    """
    Инкапсулирует логику вызова yt-dlp для скачивания видео.
    """
    def __init__(self, logger):
        self.logger = logger

    def _get_yt_dlp_path(self) -> str:
        """
        Находит полный путь к исполняемому файлу yt-dlp.
        Приоритет отдается файлу внутри виртуального окружения.
        """
        # sys.executable - это путь к интерпретатору python (например, /path/to/venv/bin/python)
        # os.path.dirname(...) дает нам папку /path/to/venv/bin/
        venv_executable_path = os.path.join(os.path.dirname(sys.executable), 'yt-dlp')
        
        if os.path.exists(venv_executable_path):
            # Если нашли yt-dlp рядом с python в venv, используем его
            return venv_executable_path
        else:
            # Если нет, полагаемся на системный PATH
            return 'yt-dlp'

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

        yt_dlp_executable = self._get_yt_dlp_path()

        try:
            command = [
                yt_dlp_executable,
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
                # Если ошибка связана с недоступностью видео, это не наша вина
                if "Video unavailable" in error_message or "Private video" in error_message:
                    return False, "Video unavailable or private"
                return False, error_message

        except FileNotFoundError:
            self.logger.error("downloader", f"Команда '{yt_dlp_executable}' не найдена. Убедитесь, что yt-dlp установлен и доступен.")
            return False, "yt-dlp not found"
        except Exception as e:
            self.logger.error("downloader", f"Непредвиденная ошибка при запуске yt-dlp: {e}", exc_info=True)
            return False, str(e)