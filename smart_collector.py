import json
from typing import List, Dict, Any, Set

class SmartCollector:
    """
    Рассчитывает оптимальный "план загрузки" для сериала,
    обрабатывая каждый сезон независимо и выбирая наилучшее качество видео.
    """
    def __init__(self, logger, db):
        self.logger = logger
        self.db = db

    def _get_best_quality_version(self, items: List[Dict[str, Any]], quality_priority: List[int]) -> Dict[str, Any]:
        """
        Из списка дубликатов одного и того же эпизода/компиляции выбирает лучший.
        Логика выбора:
        1. По пользовательскому приоритету разрешений.
        2. Если приоритет не задан, по максимальному разрешению.
        3. Если разрешения равны, по самой новой дате публикации.
        """
        if not items:
            return None
        if len(items) == 1:
            return items[0]

        # Сортировка по качеству
        def sort_key(item):
            resolution = item.get('source_data', {}).get('resolution') or 0
            
            # Приоритет №1: Пользовательский порядок
            if quality_priority:
                try:
                    # Чем ниже индекс в списке приоритетов, тем лучше (индекс 0 - лучший)
                    priority_index = quality_priority.index(resolution)
                except ValueError:
                    # Если разрешения нет в списке, отправляем его в конец
                    priority_index = float('inf')
                return priority_index
            
            # Приоритет №2: Максимальное разрешение (сортируем по убыванию, поэтому -resolution)
            return -resolution

        # Сначала сортируем по качеству
        sorted_by_quality = sorted(items, key=sort_key)
        
        # Отбираем всех кандидатов с наилучшим качеством
        best_quality_value = sort_key(sorted_by_quality[0])
        top_candidates = [item for item in sorted_by_quality if sort_key(item) == best_quality_value]

        # Если после фильтрации по качеству остался один кандидат, возвращаем его
        if len(top_candidates) == 1:
            return top_candidates[0]
            
        # Приоритет №3: Если качества одинаковы, выбираем по самой новой дате
        return max(top_candidates, key=lambda x: x.get('source_data', {}).get('publication_date'))

    def _build_plan_for_season(self, singles: List[Dict[str, Any]], compilations: List[Dict[str, Any]], quality_priority: List[int]) -> Dict[str, Dict[str, Any]]:
        """Содержит основную логику построения плана для ОДНОГО сезона."""
        
        statuses = {}

        # --- ИЗМЕНЕНИЕ: Группируем одиночные серии по номеру эпизода ---
        singles_by_episode = {}
        for s in singles:
            ep_num = s['result']['extracted']['episode']
            if ep_num not in singles_by_episode:
                singles_by_episode[ep_num] = []
            singles_by_episode[ep_num].append(s)

        # 1. Создание базового плана из лучших версий одиночных серий
        base_plan_episodes: Dict[int, Dict[str, Any]] = {}
        for ep_num, items in singles_by_episode.items():
            best_version = self._get_best_quality_version(items, quality_priority)
            base_plan_episodes[ep_num] = best_version
            # Помечаем остальные версии как избыточные
            for item in items:
                if item != best_version:
                    statuses[item['source_data']['url']] = {'status': 'redundant', 'reason': 'Найдена версия с лучшим качеством'}

        all_ep_numbers: Set[int] = set(base_plan_episodes.keys())
        for c in compilations:
            all_ep_numbers.update(range(c['result']['extracted']['start'], c['result']['extracted']['end'] + 1))

        if not all_ep_numbers:
            return statuses

        min_episode = min(all_ep_numbers)
        max_episode = max(all_ep_numbers)
        full_episode_range = set(range(min_episode, max_episode + 1))
        
        covered_eps = set(base_plan_episodes.keys())
        gaps = sorted(list(full_episode_range - covered_eps))
        
        # 2. Заполнение пробелов компиляциями
        plan_compilations = []
        processed_gaps: Set[int] = set()
        
        for gap_ep in gaps:
            if gap_ep in processed_gaps:
                continue

            suitable_compilations = [c for c in compilations if c['result']['extracted']['start'] <= gap_ep <= c['result']['extracted']['end']]
            if not suitable_compilations:
                continue

            best_compilation = None
            min_cost = float('inf')
            min_range_size = float('inf')

            for comp in suitable_compilations:
                start, end = comp['result']['extracted']['start'], comp['result']['extracted']['end']
                comp_range = set(range(start, end + 1))
                cost = len(comp_range.intersection(covered_eps))
                range_size = end - start + 1

                if cost < min_cost or (cost == min_cost and range_size < min_range_size):
                    min_cost = cost
                    min_range_size = range_size
                    best_compilation = comp
            
            if best_compilation:
                plan_compilations.append(best_compilation)
                start, end = best_compilation['result']['extracted']['start'], best_compilation['result']['extracted']['end']
                newly_covered = set(range(start, end + 1))
                processed_gaps.update(newly_covered)

        # 3. Финальная дедупликация и присвоение статусов
        final_plan_items = []
        final_covered_eps = set()

        for comp in plan_compilations:
            final_plan_items.append(comp)
            statuses[comp['source_data']['url']] = {'status': 'in_plan_compilation'}
            start, end = comp['result']['extracted']['start'], comp['result']['extracted']['end']
            final_covered_eps.update(range(start, end + 1))

        for ep_num, single_item in base_plan_episodes.items():
            if ep_num in final_covered_eps:
                statuses[single_item['source_data']['url']] = {'status': 'replaced', 'reason': f'Заменено компиляцией'}
            else:
                final_plan_items.append(single_item)
                statuses[single_item['source_data']['url']] = {'status': 'in_plan_single'}

        for comp in compilations:
            if comp not in final_plan_items:
                 statuses[comp['source_data']['url']] = {'status': 'redundant', 'reason': 'Выбрана более эффективная компиляция'}
        
        return statuses


    def collect(self, processed_items: List[Dict[str, Any]], series_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        self.logger.info("smart_collector", "Запуск НОВОГО сезонно-ориентированного алгоритма с фильтрацией по качеству.")

        # --- ИЗМЕНЕНИЕ: Загружаем приоритет качества из данных сериала ---
        quality_priority = []
        try:
            if series_data.get('vk_quality_priority'):
                quality_priority = json.loads(series_data['vk_quality_priority'])
        except (json.JSONDecodeError, TypeError):
            self.logger.warning("smart_collector", "Не удалось прочитать настройки приоритета качества.")
        
        self.logger.info("smart_collector", f"Используемый приоритет качества: {quality_priority or 'По убыванию'}")

        # Шаг 1: Группировка всех элементов по сезонам
        seasons: Dict[int, Dict[str, List]] = {}
        
        for item in processed_items:
            # --- ИЗМЕНЕНИЕ: Пропускаем видео без разрешения ---
            if not item.get('result') or item['result'].get('error') or not item.get('source_data', {}).get('resolution'):
                continue

            extracted = item['result'].get('extracted', {})
            season_num = extracted.get('season', 1)

            if season_num not in seasons:
                seasons[season_num] = {'singles': [], 'compilations': []}

            if extracted.get('episode') is not None:
                seasons[season_num]['singles'].append(item)
            elif extracted.get('start') is not None and extracted.get('end') is not None:
                seasons[season_num]['compilations'].append(item)

        # Шаг 2: Независимая обработка каждого сезона
        final_statuses = {}
        for season_num, season_data in seasons.items():
            self.logger.debug(f"smart_collector: Обработка сезона {season_num} ({len(season_data['singles'])} одиночных, {len(season_data['compilations'])} компиляций)")
            season_statuses = self._build_plan_for_season(season_data['singles'], season_data['compilations'], quality_priority)
            final_statuses.update(season_statuses)

        # Шаг 3: Сборка итогового результата
        result_with_statuses = []
        for item in processed_items:
            item_with_status = item.copy()
            status_info = final_statuses.get(item['source_data']['url'], {'status': 'discarded'})
            item_with_status.update(status_info)
            result_with_statuses.append(item_with_status)

        self.logger.info(f"smart_collector: План построен для {len(seasons)} сезонов.")
        return result_with_statuses
