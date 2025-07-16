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

        valid_items = [item for item in processed_items if item.get('result') and not item['result'].get('error')]
        unique_items = self._resolve_voiceover_duplicates(valid_items, preferred_voiceovers_str)
        self.logger.debug(f"smart_collector: После фильтрации и разрешения дубликатов озвучек осталось {len(unique_items)} элементов.")
        
        # --- ИЗМЕНЕНИЕ: Полностью новая, более надежная логика сборки ---

        # 1. Создаем карту всех возможных источников для каждой серии
        episode_sources: Dict[int, List[Dict[str, Any]]] = {}
        all_items_map = {id(item): item for item in unique_items} # Карта для быстрого доступа к объектам

        for item in unique_items:
            extracted = item.get('result', {}).get('extracted', {})
            if 'episode' in extracted:
                ep_num = extracted['episode']
                if ep_num not in episode_sources:
                    episode_sources[ep_num] = []
                episode_sources[ep_num].append(item)
            elif 'start' in extracted and 'end' in extracted:
                for ep_num in range(extracted['start'], extracted['end'] + 1):
                    if ep_num not in episode_sources:
                        episode_sources[ep_num] = []
                    episode_sources[ep_num].append(item)
        
        # 2. Выбираем лучший источник для каждой серии
        final_coverage: Dict[int, Dict[str, Any]] = {}
        
        sorted_episodes = sorted(episode_sources.keys())
        for ep_num in sorted_episodes:
            candidates = episode_sources[ep_num]
            if not candidates: continue

            # Приоритет: одиночные серии > компиляции.
            # Если есть хоть один кандидат-одиночка, выбираем его. Иначе - любую из компиляций.
            best_choice = next((c for c in candidates if 'episode' in c.get('result', {}).get('extracted', {})), candidates[0])
            final_coverage[ep_num] = best_choice
            
        # 3. Присваиваем статусы на основе финального выбора
        used_item_ids = {id(item) for item in final_coverage.values()}

        for item_id, item in all_items_map.items():
            extracted = item.get('result', {}).get('extracted', {})
            is_used = item_id in used_item_ids

            if 'episode' in extracted:
                item['status'] = 'new' if is_used else 'discarded'
            elif 'start' in extracted and 'end' in extracted:
                item['status'] = 'new_compilation' if is_used else 'redundant'
            else:
                item['status'] = 'processed'
        
        final_plan = list(all_items_map.values())
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---

        # 4. Проверяем по существующим в БД элементам.
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
            if not item.get('result', {}).get('extracted', {}).get('episode'):
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
                    # Если обе озвучки в преферируемых, выбираем ту, что в списке раньше (выше приоритет)
                    if preferred.index(voiceover) < preferred.index(current_voiceover):
                        episodes_dict[ep_num] = item
                # Если новая не в приоритете, а текущая - да, ничего не делаем.
        
        unique_singles = list(episodes_dict.values())
        return unique_singles + other_items