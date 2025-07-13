import re
from typing import List, Optional, Dict, Any
from flask import current_app as app
import fnmatch

class Renamer:
    def __init__(self, logger, db):
        self.logger = logger
        self.db = db

    def _compile_simple_pattern(self, user_pattern: str):
        """
        Компилирует простой пользовательский паттерн (для эпизодов/сезонов) в регулярное выражение.
        """
        temp_pattern = user_pattern
        
        match = re.search(r'(X+)', temp_pattern)
        placeholder = "___CAPTURE_GROUP___" if match else ""
        
        if match:
            x_sequence = match.group(1)
            temp_pattern = temp_pattern.replace(x_sequence, placeholder, 1)

        regex_pattern = re.escape(temp_pattern)
        regex_pattern = regex_pattern.replace(re.escape('X'), r'(?:\d)')

        if match:
            n = len(match.group(1))
            regex_pattern = regex_pattern.replace(placeholder, fr'(\d{{{n}}})')
            
        regex_pattern = regex_pattern.replace(re.escape('*'), r'.*?')

        if not user_pattern.startswith('*'):
            regex_pattern = '^' + regex_pattern
        if not user_pattern.endswith('*'):
            regex_pattern += '$'
        
        try:
            return re.compile(regex_pattern, re.IGNORECASE)
        except re.error as e:
            self.logger.error("renamer", f"Ошибка компиляции простого паттерна '{user_pattern}': {e}")
            return None
    
    # --- ИЗМЕНЕНИЕ: Добавлена логика для arithmetic_op ---
    def _apply_advanced_patterns(self, filename: str) -> str:
        """
        Применяет все активные продвинутые паттерны к имени файла как пре-процессор.
        """
        active_patterns = [p for p in self.db.get_advanced_patterns() if p.get('is_active')]
        if not active_patterns:
            return filename
        
        processed_filename = filename
        
        for p in active_patterns:
            try:
                # Шаг 1: Фильтрация
                if not fnmatch.fnmatch(processed_filename, p['file_filter']):
                    continue

                # Шаг 2: Извлечение X
                pattern_search_re = self._compile_simple_pattern(p['pattern_search'])
                if not pattern_search_re:
                    self.logger.warning(f"Пропущен продвинутый паттерн '{p['name']}': ошибка компиляции pattern_search")
                    continue
                
                match = pattern_search_re.search(processed_filename)
                if not match or not match.groups():
                    continue
                
                extracted_num_str = match.group(1)
                final_num = int(extracted_num_str)

                # Шаг 2.5: Применяем арифметическую операцию, если она есть
                if p.get('arithmetic_op') is not None:
                    final_num += p['arithmetic_op']
                
                # Проверка на наличие области для замены
                if p['area_to_replace'] not in processed_filename:
                    if app.debug_manager.is_debug_enabled('renamer'):
                        self.logger.debug("renamer", f"Паттерн '{p['name']}' пропущен: area_to_replace '{p['area_to_replace']}' не найдена в '{processed_filename}'")
                    continue
                
                # Шаг 3: Формирование новой строки
                x_len_in_template = p['replacement_template'].count('X')
                new_part = p['replacement_template'].replace('X' * x_len_in_template, str(final_num).zfill(x_len_in_template))
                
                # Шаг 4: Замена
                processed_filename = processed_filename.replace(p['area_to_replace'], new_part, 1)
                if app.debug_manager.is_debug_enabled('renamer'):
                    self.logger.debug("renamer", f"Паттерн '{p['name']}' изменил имя файла на: '{processed_filename}'")

            except Exception as e:
                self.logger.error("renamer", f"Ошибка при применении продвинутого паттерна '{p['name']}': {e}")
                continue
        
        return processed_filename
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---

    def _extract_episode_number(self, filename: str) -> Optional[str]:
        if app.debug_manager.is_debug_enabled('renamer'):
            self.logger.debug("renamer", f"Попытка извлечь номер эпизода из: {filename}")
        patterns = self.db.get_patterns()
        active_patterns = [p for p in patterns if p.get('is_active')]

        for p in active_patterns:
            if "X" not in p['pattern']:
                continue

            compiled_pattern = self._compile_simple_pattern(p['pattern'])
            if not compiled_pattern:
                self.logger.error("renamer", f"Паттерн эпизода '{p['name']}' (ID {p['id']}) пропущен из-за ошибки компиляции.")
                continue
            
            match = compiled_pattern.search(filename)
            if match and match.groups():
                episode_str = match.group(1)
                if app.debug_manager.is_debug_enabled('renamer'):
                    self.logger.debug("renamer", f"Паттерн эпизода '{p['name']}' нашел номер: '{episode_str}'")
                try:
                    if int(episode_str) > 500: continue
                except ValueError: continue
                return episode_str.zfill(2)
        
        self.logger.warning("renamer", f"Не удалось найти номер эпизода в файле: {filename}")
        return None
        
    def _extract_season_number(self, filename: str) -> Optional[str]:
        if app.debug_manager.is_debug_enabled('renamer'):
            self.logger.debug("renamer", f"Попытка извлечь номер сезона из: {filename}")
        patterns = self.db.get_season_patterns()
        active_patterns = [p for p in patterns if p.get('is_active')]

        for p in active_patterns:
            if "X" not in p['pattern']: continue
            
            compiled_pattern = self._compile_simple_pattern(p['pattern'])
            if not compiled_pattern:
                self.logger.error("renamer", f"Паттерн сезона '{p['name']}' (ID {p['id']}) пропущен из-за ошибки компиляции.")
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
                compiled_pattern = self._compile_simple_pattern(sp['pattern']) 
                if not compiled_pattern:
                    self.logger.error("renamer", f"Паттерн качества '{sp['pattern']}' для '{qp['standard_value']}' пропущен.")
                    continue
                if compiled_pattern.search(filename):
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
                compiled_pattern = self._compile_simple_pattern(sp['pattern'])
                if not compiled_pattern:
                    self.logger.error("renamer", f"Паттерн разрешения '{sp['pattern']}' для '{rp['standard_value']}' пропущен.")
                    continue
                if compiled_pattern.search(filename):
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
            original_dir = path_parts[0] + '/' if len(path_parts) > 1 else ''
            filename_only = path_parts[1] if len(path_parts) > 1 else original_path

            processed_filename = self._apply_advanced_patterns(filename_only)
            
            episode_number = self._extract_episode_number(processed_filename)
            
            quality_name = self._extract_quality(processed_filename) or series.get('quality_override')
            resolution_name = self._extract_resolution(processed_filename) or series.get('resolution_override')
            
            season_to_use = season_number
            if not season_to_use:
                if app.debug_manager.is_debug_enabled('renamer'):
                    self.logger.debug("renamer", f"Сезон не указан для сериала, ищем в имени файла '{processed_filename}'")
                season_to_use = self._extract_season_number(processed_filename)

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

    def find_episode_with_db_patterns(self, filename: str) -> str:
        patterns = self.db.get_patterns()
        active_patterns = [p for p in patterns if p.get('is_active')]
        if not active_patterns: return "Нет активных паттернов для тестирования."
        for p in active_patterns:
            compiled_pattern = self._compile_simple_pattern(p['pattern'])
            if not compiled_pattern: continue
            match = compiled_pattern.search(filename)
            if match:
                if 'X' in p['pattern'] and match.groups():
                    return f"Успех! Паттерн '{p['name']}' извлек: '{match.group(1)}'"
                else:
                    return f"Успех! Паттерн '{p['name']}' совпал (без извлечения)."
        return "Не найдено ни одним активным паттерном"

    def find_season_with_db_patterns(self, filename: str) -> str:
        patterns = self.db.get_season_patterns()
        active_patterns = [p for p in patterns if p.get('is_active')]
        if not active_patterns: return "Нет активных паттернов сезона для тестирования."
        for p in active_patterns:
            compiled_pattern = self._compile_simple_pattern(p['pattern'])
            if not compiled_pattern: continue
            match = compiled_pattern.search(filename)
            if match:
                if 'X' in p['pattern'] and match.groups():
                    return f"Успех! Паттерн '{p['name']}' извлек: '{match.group(1)}'"
                else:
                    return f"Успех! Паттерн '{p['name']}' совпал (без извлечения)."
        return "Не найдено ни одним активным паттерном сезона"