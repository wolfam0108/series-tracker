import re

class FilenameFormatter:
    """
    Создает чистое, стандартизированное имя файла из структурированных данных о медиа-элементе.
    """
    def __init__(self, logger):
        self.logger = logger

    def _sanitize_filename(self, name: str) -> str:
        """Удаляет недопустимые символы из имени файла."""
        # Удаляем символы, недопустимые в Windows и Linux/macOS
        sanitized_name = re.sub(r'[<>:"/\\|?*]', '', name)
        # Заменяем множественные пробелы на один
        sanitized_name = re.sub(r'\s+', ' ', sanitized_name).strip()
        return sanitized_name

    def format_filename(self, series_data: dict, media_item: dict) -> str:
        """
        Формирует имя файла.
        Пример: 'Showname s01e01 [AniDub].mp4'
        """
        series_name_en = self._sanitize_filename(series_data.get('name_en', 'Unknown Series'))
        
        extracted = media_item.get('result', {}).get('extracted', {})
        season = extracted.get('season', 1)
        episode = extracted.get('episode')
        start = extracted.get('start')
        end = extracted.get('end')
        voiceover = extracted.get('voiceover')

        season_part = f"s{str(season).zfill(2)}"
        
        episode_part = ''
        if episode is not None:
            episode_part = f"e{str(episode).zfill(2)}"
        elif start is not None and end is not None:
            episode_part = f"e{str(start).zfill(2)}-e{str(end).zfill(2)}"

        tag_part = f" [{self._sanitize_filename(voiceover)}]" if voiceover else ""

        # Собираем все части вместе
        base_name = f"{series_name_en} {season_part}{episode_part}{tag_part}"
        
        return f"{base_name}.mp4"