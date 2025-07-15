from typing import List, Dict, Any
from datetime import datetime
import hashlib

def generate_media_item_id(url: str, pub_date: datetime) -> str:
    """Генерирует уникальный ID для медиа-элемента на основе URL и даты."""
    date_str = pub_date.strftime('%Y-%m-%d %H:%M:%S')
    unique_string = f"{url}{date_str}"
    return hashlib.md5(unique_string.encode()).hexdigest()[:16]

class SmartCollector:
    def __init__(self, logger):
        self.logger = logger

    def collect(self, processed_items: List[Dict[str, Any]], existing_items: List[Dict[str, Any]], preferred_voiceovers_str: str) -> List[Dict[str, Any]]:
        self.logger.info("smart_collector", "Запуск умного сборщика...")

        valid_items = [item for item in processed_items if item.get('result')]
        unique_items = self._resolve_voiceover_duplicates(valid_items, preferred_voiceovers_str)
        self.logger.debug(f"smart_collector: После фильтрации и разрешения дубликатов озвучек осталось {len(unique_items)} элементов.")
        
        singles = [item for item in unique_items if item['result']['action'] == 'extract_single']
        compilations = [item for item in unique_items if item['result']['action'] == 'extract_range']

        # 1. Заполняем карту покрытия одиночными сериями. Это наш приоритет.
        coverage_map = {}
        for item in singles:
            ep_num = item['result']['extracted']['episode']
            coverage_map[ep_num] = {'item': item, 'type': 'single'}

        # 2. Определяем, какие серии все еще нужны (пробелы).
        all_possible_episodes = set(coverage_map.keys())
        for comp in compilations:
            all_possible_episodes.update(range(comp['result']['extracted']['start'], comp['result']['extracted']['end'] + 1))
        
        gaps_to_fill = all_possible_episodes - set(coverage_map.keys())
        self.logger.debug(f"smart_collector: Обнаружено {len(gaps_to_fill)} пробелов в сериях: {sorted(list(gaps_to_fill))}")

        # 3. Итеративно выбираем лучшие компиляции для закрытия пробелов.
        while gaps_to_fill:
            best_compilation = None
            best_score = -1
            
            for comp_item in compilations:
                start, end = comp_item['result']['extracted']['start'], comp_item['result']['extracted']['end']
                comp_episodes = set(range(start, end + 1))
                
                # Сколько пробелов закрывает эта компиляция?
                covered_gaps = gaps_to_fill.intersection(comp_episodes)
                if not covered_gaps:
                    continue

                # Сколько лишних (уже покрытых) серий она захватывает?
                redundant_coverage = len(comp_episodes.difference(gaps_to_fill))
                
                # Оценка: больше покрытых пробелов - лучше, меньше лишних серий - лучше.
                score = len(covered_gaps) - (redundant_coverage * 0.1) # Небольшой штраф за избыточность

                if score > best_score:
                    best_score = score
                    best_compilation = comp_item

            if best_compilation:
                # Мы нашли лучшую компиляцию для текущего шага.
                self.logger.debug(f"smart_collector: Выбрана компиляция '{best_compilation['source_data']['title']}' со счетом {best_score}")
                start, end = best_compilation['result']['extracted']['start'], best_compilation['result']['extracted']['end']
                for ep_num in range(start, end + 1):
                    # Заполняем карту этой компиляцией, даже если там уже есть одиночная серия.
                    # Это нужно для правильного присвоения статуса 'discarded'.
                    if ep_num in all_possible_episodes:
                         coverage_map[ep_num] = {'item': best_compilation, 'type': 'compilation'}
                
                # Обновляем список оставшихся пробелов.
                gaps_to_fill -= set(range(start, end + 1))
                # Удаляем использованную компиляцию, чтобы не рассматривать ее снова.
                compilations.remove(best_compilation)
            else:
                # Если ни одна компиляция не может закрыть оставшиеся пробелы.
                break
        
        # 4. Формируем финальный план и присваиваем статусы на основе итоговой карты покрытия.
        final_plan = []
        for item in unique_items:
            action = item['result']['action']
            
            if action == 'extract_single':
                ep_num = item['result']['extracted']['episode']
                final_owner = coverage_map.get(ep_num, {}).get('item')
                if final_owner == item:
                    item['status'] = 'new'
                else:
                    item['status'] = 'discarded'
            
            elif action == 'extract_range':
                start, end = item['result']['extracted']['start'], item['result']['extracted']['end']
                is_used = False
                for ep_num in range(start, end + 1):
                    if coverage_map.get(ep_num, {}).get('item') == item:
                        is_used = True
                        break
                item['status'] = 'new_compilation' if is_used else 'redundant'
            
            else:
                item['status'] = 'processed'
            
            final_plan.append(item)

        # 5. Проверяем по существующим в БД элементам.
        existing_map = {item['unique_id']: item for item in existing_items}
        for item in final_plan:
            # Присваиваем id и флаг is_ignored, если элемент уже есть в БД
            unique_id = generate_media_item_id(item['source_data']['url'], item['source_data']['publication_date'])
            if unique_id in existing_map:
                 db_item = existing_map[unique_id]
                 item['id'] = db_item['id']
                 item['is_ignored_by_user'] = db_item['is_ignored_by_user']
                 # Если статус уже 'completed', оставляем его.
                 if db_item['status'] == 'completed':
                     item['status'] = 'completed'

        self.logger.info("smart_collector: Умный сборщик завершил работу.")
        return final_plan

    def _resolve_voiceover_duplicates(self, items: List[Dict[str, Any]], preferred_voiceovers_str: str) -> List[Dict[str, Any]]:
        preferred = [v.strip().lower() for v in (preferred_voiceovers_str or "").split(',') if v.strip()]
        
        episodes_dict = {}
        other_items = []

        for item in items:
            if not (item and item.get('result') and item['result'].get('action') == 'extract_single'):
                other_items.append(item)
                continue

            ep_num = item['result']['extracted']['episode']
            voiceover = (item['result']['extracted'].get('voiceover') or 'default').lower()
            
            if ep_num not in episodes_dict:
                episodes_dict[ep_num] = item
            else:
                current_voiceover = (episodes_dict[ep_num]['result']['extracted'].get('voiceover') or 'default').lower()
                
                new_is_preferred = voiceover in preferred
                current_is_preferred = current_voiceover in preferred

                if new_is_preferred and not current_is_preferred:
                    episodes_dict[ep_num] = item
                elif new_is_preferred and current_is_preferred:
                    if preferred.index(voiceover) < preferred.index(current_voiceover):
                        episodes_dict[ep_num] = item
        
        unique_singles = list(episodes_dict.values())
        return unique_singles + other_items