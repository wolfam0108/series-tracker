import re
import json
from typing import List, Dict, Any

class RuleEngine:
    def __init__(self, db, logger):
        self.db = db
        self.logger = logger

    def _build_regex_from_blocks(self, blocks_json: str, for_extraction: bool = False) -> str:
        try:
            blocks = json.loads(blocks_json)
        except (json.JSONDecodeError, TypeError):
            return "" 

        regex_parts = []
        
        for block in blocks:
            b_type = block.get('type')
            
            if b_type == 'text':
                regex_parts.append(re.escape(block.get('value', '')))
            elif b_type == 'number':
                if for_extraction:
                    regex_parts.append(r'(\d+)')
                else:
                    regex_parts.append(r'\d+')
            elif b_type == 'whitespace':
                regex_parts.append(r'\s+')
            elif b_type == 'any_text':
                regex_parts.append(r'.*?')
            elif b_type == 'start_of_line':
                regex_parts.append(r'^')
            elif b_type == 'end_of_line':
                regex_parts.append(r'$')
        
        return "".join(regex_parts)

    def _evaluate_conditions(self, title: str, conditions: List[Dict[str, Any]]) -> bool:
        if not conditions:
            return True

        or_group_results = []
        current_and_group_results = []

        for cond in conditions:
            regex_str = self._build_regex_from_blocks(cond['pattern'])
            if not regex_str: continue 

            match = bool(re.search(regex_str, title, re.IGNORECASE))
            result = match if cond['condition_type'] == 'contains' else not match
            
            current_and_group_results.append(result)

            if cond.get('logical_operator') == 'OR':
                or_group_results.append(all(current_and_group_results))
                current_and_group_results = []

        or_group_results.append(all(current_and_group_results))
        
        return any(or_group_results)

    def _execute_action(self, title: str, action_type: str, action_pattern: str) -> Dict[str, Any]:
        result = {'action': action_type, 'extracted': {}}

        if action_type == 'exclude':
            return result

        if action_type == 'assign_voiceover':
            result['extracted']['voiceover'] = action_pattern
            return result
        
        if action_type == 'assign_episode_number':
            try:
                assigned_data = json.loads(action_pattern)
                result['extracted']['season'] = int(assigned_data['season'])
                result['extracted']['episode'] = int(assigned_data['episode'])
                return result
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                result['error'] = f"Ошибка данных для назначения номера: {e}"
                return result

        regex_str = self._build_regex_from_blocks(action_pattern, for_extraction=True)
        if not regex_str:
            result['error'] = "Паттерн действия пуст или некорректен"
            return result

        match = re.search(regex_str, title, re.IGNORECASE)
        if not match:
            return None 

        try:
            if action_type == 'extract_single':
                result['extracted']['episode'] = int(match.group(1))
            elif action_type == 'extract_range':
                result['extracted']['start'] = int(match.group(1))
                result['extracted']['end'] = int(match.group(2))
            elif action_type == 'extract_season':
                result['extracted']['season'] = int(match.group(1))
        except (IndexError, ValueError) as e:
            result['error'] = f"Ошибка извлечения данных: {e}. Проверьте группы захвата ( ) в блоках [Число]."
        
        return result

    # --- ИЗМЕНЕНИЕ: Метод теперь принимает полные данные о видео, а не только названия ---
    def process_videos(self, profile_id: int, videos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        rules = self.db.get_rules_for_profile(profile_id)
        final_results = []

        for video_data in videos:
            title = video_data['title']
            action_result = None
            matched_rule = None

            for rule in rules:
                if self._evaluate_conditions(title, rule['conditions']):
                    temp_result = self._execute_action(title, rule['action_type'], rule['action_pattern'])
                    
                    if temp_result is not None:
                        action_result = temp_result
                        matched_rule = rule
                        break
            
            # Сохраняем исходные данные видео и добавляем результат обработки
            final_results.append({
                "source_data": video_data,
                "matched_rule_name": matched_rule['name'] if matched_rule else "Нет совпадений",
                "result": action_result
            })
            
        return final_results