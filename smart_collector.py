# Файл: smart_collector.py

import json
from typing import List, Dict, Any, Set
from collections import defaultdict

class SmartCollector:
    """
    Рассчитывает оптимальный "план загрузки", используя алгоритм,
    приоритетом которого является максимальная полнота покрытия серий.
    Версия алгоритма: 4.0 "Полнота > Качество > Одиночные"
    """
    def __init__(self, logger, db):
        self.logger = logger
        self.db = db

    def _get_quality_sort_key(self, item: Dict[str, Any], quality_priority: List[int]) -> tuple:
        """Возвращает ключ для сортировки по качеству."""
        resolution = item.get('resolution') or 0
        priority_index = float('inf')
        if quality_priority and resolution in quality_priority:
            try:
                priority_index = quality_priority.index(resolution)
            except ValueError:
                pass
        return (priority_index, -resolution)
    # --- КОНЕЦ БЛОКА ДЛЯ ВСТАВКИ ---

    def _build_plan_for_tier(
        self,
        base_plan_singles: List[Dict[str, Any]],
        all_compilations: List[Dict[str, Any]],
        episodes_to_cover: Set[int]
    ) -> List[Dict[str, Any]]:
        """
        Строит наиболее полный план из предоставленного набора элементов.
        1. Начинает с базового плана одиночных серий.
        2. Итеративно закрывает дыры самыми оптимальными компиляциями.
        3. Очищает план от одиночных серий, которые были покрыты компиляциями.
        """
        plan_compilations = []
        covered_by_compilations = set()
        
        covered_by_singles = {item['episode_start'] for item in base_plan_singles}
        gaps_to_fill = episodes_to_cover - covered_by_singles

        # --- Шаг 1: Итеративно выбираем лучшие компиляции для закрытия дыр ---
        while gaps_to_fill:
            gap_filler_candidates = [
                c for c in all_compilations 
                if not set(range(c['episode_start'], c['episode_end'] + 1)).isdisjoint(gaps_to_fill)
            ]
            if not gap_filler_candidates:
                break

            non_dominated_candidates = []
            for candidate in gap_filler_candidates:
                is_dominated = False
                cand_gaps = set(range(candidate['episode_start'], candidate['episode_end'] + 1)).intersection(gaps_to_fill)
                
                for other in gap_filler_candidates:
                    if candidate == other: continue
                    other_gaps = set(range(other['episode_start'], other['episode_end'] + 1)).intersection(gaps_to_fill)
                    if cand_gaps.issubset(other_gaps) and len(other_gaps) > len(cand_gaps):
                        is_dominated = True
                        break
                if not is_dominated:
                    non_dominated_candidates.append(candidate)
            
            if not non_dominated_candidates:
                non_dominated_candidates = gap_filler_candidates

            best_compilation = max(
                non_dominated_candidates,
                key=lambda c: (
                    len(set(range(c['episode_start'], c['episode_end'] + 1)).intersection(gaps_to_fill)),
                    -len(set(range(c['episode_start'], c['episode_end'] + 1)).intersection(covered_by_singles)),
                    -(c['episode_end'] - c['episode_start'])
                )
            )

            plan_compilations.append(best_compilation)
            newly_covered = set(range(best_compilation['episode_start'], best_compilation['episode_end'] + 1))
            covered_by_compilations.update(newly_covered)
            gaps_to_fill -= newly_covered
        
        # --- Шаг 2: Очищаем базовый план от одиночных серий, покрытых компиляциями ---
        final_plan_singles = [
            s for s in base_plan_singles 
            if s['episode_start'] not in covered_by_compilations
        ]

        # --- Шаг 3: Собираем итоговый чистый план ---
        final_plan = plan_compilations + final_plan_singles
        return final_plan

    def collect(self, series_id: int):
        self.logger.info(f"smart_collector: Запуск нового планировщика (v4.0, 'Сначала полнота') для series_id: {series_id}")

        series_data = self.db.get_series(series_id)
        if not series_data: return
            
        candidate_items = self.db.get_media_items_by_plan_status(series_id, 'candidate')
        if not candidate_items:
            self.logger.info(f"smart_collector: Для series_id {series_id} не найдено новых кандидатов.")
            return

        quality_priority = []
        try:
            if series_data.get('vk_quality_priority'):
                quality_priority = json.loads(series_data['vk_quality_priority'])
        except (json.JSONDecodeError, TypeError): pass

        # --- НАЧАЛО НОВОГО АЛГОРИТМА ---

        # 1. Подготовка: определяем полный диапазон и отбираем лучшие одиночные серии
        full_potential_range = set()
        for item in candidate_items:
            start, end = item['episode_start'], item.get('episode_end') or item['episode_start']
            full_potential_range.update(range(start, end + 1))
        
        if not full_potential_range: return

        singles_by_ep = defaultdict(list)
        all_compilations = []
        for item in candidate_items:
            if item.get('episode_end') and item['episode_end'] > item['episode_start']:
                all_compilations.append(item)
            else:
                singles_by_ep[item['episode_start']].append(item)

        base_plan_singles = []
        for ep_num in singles_by_ep:
            best_single = max(singles_by_ep[ep_num], key=lambda i: self._get_quality_sort_key(i, quality_priority))
            base_plan_singles.append(best_single)

        # 2. Строим план, используя все доступные файлы
        best_plan = self._build_plan_for_tier(base_plan_singles, all_compilations, full_potential_range)
        
        # 3. Финальный этап: апгрейд качества за счет необязательных компиляций
        final_plan_items = list(best_plan)
        plan_map = {item['episode_start']:item for item in final_plan_items if not item.get('episode_end') or item['episode_end'] == item['episode_start']}

        for comp in all_compilations:
            if comp in final_plan_items: continue
            
            comp_quality = self._get_quality_sort_key(comp, quality_priority)
            episodes_it_could_replace = []
            is_valid_for_upgrade = True
            is_strictly_better = False # Флаг, что есть реальное улучшение качества

            start, end = comp['episode_start'], comp['episode_end']
            for ep_num in range(start, end + 1):
                if ep_num in plan_map:
                    single_in_plan = plan_map[ep_num]
                    single_quality = self._get_quality_sort_key(single_in_plan, quality_priority)
                    
                    # 1. Проверяем, что компиляция НЕ ХУЖЕ ни одной из одиночных серий
                    if comp_quality > single_quality:
                        is_valid_for_upgrade = False
                        break
                    
                    # 2. Проверяем, что компиляция СТРОГО ЛУЧШЕ хотя бы одной из серий
                    if comp_quality < single_quality:
                        is_strictly_better = True
                    
                    episodes_it_could_replace.append(single_in_plan)
            
            if not is_valid_for_upgrade:
                continue

            # 3. Замена происходит, только если компиляция СТРОГО ЛУЧШЕ
            if episodes_it_could_replace and is_strictly_better:
                self.logger.debug(f"smart_collector: Апгрейд качества! Компиляция {comp['unique_id'][:8]} заменяет {len(episodes_it_could_replace)} одиночных серий.")
                final_plan_items = [item for item in final_plan_items if item not in episodes_it_could_replace]
                final_plan_items.append(comp)
                plan_map = {item['episode_start']:item for item in final_plan_items if not item.get('episode_end') or item['episode_end'] == item['episode_start']}


        # 4. Финализируем статусы на основе лучшего найденного плана
        final_plan_ids = {item['unique_id'] for item in final_plan_items}
        
        final_covered_episodes = set()
        for item in final_plan_items:
            start, end = item['episode_start'], item.get('episode_end') or item['episode_start']
            final_covered_episodes.update(range(start, end + 1))

        final_plan_statuses: Dict[str, str] = {}
        for item in candidate_items:
            unique_id = item['unique_id']
            if unique_id in final_plan_ids:
                is_compilation = item.get('episode_end') and item['episode_end'] > item['episode_start']
                final_plan_statuses[unique_id] = 'in_plan_compilation' if is_compilation else 'in_plan_single'
            else:
                start, end = item['episode_start'], item.get('episode_end') or item['episode_start']
                is_covered = any(i in final_covered_episodes for i in range(start, end + 1))
                final_plan_statuses[unique_id] = 'replaced' if is_covered else 'redundant'
        
        if final_plan_statuses:
            self.db.update_media_item_plan_statuses(final_plan_statuses)
            self.logger.info(f"smart_collector: План построен. Обновлено {len(final_plan_statuses)} записей.")