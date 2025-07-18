from typing import List, Dict, Any, Set

class SmartCollector:
    """
    Рассчитывает оптимальный "план загрузки" для сериала,
    обрабатывая каждый сезон независимо.
    """
    def __init__(self, logger):
        self.logger = logger

    def _build_plan_for_season(self, singles: List[Dict[str, Any]], compilations: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Содержит основную логику построения плана для ОДНОГО сезона."""
        
        statuses = {}

        # 1. Создание базового плана из уникальных одиночных серий
        base_plan_episodes: Dict[int, Dict[str, Any]] = {}
        for s in singles:
            ep_num = s['result']['extracted']['episode']
            if ep_num not in base_plan_episodes:
                base_plan_episodes[ep_num] = s
            else:
                # Обработка дубликатов: оставляем более новую версию
                current_date = base_plan_episodes[ep_num]['source_data']['publication_date']
                new_date = s['source_data']['publication_date']
                if new_date > current_date:
                    statuses[base_plan_episodes[ep_num]['source_data']['url']] = {'status': 'redundant', 'reason': 'Найдена более новая версия'}
                    base_plan_episodes[ep_num] = s
                else:
                    statuses[s['source_data']['url']] = {'status': 'redundant', 'reason': 'Найдена более новая версия'}

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


    def collect(self, processed_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        self.logger.info("smart_collector", "Запуск НОВОГО сезонно-ориентированного алгоритма.")

        # Шаг 1: Группировка всех элементов по сезонам
        seasons: Dict[int, Dict[str, List]] = {}
        
        for item in processed_items:
            if not item.get('result') or item['result'].get('error'):
                continue

            extracted = item['result'].get('extracted', {})
            # По умолчанию считаем сезоном 1, если он не указан
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
            season_statuses = self._build_plan_for_season(season_data['singles'], season_data['compilations'])
            final_statuses.update(season_statuses)

        # Шаг 3: Сборка итогового результата
        result_with_statuses = []
        for item in processed_items:
            item_with_status = item.copy()
            # Если элемент не попал ни в один из планов, он считается отброшенным
            status_info = final_statuses.get(item['source_data']['url'], {'status': 'discarded'})
            item_with_status.update(status_info)
            result_with_statuses.append(item_with_status)

        self.logger.info(f"smart_collector: План построен для {len(seasons)} сезонов.")
        return result_with_statuses