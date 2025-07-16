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

    def _execute_actions(self, title: str, actions_json: str) -> Dict[str, Any]:
        final_result = {'action': 'multi_action', 'extracted': {}}
        
        try:
            actions = json.loads(actions_json)
            if not isinstance(actions, list):
                final_result['error'] = "Action pattern не является списком."
                return final_result
        except (json.JSONDecodeError, TypeError):
            final_result['error'] = "Некорректный JSON в action_pattern."
            return final_result

        for action in actions:
            action_type = action.get('action_type')
            action_pattern = action.get('action_pattern', '[]')

            if action_type == 'exclude':
                return {'action': 'exclude', 'extracted': {}} # Если есть exclude, сразу выходим

            if action_type == 'assign_voiceover':
                final_result['extracted']['voiceover'] = action_pattern
            
            # --- ИЗМЕНЕНИЕ: Обработка разделенных действий ---
            elif action_type == 'assign_episode':
                try:
                    final_result['extracted']['episode'] = int(action_pattern)
                except (ValueError, TypeError):
                    final_result.setdefault('error', []).append(f"Ошибка назначения номера серии: некорректное значение '{action_pattern}'")
            
            elif action_type == 'assign_season':
                try:
                    final_result['extracted']['season'] = int(action_pattern)
                except (ValueError, TypeError):
                    final_result.setdefault('error', []).append(f"Ошибка назначения номера сезона: некорректное значение '{action_pattern}'")
            
            else: # Логика для извлечения
                regex_str = self._build_regex_from_blocks(action_pattern, for_extraction=True)
                if not regex_str:
                    final_result.setdefault('error', []).append(f"Паттерн для '{action_type}' пуст.")
                    continue

                match = re.search(regex_str, title, re.IGNORECASE)
                if not match:
                    continue

                try:
                    if action_type == 'extract_single':
                        final_result['extracted']['episode'] = int(match.group(1))
                    elif action_type == 'extract_range':
                        final_result['extracted']['start'] = int(match.group(1))
                        final_result['extracted']['end'] = int(match.group(2))
                    elif action_type == 'extract_season':
                        final_result['extracted']['season'] = int(match.group(1))
                except (IndexError, ValueError) as e:
                    final_result.setdefault('error', []).append(f"Ошибка извлечения для '{action_type}': {e}")
        
        return final_result

    def process_videos(self, profile_id: int, videos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        rules = self.db.get_rules_for_profile(profile_id)
        final_results = []

        for video_data in videos:
            title = video_data['title']
            action_result = None
            matched_rule = None

            for rule in rules:
                if self._evaluate_conditions(title, rule['conditions']):
                    temp_result = self._execute_actions(title, rule['action_pattern'])
                    
                    if temp_result is not None:
                        action_result = temp_result
                        matched_rule = rule
                        break
            
            final_results.append({
                "source_data": video_data,
                "matched_rule_name": matched_rule['name'] if matched_rule else "Нет совпадений",
                "result": action_result
            })
            
        return final_results