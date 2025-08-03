# Файл: logic/metadata_processor.py

def build_final_metadata(series_data: dict, media_item: dict, rule_engine_data: dict) -> dict:
    """
    Централизованно собирает итоговый словарь метаданных для медиа-элемента,
    соблюдая иерархию приоритетов:
    1. Ручные настройки сериала (высший приоритет)
    2. Данные от RuleEngine
    3. Базовые данные из БД (низший приоритет)
    """
    # 1. Начинаем с базовых, надежных данных из БД
    base_metadata = {
        'season': media_item.get('season'),
        'episode': media_item.get('episode_start') if not media_item.get('episode_end') else None,
        'start': media_item.get('episode_start') if media_item.get('episode_end') else None,
        'end': media_item.get('episode_end'),
        'resolution': media_item.get('resolution'),
        'voiceover': media_item.get('voiceover_tag')
    }

    # 2. Дополняем/перезаписываем данными от RuleEngine (если они есть)
    for key, value in rule_engine_data.items():
        if value is not None:
            # Преобразуем ключ 'voiceover' от RuleEngine в 'voiceover' в метаданных
            # (на случай, если где-то используется старый ключ)
            metadata_key = 'voiceover' if key == 'voiceover' else key
            base_metadata[metadata_key] = value
            
    # 3. Применяем ручные настройки из свойств сериала - они имеют наивысший приоритет
    if series_data.get('quality_override'):
        base_metadata['quality'] = series_data.get('quality_override')
        
    if series_data.get('resolution_override'):
        base_metadata['resolution'] = series_data.get('resolution_override')

    # Если сезон жестко задан в свойствах сериала, он главнее всего
    if series_data.get('season'):
        base_metadata['season'] = series_data.get('season')

    return base_metadata