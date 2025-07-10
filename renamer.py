import re
from typing import List, Optional, Dict, Any
from flask import current_app as app

class Renamer:
    def __init__(self, logger, db):
        self.logger = logger
        self.db = db

    def _compile_pattern(self, user_pattern: str):
        """
        Компилирует пользовательский паттерн в регулярное выражение.
        - Заменяет последовательности 'X' на r'(\\d{n})', где n - длина последовательности.
        - Заменяет '*' на r'.*?'.
        - Обрабатывает только первую группу 'X' как захватывающую.
        """
        # 1. Находим первую последовательность 'X', чтобы сделать ее захватывающей группой.
        match = re.search(r'(X+)', user_pattern)
        
        temp_pattern = user_pattern
        
        if match:
            x_sequence = match.group(1)
            n = len(x_sequence)
            # Заменяем первую найденную последовательность X на уникальный плейсхолдер.
            placeholder = "___CAPTURE_GROUP___"
            temp_pattern = temp_pattern.replace(x_sequence, placeholder, 1)

        # 2. Экранируем весь временный паттерн.
        regex_pattern = re.escape(temp_pattern)
        
        # 3. Заменяем любые оставшиеся (и теперь экранированные) 'X' на незахватывающие группы цифр.
        # Это обеспечивает корректную работу, даже если пользователь нарушил правило "одна группа X на паттерн".
        regex_pattern = regex_pattern.replace(re.escape('X'), r'(?:\d)')

        # 4. Вставляем на место плейсхолдера настоящую захватывающую группу с нужным количеством разрядов.
        if match:
            regex_pattern = regex_pattern.replace(placeholder, fr'(\d{{{n}}})')
            
        # 5. Заменяем экранированный символ '*' на его аналог в regex.
        regex_pattern = regex_pattern.replace(re.escape('*'), r'.*?')

        # 6. Добавляем якоря начала и конца строки, если паттерн не начинается/заканчивается на '*'.
        if not user_pattern.startswith('*'):
            regex_pattern = '^' + regex_pattern
        if not user_pattern.endswith('*'):
            regex_pattern += '$'
        
        try:
            return re.compile(regex_pattern, re.IGNORECASE), None
        except re.error as e:
            return None, f"Ошибка в паттерне: {e}"

    def test_user_pattern(self, user_pattern: str, filename: str) -> str:
        compiled_pattern, error = self._compile_pattern(user_pattern)
        if error:
            return error

        match = compiled_pattern.search(filename)
        if match:
            if 'X' in user_pattern:
                # Проверяем, есть ли у нас захваченные группы
                if match.groups():
                    return f"Успех! Извлечено: '{match.group(1)}'"
                else:
                    return "Успех! Паттерн совпал, но не содержит группы для извлечения (X)."
            else:
                return "Успех! Паттерн совпал."
        else:
            return "Не найдено"

    def find_episode_with_db_patterns(self, filename: str) -> str:
        patterns = self.db.get_patterns()
        active_patterns = [p for p in patterns if p.get('is_active')]
        
        if not active_patterns:
            return "Нет активных паттернов для тестирования."

        for p in active_patterns:
            compiled_pattern, error = self._compile_pattern(p['pattern'])
            if error:
                self.logger.error("renamer", f"Паттерн '{p['name']}' (ID {p['id']}) не скомпилирован: {error}")
                continue

            match = compiled_pattern.search(filename)
            if match:
                if 'X' in p['pattern'] and match.groups():
                    result = match.group(1)
                    return f"Успех! Паттерн '{p['name']}' (ID {p['id']}) извлек: '{result}'"
                else:
                    return f"Успех! Паттерн '{p['name']}' (ID {p['id']}) совпал (без извлечения)."

        return "Не найдено ни одним активным паттерном"

    def find_season_with_db_patterns(self, filename: str) -> str:
        """Ищет номер сезона, используя все активные паттерны из БД."""
        patterns = self.db.get_season_patterns()
        active_patterns = [p for p in patterns if p.get('is_active')]
        
        if not active_patterns:
            return "Нет активных паттернов сезона для тестирования."

        for p in active_patterns:
            compiled_pattern, error = self._compile_pattern(p['pattern'])
            if error:
                self.logger.error("renamer", f"Паттерн сезона '{p['name']}' (ID {p['id']}) не скомпилирован: {error}")
                continue

            match = compiled_pattern.search(filename)
            if match:
                if 'X' in p['pattern'] and match.groups():
                    result = match.group(1)
                    return f"Успех! Паттерн '{p['name']}' (ID {p['id']}) извлек: '{result}'"
                else:
                    return f"Успех! Паттерн '{p['name']}' (ID {p['id']}) совпал (без извлечения)."

        return "Не найдено ни одним активным паттерном сезона"

    def _extract_episode_number(self, filename: str) -> Optional[str]:
        if app.debug_manager.is_debug_enabled('renamer'):
            self.logger.debug("renamer", f"Попытка извлечь номер эпизода из: {filename}")
        patterns = self.db.get_patterns()
        active_patterns = [p for p in patterns if p.get('is_active')]

        for p in active_patterns:
            if "X" not in p['pattern']:
                continue

            compiled_pattern, error = self._compile_pattern(p['pattern'])
            if error:
                self.logger.error("renamer", f"Паттерн эпизода '{p['name']}' (ID {p['id']}) пропущен: {error}")
                continue
            
            match = compiled_pattern.search(filename)
            if match and match.groups():
                episode_str = match.group(1)
                if app.debug_manager.is_debug_enabled('renamer'):
                    self.logger.debug("renamer", f"Паттерн эпизода '{p['name']}' нашел номер: '{episode_str}'")
                try:
                    if int(episode_str) > 500:
                        continue
                except ValueError:
                    continue
                return episode_str.zfill(2)
        
        self.logger.warning("renamer", f"Не удалось найти номер эпизода в файле: {filename}")
        return None
        
    def _extract_season_number(self, filename: str) -> Optional[str]:
        if app.debug_manager.is_debug_enabled('renamer'):
            self.logger.debug("renamer", f"Попытка извлечь номер сезона из: {filename}")
        patterns = self.db.get_season_patterns()
        active_patterns = [p for p in patterns if p.get('is_active')]

        for p in active_patterns:
            if "X" not in p['pattern']:
                continue
            
            compiled_pattern, error = self._compile_pattern(p['pattern'])
            if error:
                self.logger.error("renamer", f"Паттерн сезона '{p['name']}' (ID {p['id']}) пропущен: {error}")
                continue
            
            match = compiled_pattern.search(filename)
            if match and match.groups():
                season_str = match.group(1)
                if app.debug_manager.is_debug_enabled('renamer'):
                    self.logger.debug("renamer", f"Паттерн сезона '{p['name']}' нашел номер: '{season_str}'")
                return season_str.zfill(2)
        
        if app.debug_manager.is_debug_enabled('renamer'):
            self.logger.debug("renamer", f"Не удалось найти номер сезона в файле: {filename}")
        return None


    def _extract_quality(self, filename: str) -> Optional[str]:
        if app.debug_manager.is_debug_enabled('renamer'):
            self.logger.debug("renamer", f"Попытка извлечь качество из: {filename}")
        quality_patterns_data = self.db.get_quality_patterns()
        active_quality_patterns = [qp for qp in quality_patterns_data if qp.get('is_active')]

        for qp in sorted(active_quality_patterns, key=lambda x: x['priority']):
            for sp in qp.get('search_patterns', []):
                compiled_pattern, error = self._compile_pattern(sp['pattern']) 
                if error:
                    self.logger.error("renamer", f"Паттерн качества '{sp['pattern']}' для '{qp['standard_value']}' пропущен: {error}")
                    continue
                match = compiled_pattern.search(filename)
                if match:
                    if app.debug_manager.is_debug_enabled('renamer'):
                        self.logger.debug("renamer", f"Паттерн '{sp['pattern']}' нашел качество: '{qp['standard_value']}'")
                    return qp['standard_value']

        if app.debug_manager.is_debug_enabled('renamer'):
            self.logger.debug("renamer", f"Не удалось найти качество в файле: {filename}")
        return None

    def _extract_resolution(self, filename: str) -> Optional[str]:
        if app.debug_manager.is_debug_enabled('renamer'):
            self.logger.debug("renamer", f"Попытка извлечь разрешение из: {filename}")
        resolution_patterns_data = self.db.get_resolution_patterns()
        active_resolution_patterns = [rp for rp in resolution_patterns_data if rp.get('is_active')]

        for rp in sorted(active_resolution_patterns, key=lambda x: x['priority']):
            for sp in rp.get('search_patterns', []):
                compiled_pattern, error = self._compile_pattern(sp['pattern'])
                if error:
                    self.logger.error("renamer", f"Паттерн разрешения '{sp['pattern']}' для '{rp['standard_value']}' пропущен: {error}")
                    continue
                match = compiled_pattern.search(filename)
                if match:
                    if app.debug_manager.is_debug_enabled('renamer'):
                        self.logger.debug("renamer", f"Паттерн '{sp['pattern']}' нашел разрешение: '{rp['standard_value']}'")
                    return rp['standard_value']

        if app.debug_manager.is_debug_enabled('renamer'):
            self.logger.debug("renamer", f"Не удалось найти разрешение в файле: {filename}")
        return None

    def get_rename_preview(self, files: List[str], series: Dict[str, Any]) -> List[Dict[str, str]]:
        series_name = series['name_en']
        season_number = series.get('season')
        if app.debug_manager.is_debug_enabled('renamer'):
            self.logger.debug("renamer", f"Запрос на предпросмотр для '{series_name}' сезона {season_number or 'Авто'}")
        preview_list = []

        video_extensions = ['.mkv', '.avi', '.mp4', '.mov', '.wmv', '.webm']
        video_files = [f for f in files if any(f.lower().endswith(ext) for ext in video_extensions)]
        
        for original_path in video_files:
            path_parts = original_path.rsplit('/', 1)
            original_dir = ''
            filename_only = original_path
            if len(path_parts) > 1:
                original_dir = path_parts[0] + '/'
                filename_only = path_parts[1]

            episode_number = self._extract_episode_number(filename_only)
            
            quality_name = self._extract_quality(filename_only)
            if not quality_name:
                quality_name = series.get('quality_override')

            resolution_name = self._extract_resolution(filename_only)
            if not resolution_name:
                resolution_name = series.get('resolution_override')
            
            season_to_use = season_number
            if not season_to_use:
                if app.debug_manager.is_debug_enabled('renamer'):
                    self.logger.debug("renamer", f"Сезон не указан для сериала, ищем в имени файла '{filename_only}'")
                season_to_use = self._extract_season_number(filename_only)

            new_path = ""
            if episode_number and season_to_use:
                extension = self._get_file_extension(filename_only)
                season_str_formatted = str(season_to_use).lower().replace('s', '').zfill(2)
                episode_str_formatted = episode_number.lstrip('eE').zfill(2)

                season_episode_part = f"s{season_str_formatted}e{episode_str_formatted}"

                new_filename_parts = [series_name, season_episode_part]
                if quality_name: new_filename_parts.append(quality_name)
                if resolution_name: new_filename_parts.append(resolution_name)
                
                new_filename = " ".join(filter(None, new_filename_parts)) + extension
                new_path = f"{original_dir}{new_filename}"
            
            preview_list.append({
                "original": original_path,
                "renamed": new_path or "Ошибка: не удалось определить номер эпизода/сезона"
            })
        
        return preview_list

    def _get_file_extension(self, filename: str) -> str:
        parts = filename.rsplit('.', 1)
        return f".{parts[1].lower()}" if len(parts) > 1 else ""