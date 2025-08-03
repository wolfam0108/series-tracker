import signal
import sys
import atexit
import time # Добавьте импорт time, если его нет
from flask import Flask
from flask_cors import CORS

from db import Database
from logger import Logger, set_db_for_logging
from sse import sse_broadcaster
from agents.agent import Agent
from agents.monitoring_agent import MonitoringAgent
from agents.downloader_agent import DownloaderAgent
from agents.slicing_agent import SlicingAgent
from agents.renaming_agent import RenamingAgent
from routes import init_all_routes
from debug_manager import DebugManager
from status_manager import StatusManager


app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

db_url = "sqlite:///app.db"
app.logger = Logger(__name__)
app.db = Database(db_url, logger=app.logger)
set_db_for_logging(app.db)

app.debug_manager = DebugManager(app.db)
app.sse_broadcaster = sse_broadcaster
app.status_manager = StatusManager(app, app.db, app.sse_broadcaster, app.logger)

init_all_routes(app)

agent = Agent(app, app.logger, app.db, app.sse_broadcaster, app.status_manager)
monitoring_agent = MonitoringAgent(app, app.logger, app.db, app.sse_broadcaster, app.status_manager)
downloader_agent = DownloaderAgent(app, app.logger, app.db, app.sse_broadcaster, app.status_manager)
slicing_agent = SlicingAgent(app, app.logger, app.db, app.sse_broadcaster, app.status_manager)
renaming_agent = RenamingAgent(app, app.logger, app.db)

# agent.start()
# monitoring_agent.start()
# downloader_agent.start()
# slicing_agent.start()

def post_fork_hook(server, worker):
    """Этот хук вызывается Gunicorn в рабочем процессе ПОСЛЕ его создания."""
    app.logger.info("run", f"Worker (pid: {worker.pid}) forked. Starting background agents...")
    
    # Запускаем агентов здесь, в контексте воркера
    agent.start()
    monitoring_agent.start()
    downloader_agent.start()
    slicing_agent.start()
    renaming_agent.start()
    
    app.logger.info("run", "All agents started successfully in the worker process.")

def shutdown_agents():
    agent.shutdown()
    monitoring_agent.shutdown()
    downloader_agent.shutdown()
    slicing_agent.shutdown()

app.agent = agent
app.scanner_agent = monitoring_agent
app.downloader_agent = downloader_agent
app.slicing_agent = slicing_agent
app.renaming_agent = renaming_agent

def on_exit(server):
    """Gunicorn pre_stop hook."""
    app.logger.info("run", "Gunicorn pre_stop: Завершаем работу фоновых агентов...")
    # Используем уже созданные и запущенные экземпляры агентов
    app.agent.shutdown()
    app.scanner_agent.shutdown()
    app.downloader_agent.shutdown()
    app.slicing_agent.shutdown()
    app.renaming_agent.shutdown()
    
    # Даем агентам немного времени на завершение.
    # Так как CHECK_INTERVAL = 10, дадим им 11 секунд.
    app.logger.info("run", "Gunicorn pre_stop: Ожидание завершения потоков (11 секунд)...")
    time.sleep(11) 
    app.logger.info("run", "Gunicorn pre_stop: Завершение работы хука.")

def signal_handler(signum, frame):
    """Обработчик сигналов для грациозного завершения работы."""
    app.logger.info("run", f"Получен сигнал {signal.Signals(signum).name}. Завершение работы агентов...")
    shutdown_agents()
    app.logger.info("run", "Агенты остановлены. Выход.")
    # Даем Gunicorn немного времени на завершение перед принудительным выходом
    sys.exit(0)

def shutdown_agents():
    agent.shutdown()
    monitoring_agent.shutdown()
    downloader_agent.shutdown()
    slicing_agent.shutdown()

# Регистрируем обработчик для сигналов завершения
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGQUIT, signal_handler)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)