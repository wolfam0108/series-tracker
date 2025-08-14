import os
import json
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
    внутри одного торрента.
    """
    db: Database = flask_app.db
    logger: Logger = flask_app.logger
    
    logger.info("renaming_processor", f"Запуск обработки для series_id: {series_id}, хеш: {qb_hash[:8]}")
    
    series = db.get_series(series_id)
    if not series or not series.get('parser_profile_id'):
        logger.error("renaming_processor", f"Не найден сериал или профиль парсера. Обработка прервана.")
        return

    profile_id = series['parser_profile_id']
    engine = RuleEngine(db, logger)
    formatter = FilenameFormatter(logger)
    auth_manager = AuthManager(db, logger)
    qb_client = QBittorrentClient(auth_manager, db, logger)
    
    files_in_qbit = qb_client.get_torrent_files_by_hash(qb_hash)
    if not files_in_qbit:
        logger.warning("renaming_processor", f"Не удалось получить список файлов из qBittorrent для хеша {qb_hash[:8]}.")
        return

    video_extensions = ['.mkv', '.avi', '.mp4', '.mov', '.wmv', '.webm']
    db_files_to_save = []
    
    torrent_db_entry = db.get_torrent_by_hash(qb_hash)
    if not torrent_db_entry:
        logger.error("renaming_processor", f"Торрент с хешем {qb_hash[:8]} не найден в локальной БД.")
        return

    files_in_db_map = {f['original_path']: f for f in db.get_torrent_files_for_torrent(torrent_db_entry['id'])}

    for current_path in files_in_qbit:
        # Пропускаем не-видео файлы
        if not any(current_path.lower().endswith(ext) for ext in video_extensions):
            continue

        db_record = next((r for r in files_in_db_map.values() if (r.get('renamed_path') or r['original_path']) == current_path), None)
        original_path = db_record['original_path'] if db_record else current_path
        
        basename_for_rules = os.path.basename(original_path)
        processed_result = engine.process_videos(profile_id, [{'title': basename_for_rules}])[0]
        extracted_data = processed_result.get('result', {}).get('extracted', {})

        final_renamed_path = None
        file_status = 'skipped'

        has_episode_data = extracted_data.get('episode') is not None or extracted_data.get('start') is not None
        if has_episode_data:
            target_new_path = formatter.format_filename(series, extracted_data, original_path)
            
            if current_path == target_new_path:
                file_status = 'renamed'
                final_renamed_path = current_path
            else:
                if qb_client.rename_file(qb_hash, current_path, target_new_path):
                    file_status = 'renamed'
                    final_renamed_path = target_new_path
                else:
                    file_status = 'rename_error'
        
        db_files_to_save.append({
            "original_path": original_path,
            "renamed_path": final_renamed_path,
            "status": file_status,
            "extracted_metadata": json.dumps(extracted_data)
        })

    if db_files_to_save:
        db.add_or_update_torrent_files(torrent_db_entry['id'], db_files_to_save)
        logger.info("renaming_processor", f"Обработка для хеша {qb_hash[:8]} завершена. Обновлено {len(db_files_to_save)} файлов в БД.")