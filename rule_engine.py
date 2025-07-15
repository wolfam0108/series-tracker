import re
import json
from typing import List, Dict, Any

class RuleEngine:
    def __init__(self, db, logger):
        self.db = db
        self.logger = logger

    def _build_regex_from_blocks(self, blocks_json: str, for_extraction: bool = False) -> str:
        """Преобразует JSON с блоками в строку regex."""
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
                # Если этот regex используется для извлечения, оборачиваем в группу
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
        result = {'original_title': title, 'action': action_type, 'extracted': None}

        if action_type == 'exclude':
            return result

        regex_str = self._build_regex_from_blocks(action_pattern, for_extraction=True)
        if not regex_str:
            result['error'] = "Паттерн действия пуст или некорректен"
            return result

        match = re.search(regex_str, title, re.IGNORECASE)
        # Если паттерн действия не нашел совпадения, действие считается проваленным
        if not match:
            return None 

        try:
            if action_type == 'extract_single':
                result['extracted'] = {'episode': int(match.group(1))}
            elif action_type == 'extract_range':
                result['extracted'] = {'start': int(match.group(1)), 'end': int(match.group(2))}
            elif action_type == 'extract_season':
                result['extracted'] = {'season': int(match.group(1))}
        except (IndexError, ValueError) as e:
            result['error'] = f"Ошибка извлечения данных: {e}. Проверьте группы захвата ( ) в блоках [Число]."
        
        return result

    def test_rules_on_titles(self, profile_id: int, titles: List[str]) -> List[Dict[str, Any]]:
        # --- ИЗМЕНЕНИЕ: Логика полностью переписана ---
        rules = self.db.get_rules_for_profile(profile_id)
        final_results = []

        for title in titles:
            action_result = None
            matched_rule = None

            for rule in rules:
                # 1. Проверяем, выполняются ли условия "ЕСЛИ"
                if self._evaluate_conditions(title, rule['conditions']):
                    # 2. Если да, пытаемся выполнить действие "ТО"
                    temp_result = self._execute_action(title, rule['action_type'], rule['action_pattern'])
                    
                    # 3. Правило считается сработавшим, только если действие было успешным.
                    #    _execute_action возвращает None, если его паттерн не сработал.
                    if temp_result is not None:
                        action_result = temp_result
                        matched_rule = rule
                        # 4. Успех! Прерываем цикл и переходим к следующему названию.
                        break
            
            final_results.append({
                "title": title,
                "matched_rule_id": matched_rule['id'] if matched_rule else None,
                "matched_rule_name": matched_rule['name'] if matched_rule else "Нет совпадений",
                "result": action_result
            })
            
        return final_results
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---