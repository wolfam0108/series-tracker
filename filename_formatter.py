import re
import os

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

    def format_filename(self, series_data: dict, metadata: dict, original_filename: str = None) -> str:
        """
        Формирует стандартизированное имя файла из данных сериала и извлечённых метаданных.
        Реализует иерархию приоритетов для опциональных тегов и сохраняет исходный подкаталог.
        """
        series_name_en = self._sanitize_filename(series_data.get('name_en', 'Unknown Series'))

        # --- Основные метаданные (обязательные) ---
        series_season_str = series_data.get('season')

        if series_season_str:
            # Если сезон жестко задан в свойствах сериала, используем его в приоритете.
            # Извлекаем только цифры для надежности (например, из "s02" получим 2).
            season_num_match = re.search(r'\d+', series_season_str)
            season = int(season_num_match.group(0)) if season_num_match else 1
        else:
            # Иначе, берем сезон из результатов работы фильтра, с фолбэком на 1.
            season = metadata.get('season', 1)

        episode = metadata.get('episode')
        start = metadata.get('start')
        end = metadata.get('end')

        season_part = f"s{str(season).zfill(2)}"

        episode_part = ''
        if episode is not None:
            episode_part = f"e{str(episode).zfill(2)}"
        elif start is not None and end is not None:
            episode_part = f"e{str(start).zfill(2)}-e{str(end).zfill(2)}"
        elif start is not None:
            episode_part = f"e{str(start).zfill(2)}"

        # --- Опциональные метаданные с иерархией приоритетов ---
        voiceover = metadata.get('voiceover')
        # Ручные настройки из свойств сериала теперь имеют наивысший приоритет
        quality = series_data.get('quality_override') or metadata.get('quality')
        resolution = series_data.get('resolution_override') or metadata.get('resolution')

        # --- Сборка имени ---
        parts = [series_name_en, f"{season_part}{episode_part}"]

        # 1. Тег (озвучка)
        if voiceover:
            parts.append(f"[{self._sanitize_filename(voiceover)}]")

        # 2. Качество
        if quality:
            parts.append(self._sanitize_filename(quality))

        # 3. Разрешение (с добавлением "p")
        if resolution:
            resolution_str = str(resolution)
            # Если значение - это просто число, добавляем 'p'.
            # Если это уже строка (например, '1080p WEB-DL'), используем как есть.
            if resolution_str.isdigit():
                parts.append(f"{resolution_str}p")
            else:
                parts.append(self._sanitize_filename(resolution_str))

        # --- Определение расширения файла ---
        extension = ".mkv"
        if series_data.get('source_type') == 'vk_video':
            extension = ".mp4"
        elif original_filename:
            _, ext = os.path.splitext(original_filename)
            if ext:
                extension = ext.lower()

        final_basename = " ".join(filter(None, parts)) + extension

        # --- ИСПРАВЛЕНИЕ: Гарантированное сохранение пути ---
        if original_filename:
            # os.path.split() надежно разделяет путь на (каталог, имя_файла)
            original_dir, _ = os.path.split(original_filename)
            if original_dir:
                # Собираем новый полный путь
                return os.path.join(original_dir, final_basename).replace("\\", "/")

        return final_basename