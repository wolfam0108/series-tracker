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
        """
        if not items:
            return None
        if len(items) == 1:
            return items[0]

        def sort_key(item):
            # --- ИЗМЕНЕНИЕ: Данные теперь в другом формате ---
            resolution = item.get('resolution') or 0
            
            if quality_priority:
                try:
                    priority_index = quality_priority.index(resolution)
                except ValueError:
                    priority_index = float('inf')
                return priority_index
            
            return -resolution

        sorted_by_quality = sorted(items, key=sort_key)
        best_quality_value = sort_key(sorted_by_quality[0])
        top_candidates = [item for item in sorted_by_quality if sort_key(item) == best_quality_value]

        if len(top_candidates) == 1:
            return top_candidates[0]
            
        return max(top_candidates, key=lambda x: x.get('publication_date'))

    def _build_plan_for_season(self, singles: List[Dict[str, Any]], compilations: List[Dict[str, Any]], quality_priority: List[int]) -> Dict[str, str]:
        """Содержит основную логику построения плана для ОДНОГО сезона."""
        
        plan_statuses = {}

        singles_by_episode = {}
        for s in singles:
            ep_num = s['episode_start']
            if ep_num not in singles_by_episode:
                singles_by_episode[ep_num] = []
            singles_by_episode[ep_num].append(s)

        base_plan_episodes: Dict[int, Dict[str, Any]] = {}
        for ep_num, items in singles_by_episode.items():
            best_version = self._get_best_quality_version(items, quality_priority)
            base_plan_episodes[ep_num] = best_version
            for item in items:
                if item != best_version:
                    plan_statuses[item['unique_id']] = 'redundant'

        all_ep_numbers: Set[int] = set(base_plan_episodes.keys())
        for c in compilations:
            all_ep_numbers.update(range(c['episode_start'], c['episode_end'] + 1))

        if not all_ep_numbers:
            return plan_statuses

        min_episode = min(all_ep_numbers)
        max_episode = max(all_ep_numbers)
        full_episode_range = set(range(min_episode, max_episode + 1))
        
        covered_eps = set(base_plan_episodes.keys())
        gaps = sorted(list(full_episode_range - covered_eps))
        
        plan_compilations = []
        processed_gaps: Set[int] = set()
        
        for gap_ep in gaps:
            if gap_ep in processed_gaps:
                continue

            suitable_compilations = [c for c in compilations if c['episode_start'] <= gap_ep <= c['episode_end']]
            if not suitable_compilations:
                continue

            best_compilation = None
            min_cost = float('inf')
            min_range_size = float('inf')

            for comp in suitable_compilations:
                start, end = comp['episode_start'], comp['episode_end']
                comp_range = set(range(start, end + 1))
                cost = len(comp_range.intersection(covered_eps))
                range_size = end - start + 1

                if cost < min_cost or (cost == min_cost and range_size < min_range_size):
                    min_cost = cost
                    min_range_size = range_size
                    best_compilation = comp
            
            if best_compilation:
                plan_compilations.append(best_compilation)
                start, end = best_compilation['episode_start'], best_compilation['episode_end']
                newly_covered = set(range(start, end + 1))
                processed_gaps.update(newly_covered)

        final_plan_items = []
        final_covered_eps = set()

        for comp in plan_compilations:
            final_plan_items.append(comp)
            plan_statuses[comp['unique_id']] = 'in_plan_compilation'
            start, end = comp['episode_start'], comp['episode_end']
            final_covered_eps.update(range(start, end + 1))

        for ep_num, single_item in base_plan_episodes.items():
            if ep_num in final_covered_eps:
                plan_statuses[single_item['unique_id']] = 'replaced'
            else:
                final_plan_items.append(single_item)
                plan_statuses[single_item['unique_id']] = 'in_plan_single'

        for comp in compilations:
            if comp not in final_plan_items:
                 if comp['unique_id'] not in plan_statuses:
                    plan_statuses[comp['unique_id']] = 'redundant'
        
        return plan_statuses

    # --- ИЗМЕНЕНИЕ: Вся логика метода collect переписана ---
    def collect(self, series_id: int):
        self.logger.info("smart_collector", f"Запуск планировщика для series_id: {series_id}")

        series_data = self.db.get_series(series_id)
        if not series_data:
            self.logger.error("smart_collector", f"Не удалось найти сериал с ID {series_id}")
            return

        # 1. Получаем всех кандидатов из БД
        candidate_items = self.db.get_media_items_by_plan_status(series_id, 'candidate')
        if not candidate_items:
            self.logger.info("smart_collector", f"Для series_id {series_id} не найдено новых кандидатов для планирования.")
            return
        
        # 2. Получаем настройки приоритета
        quality_priority = []
        try:
            if series_data.get('vk_quality_priority'):
                quality_priority = json.loads(series_data['vk_quality_priority'])
        except (json.JSONDecodeError, TypeError):
            self.logger.warning("smart_collector", "Не удалось прочитать настройки приоритета качества.")
        
        self.logger.info("smart_collector", f"Используемый приоритет качества: {quality_priority or 'По убыванию'}")

        # 3. Группируем кандидатов по сезонам
        seasons: Dict[int, Dict[str, List]] = {}
        for item in candidate_items:
            season_num = item.get('season', 1)

            if season_num not in seasons:
                seasons[season_num] = {'singles': [], 'compilations': []}

            # Проверяем, является ли элемент компиляцией
            if item.get('episode_end') and item['episode_end'] > item['episode_start']:
                seasons[season_num]['compilations'].append(item)
            else:
                seasons[season_num]['singles'].append(item)

        # 4. Обрабатываем каждый сезон и собираем итоговые статусы плана
        final_plan_statuses: Dict[str, str] = {}
        for season_num, season_data in seasons.items():
            self.logger.debug(f"smart_collector: Обработка сезона {season_num} ({len(season_data['singles'])} одиночных, {len(season_data['compilations'])} компиляций)")
            season_statuses = self._build_plan_for_season(season_data['singles'], season_data['compilations'], quality_priority)
            final_plan_statuses.update(season_statuses)

        # 5. Устанавливаем статус 'discarded' для всех кандидатов, которые не попали в план
        for item in candidate_items:
            if item['unique_id'] not in final_plan_statuses:
                final_plan_statuses[item['unique_id']] = 'discarded'
        
        # 6. Обновляем статусы в БД
        if final_plan_statuses:
            self.db.update_media_item_plan_statuses(final_plan_statuses)
            self.logger.info(f"smart_collector: План построен для {len(seasons)} сезонов. Обновлено {len(final_plan_statuses)} записей в БД.")