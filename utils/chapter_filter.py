import re
from typing import List, Dict, Tuple, Optional

class ChapterFilter:
    """
    Класс для фильтрации мусорных глав в видео-компиляциях.
    Определяет и помечает главы, которые являются опенингами, эндингами и другим мусором.
    """
    
    # Список ключевых слов для определения мусорных глав
    GARBAGE_PATTERNS = [
        # Опенинги и эндинги
        r'op\b', r'opening', r'опенинг', r'опенинги', r'opening\s*\d*',
        r'ed\b', r'ending', r'эндинг', r'эндинги', r'ending\s*\d*',
        
        # Промо-материалы
        r'promo', r'pv', r'preview', r'трейлер', r'промо', r'анонс',
        
        # Другой мусор
        r'credits?', r'титры', r'интро', r'outro', r'перерыв',
        r'recap', r'повтор', r'preview', r'предпросмотр',
        
        # Нумерация опенингов/эндингов
        r'op\s*\d+', r'ed\s*\d+', r'opening\s*\d+', r'ending\s*\d+',
    ]
    
    # Минимальная длительность главы в секундах (чтобы отфильтровать слишком короткие)
    MIN_DURATION_SECONDS = 30
    
    # Максимальная длительность для опенинга/эндинга в секундах
    MAX_OP_ED_DURATION_SECONDS = 120
    
    @classmethod
    def is_garbage_chapter(cls, chapter: Dict, index: int, total_chapters: int) -> Tuple[bool, Optional[str]]:
        """
        Определяет, является ли глава мусорной.
        
        Args:
            chapter: Словарь с информацией о главе {'time': str, 'title': str}
            index: Индекс главы в списке (0-based)
            total_chapters: Общее количество глав
            
        Returns:
            Tuple[bool, Optional[str]]: (является_мусорной, причина)
        """
        title = chapter.get('title', '').lower().strip()
        time_str = chapter.get('time', '')
        
        # Проверяем по ключевым словам в названии
        for pattern in cls.GARBAGE_PATTERNS:
            if re.search(pattern, title, re.IGNORECASE):
                return True, f"Совпадение с паттерном: {pattern}"
        
        # Проверяем первую главу (обычно опенинг)
        if index == 0 and cls._is_likely_opening(title):
            return True, "Первая глава, похожая на опенинг"
        
        # Проверяем последнюю главу (обычно эндинг или превью)
        if index == total_chapters - 1 and cls._is_likely_ending(title):
            return True, "Последняя глава, похожая на эндинг/превью"
        
        # Проверяем по длительности (если можем определить)
        duration = cls._estimate_chapter_duration(time_str)
        if duration is not None and duration < cls.MIN_DURATION_SECONDS:
            return True, f"Слишком короткая глава: {duration}сек"
        
        # Проверяем по позициям (первая/последняя) с коротким названием
        if (index in [0, total_chapters - 1] and 
            len(title) < 10 and 
            not any(c.isdigit() for c in title)):
            return True, "Короткое название в начале/конце"
        
        return False, None
    
    @classmethod
    def _is_likely_opening(cls, title: str) -> bool:
        """Определяет, похоже ли название на опенинг."""
        opening_keywords = ['op', 'opening', 'оп', 'опенинг', 'тема', 'intro']
        return any(keyword in title for keyword in opening_keywords)
    
    @classmethod
    def _is_likely_ending(cls, title: str) -> bool:
        """Определяет, похоже ли название на эндинг."""
        ending_keywords = ['ed', 'ending', 'эн', 'эндинг', 'титры', 'конец', 'outro', 'credits']
        return any(keyword in title for keyword in ending_keywords)
    
    @classmethod
    def _estimate_chapter_duration(cls, time_str: str) -> Optional[int]:
        """
        Оценивает длительность главы по времени начала.
        Это приблизительная оценка, так как у нас нет времени окончания.
        """
        try:
            # Парсим время в формате HH:MM:SS
            parts = time_str.split(':')
            if len(parts) == 3:
                hours, minutes, seconds = map(int, parts)
                total_seconds = hours * 3600 + minutes * 60 + seconds
                return total_seconds
            elif len(parts) == 2:
                minutes, seconds = map(int, parts)
                total_seconds = minutes * 60 + seconds
                return total_seconds
        except (ValueError, AttributeError):
            pass
        return None
    
    @classmethod
    def filter_chapters(cls, chapters: List[Dict]) -> List[Dict]:
        """
        Фильтрует список глав, удаляя мусорные.
        
        Args:
            chapters: Список глав [{'time': str, 'title': str}, ...]
            
        Returns:
            List[Dict]: Отфильтрованный список глав
        """
        filtered_chapters = []
        total_chapters = len(chapters)
        
        for index, chapter in enumerate(chapters):
            is_garbage, reason = cls.is_garbage_chapter(chapter, index, total_chapters)
            
            # Добавляем информацию о фильтрации в главу
            chapter_with_meta = chapter.copy()
            chapter_with_meta['is_garbage'] = is_garbage
            chapter_with_meta['garbage_reason'] = reason
            
            if not is_garbage:
                filtered_chapters.append(chapter_with_meta)
        
        return filtered_chapters
    
    @classmethod
    def get_garbage_chapters(cls, chapters: List[Dict]) -> List[Dict]:
        """
        Возвращает только мусорные главы из списка.
        
        Args:
            chapters: Список глав [{'time': str, 'title': str}, ...]
            
        Returns:
            List[Dict]: Список мусорных глав с метаданными
        """
        garbage_chapters = []
        total_chapters = len(chapters)
        
        for index, chapter in enumerate(chapters):
            is_garbage, reason = cls.is_garbage_chapter(chapter, index, total_chapters)
            
            if is_garbage:
                chapter_with_meta = chapter.copy()
                chapter_with_meta['is_garbage'] = True
                chapter_with_meta['garbage_reason'] = reason
                chapter_with_meta['original_index'] = index
                garbage_chapters.append(chapter_with_meta)
        
        return garbage_chapters
    
    @classmethod
    def mark_chapters_manually(cls, chapters: List[Dict], garbage_indices: List[int]) -> List[Dict]:
        """
        Помечает главы как мусорные на основе ручного выбора пользователя.
        
        Args:
            chapters: Список глав [{'time': str, 'title': str}, ...]
            garbage_indices: Список индексов глав, которые нужно пометить как мусорные
            
        Returns:
            List[Dict]: Список глав с метаданными о мусорности
        """
        marked_chapters = []
        
        for index, chapter in enumerate(chapters):
            chapter_with_meta = chapter.copy()
            is_garbage = index in garbage_indices
            chapter_with_meta['is_garbage'] = is_garbage
            chapter_with_meta['garbage_reason'] = 'Отмечено вручную' if is_garbage else None
            chapter_with_meta['original_index'] = index
            marked_chapters.append(chapter_with_meta)
        
        return marked_chapters