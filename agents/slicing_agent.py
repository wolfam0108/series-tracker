import threading
import time
import json
import os
import select
import subprocess
from flask import Flask
from datetime import datetime
from db import Database
from logger import Logger
from sse import ServerSentEvent
from filename_formatter import FilenameFormatter
from utils.path_finder import get_executable_path
from status_manager import StatusManager

class SlicingAgent(threading.Thread):
    def __init__(self, app: Flask, logger: Logger, db: Database, broadcaster: ServerSentEvent, status_manager: StatusManager):
        super().__init__(daemon=True)
        self.name = "SlicingAgent"
        self.app = app
        self.logger = logger
        self.db = db
        self.broadcaster = broadcaster
        self.shutdown_flag = threading.Event()
        self.CHECK_INTERVAL = 5
        self.status_manager = status_manager
        # 2. Создаем "канал пробуждения"
        self._shutdown_pipe_r, self._shutdown_pipe_w = os.pipe()

    def recover_tasks(self):
        """Восстанавливает прерванные задачи при старте."""
        with self.app.app_context():
            self.logger.info("slicing_agent", "Проверка на наличие незавершенных задач нарезки...")
            requeued_count = self.db.requeue_stuck_slicing_tasks()
            if requeued_count > 0:
                self.logger.info("slicing_agent", f"Возвращено в очередь {requeued_count} 'зависших' задач на нарезку.")
                self._broadcast_queue_update()
            else:
                self.logger.info("slicing_agent", "Незавершенных задач нарезки не найдено. Всё в порядке.")

    def _process_task(self, task):
        unique_id = task['media_item_unique_id']
        task_id = task['id']
        series_id = task['series_id']
        
        try:
            self.status_manager.set_status(series_id, 'slicing', True)
            self.db.update_slicing_task(task_id, {'status': 'slicing'})
            self.db.update_media_item_slicing_status(unique_id, 'slicing')
            self._broadcast_queue_update()

            media_item = self.db.get_media_item_by_uid(unique_id)
            series = self.db.get_series(media_item['series_id'])
            source_file = media_item['final_filename']
            chapters = json.loads(media_item['chapters'])
            
            if not os.path.exists(source_file):
                raise FileNotFoundError(f"Исходный файл не найден: {source_file}")

            progress = json.loads(task['progress_chapters']) if task['progress_chapters'] and task['progress_chapters'] != '{}' else {}
            formatter = FilenameFormatter(self.logger)
            
            if not progress:
                self.logger.info("slicing_agent", "Первый запуск задачи. Проверка существующих файлов...")
                for i in range(len(chapters)):
                    episode_number = media_item['episode_start'] + i
                    progress[str(episode_number)] = 'pending'
                
                for i, chapter in enumerate(chapters):
                    episode_number = media_item['episode_start'] + i

                    # Создаем "плоский" словарь с метаданными
                    metadata = {
                        'season': media_item.get('season'),
                        'episode': episode_number
                    }
                    expected_filename = formatter.format_filename(series, temp_media_item_data)
                    expected_path = os.path.join(os.path.dirname(source_file), expected_filename)
                    if os.path.exists(expected_path):
                        self.logger.info("slicing_agent", f"Найден существующий файл для эпизода {episode_number}. Помечаем как выполненный.")
                        progress[str(episode_number)] = 'completed'
                        self.db.add_sliced_file(series['id'], unique_id, episode_number, expected_path)
                
                self.db.update_slicing_task(task_id, {'progress_chapters': json.dumps(progress)})
                self._broadcast_queue_update()

            ffmpeg_executable = get_executable_path('ffmpeg')

            for i, chapter in enumerate(chapters):
                episode_number = media_item['episode_start'] + i
                if progress.get(str(episode_number)) == 'completed':
                    self.logger.info("slicing_agent", f"Эпизод {episode_number} уже нарезан, пропуск.")
                    continue

                start_time = chapter['time']
                end_time_str = chapters[i+1]['time'] if i + 1 < len(chapters) else None
                FMT = '%H:%M:%S'
                start_dt = datetime.strptime(start_time, FMT)
                
                command = [ffmpeg_executable, '-y', '-ss', start_time, '-i', source_file]
                
                if end_time_str:
                    end_dt = datetime.strptime(end_time_str, FMT)
                    duration = end_dt - start_dt
                    command.extend(['-t', str(duration)])
                command.extend(['-c', 'copy'])
                
                temp_media_item_data = { 'result': { 'extracted': { 'season': media_item['season'], 'episode': episode_number } } }
                output_filename = formatter.format_filename(series, temp_media_item_data)
                output_path = os.path.join(os.path.dirname(source_file), output_filename)
                command.append(output_path)
                
                self.logger.info("slicing_agent", f"Запуск ffmpeg для эпизода {episode_number}: {' '.join(command)}")
                result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
                
                if result.returncode != 0:
                    raise Exception(f"Ошибка ffmpeg для эпизода {episode_number}: {result.stderr}")

                self.db.add_sliced_file(series['id'], unique_id, episode_number, output_path)
                progress[str(episode_number)] = 'completed'
                self.db.update_slicing_task(task_id, {'progress_chapters': json.dumps(progress)})
                self._broadcast_queue_update()

            self.logger.info("slicing_agent", f"Нарезка для UID {unique_id} успешно завершена.")
            
            self.db.update_media_item_slicing_status(unique_id, 'completed')
            self.db.set_media_item_ignored_status_by_uid(unique_id, True)
            self.logger.info("slicing_agent", f"Компиляция {unique_id} помечена как обработанная и игнорируемая.")

            delete_source_enabled = self.db.get_setting('slicing_delete_source_file', 'false') == 'true'
            if delete_source_enabled:
                try:
                    os.remove(source_file)
                    self.logger.info("slicing_agent", f"Исходный файл {source_file} удален согласно настройке.")
                except OSError as e:
                    self.logger.error("slicing_agent", f"Не удалось удалить исходный файл {source_file}: {e}")

            self.db.delete_slicing_task(task_id)

        except Exception as e:
            self.logger.error("slicing_agent", f"Ошибка при обработке задачи нарезки ID {task_id}: {e}", exc_info=True)
            self.db.update_slicing_task(task_id, {'status': 'error', 'error_message': str(e)})
            self.db.update_media_item_slicing_status(unique_id, 'error')
            self.status_manager.set_status(series_id, 'error', True)
        finally:
            self.status_manager.set_status(series_id, 'slicing', False)
            self._broadcast_queue_update()

    def run(self):
        self.logger.info(f"{self.name} запущен.")
        time.sleep(10)
        self.recover_tasks()

        while not self.shutdown_flag.is_set():
            # 3. Заменяем shutdown_flag.wait() на select()
            readable, _, _ = select.select([self._shutdown_pipe_r], [], [], self.CHECK_INTERVAL)
            if readable:
                break
                
            with self.app.app_context():
                self.broadcaster.broadcast('agent_heartbeat', {'name': 'slicing'})
                task = self.db.get_pending_slicing_task()
            
                if task:
                    self.logger.info("slicing_agent", f"Взята в работу задача на нарезку ID: {task['id']}")
                    self._process_task(task)
        
        # 4. Очищаем ресурсы pipe после выхода из цикла
        os.close(self._shutdown_pipe_r)
        os.close(self._shutdown_pipe_w)
        self.logger.info(f"{self.name} был остановлен.")

    def shutdown(self):
        self.logger.info(f"{self.name}: получен сигнал на остановку.")
        self.shutdown_flag.set()
        try:
            # 5. Пишем в pipe, чтобы мгновенно разбудить поток из select()
            os.write(self._shutdown_pipe_w, b'x')
        except OSError:
            pass
    
    def _broadcast_queue_update(self):
        """Собирает активные задачи нарезки и транслирует их через SSE."""
        # Контекст здесь уже не нужен, так как метод вызывается из _process_task,
        # который, в свою очередь, вызывается из run() внутри контекста.
        # Но для безопасности и независимости вызовов его можно оставить.
        with self.app.app_context():
            active_tasks = self.db.get_all_slicing_tasks()
            self.broadcaster.broadcast('slicing_queue_update', active_tasks)
