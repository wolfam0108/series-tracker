import os
import json
import re
from flask import Flask
from db import Database
from logger import Logger
from qbittorrent import QBittorrentClient
from rule_engine import RuleEngine
from filename_formatter import FilenameFormatter
from auth import AuthManager

def process_and_rename_torrent_files(flask_app: Flask, series_id: int, qb_hash: str):
    """
    Централизованная функция для полной обработки и переименования файлов
    внутри одного торрента с распределением по папкам сезонов.
    """
    db: Database = flask_app.db
    logger: Logger = flask_app.logger
    
    logger.info("renaming_processor", f"Запуск обработки с распределением по сезонам для series_id: {series_id}, хеш: {qb_hash[:8]}")
    
    series = db.get_series(series_id)
    if not series or not series.get('parser_profile_id'):
        logger.error("renaming_processor", f"Не найден сериал или профиль парсера. Обработка прервана.")
        return

    profile_id = series['parser_profile_id']
    engine = RuleEngine(db, logger)
    formatter = FilenameFormatter(logger)
    auth_manager = AuthManager(db, logger)
    qb_client = QBittorrentClient(auth_manager, db, logger)
    
    # Получаем список файлов из qBittorrent
    files_in_qbit = qb_client.get_torrent_files_by_hash(qb_hash)
    if not files_in_qbit:
        logger.warning("renaming_processor", f"Не удалось получить список файлов из qBittorrent для хеша {qb_hash[:8]}.")
        return

    # Получаем торрент из базы данных
    torrent_db_entry = db.get_torrent_by_hash(qb_hash)
    if not torrent_db_entry:
        logger.error("renaming_processor", f"Торрент с хешем {qb_hash[:8]} не найден в базе данных")
        return
    
    # Получаем файлы торрента из базы данных
    files_in_db_map = {f['original_path']: f for f in db.get_torrent_files_for_torrent(torrent_db_entry['id'])}
    
    # Обрабатываем каждый файл
    video_extensions = ['.mkv', '.avi', '.mp4', '.mov', '.wmv', '.webm']
    db_files_to_save = []
    
    for current_path in files_in_qbit:
        # Пропускаем не-видео файлы
        if not any(current_path.lower().endswith(ext) for ext in video_extensions):
            continue
        
        db_record = next((r for r in files_in_db_map.values() if (r.get('renamed_path') or r['original_path']) == current_path), None)
        original_path = db_record['original_path'] if db_record else current_path
        
        # Извлекаем только имя файла для анализа правил, игнорируя подкаталоги
        file_basename = os.path.basename(original_path)
        
        # Обрабатываем файл через движок правил, чтобы извлечь метаданные
        processed_result = engine.process_videos(profile_id, [{'title': file_basename}])[0]
        extracted_data = processed_result.get('result', {}).get('extracted', {})
        
        # Получаем номер сезона из извлеченных метаданных
        season_number = extracted_data.get('season')

        # Определяем, является ли сериал многосезонным или односезонным
        # Если в series['season'] есть значение, значит это односезонный сериал - используем этот сезон
        # Если в series['season'] пусто, значит это многосезонный сериал - используем сезон из extracted_data
        if series.get('season'):  # Если поле season заполнено, это односезонный сериал
            try:
                # Извлекаем числовое значение из строки сезона, например "s03", "S03", "season 3" и т.д.
                season_str = str(series['season']).strip()
                season_match = re.search(r'\d+', season_str)
                if season_match:
                    season_number = int(season_match.group())
                    logger.info("renaming_processor", f"Номер сезона получен из базы данных (односезонный сериал): {season_number}")
                else:
                    logger.warning("renaming_processor", f"Не удалось извлечь числовое значение сезона из строки: {series['season']}")
            except (ValueError, TypeError):
                logger.warning("renaming_processor", f"Не удалось преобразовать номер сезона из базы данных: {series['season']}")
        # else: для многосезонного сериала season_number остается из extracted_data

        if season_number is None:
            # Для многосезонных сериалов (где series['season'] пустой) сезон должен быть определен из extracted_data
            # Если сезон не определен, используем сезон по умолчанию (например, Season 00 для специальных серий или Season 01)
            if not series.get('season'):
                # Это многосезонный сериал, но сезон не определен из имени файла
                # Попробуем определить из подкаталога или использовать значение по умолчанию
                if 'specials' in os.path.dirname(original_path).lower():
                    season_number = 0 # Специальные серии в Season 00
                else:
                    # Для многосезонных сериалов, если не удалось определить сезон, используем Season 01
                    logger.warning("renaming_processor", f"Не удалось определить номер сезона для файла '{current_path}' в многосезонном сериале, используем Season 01")
                    season_number = 1
            else:
                logger.warning("renaming_processor", f"Не удалось определить номер сезона для файла '{current_path}', пропускаем")
                continue
        
        # Формируем имя папки сезона
        season_folder_name = f"Season {season_number:02d}"
        
        # Форматируем новое имя файла
        filename = formatter.format_filename(series, extracted_data, file_basename)
        
        # Создаем новый путь, добавив папку сезона
        new_file_path = os.path.join(season_folder_name, filename).replace("\\", "/")
        
        logger.info("renaming_processor", f"Переименование файла в qBittorrent: '{current_path}' -> '{new_file_path}'")
        
        # Переименовываем файл в qBittorrent
        if qb_client.rename_file(qb_hash, current_path, new_file_path):
            final_renamed_path = new_file_path
            file_status = 'renamed'
        else:
            logger.error("renaming_processor", f"Не удалось переименовать файл в qBittorrent '{current_path}' -> '{new_file_path}'")
            final_renamed_path = None
            file_status = 'rename_error'
        
        db_files_to_save.append({
            "original_path": original_path,
            "renamed_path": final_renamed_path,
            "status": file_status,
            "extracted_metadata": json.dumps(extracted_data)
        })
    
    if db_files_to_save:
        db.add_or_update_torrent_files(torrent_db_entry['id'], db_files_to_save)
        successful_renames = len([f for f in db_files_to_save if f['status'] == 'renamed'])
        logger.info("renaming_processor", f"Обработка файлов торрента {qb_hash[:8]} завершена. Успешно переименовано: {successful_renames}/{len(db_files_to_save)}")
    
    return True

