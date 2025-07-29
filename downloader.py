# downloader.py

import subprocess
import os
import re # <<< Добавляем импорт re
from typing import Callable, Dict
from utils.path_finder import get_executable_path

class Downloader:
    def __init__(self, logger):
        self.logger = logger
        # Регулярное выражение для парсинга строки прогресса от yt-dlp
        self.progress_regex = re.compile(
            r"\[download\]\s+(?P<percent>[\d\.]+)%\s+of\s+~?(?P<size>[\d\.]+\w+)\s+at\s+(?P<speed>[\d\.]+\w+/s)\s+ETA\s+(?P<eta>[\d:]+)"
        )

    def _parse_size_to_bytes(self, size_str: str) -> int:
        """Конвертирует строку '12.34MiB/s' в байты/с."""
        size_str = size_str.lower().replace('/s', '')
        if 'kib' in size_str:
            return int(float(size_str.replace('kib', '').strip()) * 1024)
        if 'mib' in size_str:
            return int(float(size_str.replace('mib', '').strip()) * 1024 * 1024)
        if 'gib' in size_str:
            return int(float(size_str.replace('gib', '').strip()) * 1024 * 1024 * 1024)
        return 0

    def _parse_eta_to_seconds(self, eta_str: str) -> int:
        """Конвертирует строку '01:33' в секунды."""
        parts = eta_str.split(':')
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        return 0

    # <<< ПОЛНОСТЬЮ ЗАМЕНИТЕ СТАРЫЙ МЕТОД download_video НА ЭТОТ >>>
    def download_video(self, video_url: str, full_output_path: str, progress_callback: Callable[[Dict], None]) -> (bool, str):
        self.logger.info("downloader", f"Начало загрузки: {video_url} -> {full_output_path}")
        
        output_dir = os.path.dirname(full_output_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        if os.path.exists(full_output_path):
            self.logger.warning("downloader", f"Файл {full_output_path} уже существует. Пропуск.")
            return True, "File already exists"

        yt_dlp_executable = get_executable_path('yt-dlp')

        command = [
            yt_dlp_executable,
            '--progress',          # Включаем вывод прогресса
            '--newline',           # Каждое обновление на новой строке
            '--merge-output-format', 'mp4',
            '-o', full_output_path,
            video_url
        ]
        
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace'
            )

            for line in iter(process.stdout.readline, ''):
                match = self.progress_regex.search(line)
                if match:
                    data = match.groupdict()
                    progress_data = {
                        'progress': int(float(data['percent'])),
                        'total_size_mb': round(self._parse_size_to_bytes(data['size']) / (1024*1024), 2),
                        'dlspeed': self._parse_size_to_bytes(data['speed']),
                        'eta': self._parse_eta_to_seconds(data['eta'])
                    }
                    progress_callback(progress_data)
            
            process.wait() # Ждем завершения процесса
            
            if process.returncode == 0:
                self.logger.info("downloader", f"Успешно скачан файл: {full_output_path}")
                # Отправляем финальный 100% статус
                progress_callback({'progress': 100, 'dlspeed': 0, 'eta': 0})
                return True, ""
            else:
                error_message = process.stderr.read().strip()
                self.logger.error("downloader", f"Ошибка yt-dlp. Код: {process.returncode}. Ошибка: {error_message}")
                if "Video unavailable" in error_message or "Private video" in error_message:
                    return False, "Video unavailable or private"
                return False, error_message

        except FileNotFoundError:
            return False, f"yt-dlp не найден по пути: {yt_dlp_executable}"
        except Exception as e:
            self.logger.error("downloader", f"Непредвиденная ошибка при запуске yt-dlp: {e}", exc_info=True)
            return False, str(e)