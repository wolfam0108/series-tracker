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
            
            # --- ИЗМЕНЕНИЕ: Пропускаем блоки операций при построении регулярного выражения ---
            if b_type in ['add', 'subtract']:
                continue
            
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

        capture_group_index = 1
        for action in actions:
            action_type = action.get('action_type')
            action_pattern_json = action.get('action_pattern', '[]')

            if action_type == 'exclude':
                return {'action': 'exclude', 'extracted': {}}

            # Блок для действий-назначений (assign)
            if action_type == 'assign_voiceover':
                final_result['extracted']['voiceover'] = action_pattern_json
            elif action_type == 'assign_episode':
                try:
                    final_result['extracted']['episode'] = int(action_pattern_json)
                except (ValueError, TypeError):
                    final_result.setdefault('error', []).append(f"Ошибка назначения номера серии: некорректное значение '{action_pattern_json}'")
            elif action_type == 'assign_season':
                try:
                    final_result['extracted']['season'] = int(action_pattern_json)
                except (ValueError, TypeError):
                    final_result.setdefault('error', []).append(f"Ошибка назначения номера сезона: некорректное значение '{action_pattern_json}'")
            
            # Блок для действий-извлечений (extract) с новой логикой
            else:
                regex_str = self._build_regex_from_blocks(action_pattern_json, for_extraction=True)
                if not regex_str:
                    continue

                match = re.search(regex_str, title, re.IGNORECASE)
                if not match:
                    continue

                try:
                    action_blocks = json.loads(action_pattern_json)
                    number_blocks_indices = [i for i, block in enumerate(action_blocks) if block.get('type') == 'number']
                    
                    current_match_index = 0
                    for block_index in number_blocks_indices:
                        original_value_str = match.group(capture_group_index + current_match_index)
                        original_value = int(original_value_str)
                        final_value = original_value

                        # Проверяем, есть ли следующий блок и является ли он операцией
                        if block_index + 1 < len(action_blocks):
                            modifier_block = action_blocks[block_index + 1]
                            mod_type = modifier_block.get('type')
                            
                            if mod_type in ['add', 'subtract']:
                                try:
                                    mod_value = int(modifier_block.get('value', 0))
                                    temp_result = original_value + mod_value if mod_type == 'add' else original_value - mod_value
                                    
                                    # ВАШЕ ПРАВИЛО: Не выполнять операцию, если результат < 0
                                    if temp_result >= 0:
                                        final_value = temp_result
                                    else:
                                        self.logger.warning("rule_engine", f"Операция '{mod_type} {mod_value}' для числа {original_value} проигнорирована, т.к. результат ({temp_result}) < 0.")
                                except (ValueError, TypeError):
                                    pass # Игнорируем, если значение в блоке операции - не число

                        # Присваиваем результат в зависимости от типа действия
                        if action_type == 'extract_single':
                            final_result['extracted']['episode'] = final_value
                        elif action_type == 'extract_season':
                            final_result['extracted']['season'] = final_value
                        elif action_type == 'extract_range':
                            if current_match_index == 0:
                                final_result['extracted']['start'] = final_value
                            elif current_match_index == 1:
                                final_result['extracted']['end'] = final_value

                        current_match_index += 1
                    
                    capture_group_index += len(number_blocks_indices)

                except (IndexError, ValueError) as e:
                    final_result.setdefault('error', []).append(f"Ошибка извлечения для '{action_type}': {e}")
        
        return final_result

    def process_videos(self, profile_id: int, videos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        rules = self.db.get_rules_for_profile(profile_id)
        final_results = []

        for video_data in videos:
            title = video_data['title']
            
            # ---> НАЧАЛО ИЗМЕНЕНИЙ: Новая, более детальная структура <---
            match_events = [] # Список событий для каждого сработавшего правила
            final_extracted_data = {} # Итоговые накопленные данные

            for rule in rules:
                if self._evaluate_conditions(title, rule['conditions']):
                    temp_result = self._execute_actions(title, rule['action_pattern'])
                    
                    if temp_result:
                        # Если действие - исключить, это финальное событие
                        if temp_result.get('action') == 'exclude':
                            match_events.append({
                                'rule_name': rule['name'],
                                'action': 'exclude',
                                'extracted': {}
                            })
                            break 

                        # Сохраняем, что именно извлекло это правило
                        extracted_by_this_rule = temp_result.get('extracted', {})
                        if extracted_by_this_rule:
                            match_events.append({
                                'rule_name': rule['name'],
                                'action': 'extract',
                                'extracted': extracted_by_this_rule
                            })
                            # Обновляем итоговые данные
                            final_extracted_data.update(extracted_by_this_rule)

                        # Если нет флага "продолжить", прерываем цикл
                        if not rule.get('continue_after_match', False):
                            break
            
            final_results.append({
                "source_data": video_data,
                "match_events": match_events, # Детальный список
                "result": { # Общий результат
                    'extracted': final_extracted_data
                }
            })
            # ---> КОНЕЦ ИЗМЕНЕНИЙ <---
            
        return final_results