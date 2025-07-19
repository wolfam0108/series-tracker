import atexit
from flask import Flask
from flask_cors import CORS

from db import Database
from logger import Logger, set_db_for_logging
from sse import sse_broadcaster
from agents.agent import Agent
from agents.monitoring_agent import MonitoringAgent
# --- ИЗМЕНЕНИЕ: Импортируем нового агента ---
from agents.downloader_agent import DownloaderAgent
from routes import init_all_routes
from debug_manager import DebugManager

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

db_url = "sqlite:///app.db"
app.logger = Logger(__name__)
app.db = Database(db_url, logger=app.logger)
set_db_for_logging(app.db)

app.debug_manager = DebugManager(app.db)
app.sse_broadcaster = sse_broadcaster

init_all_routes(app)

agent = Agent(app, app.logger, app.db, app.sse_broadcaster)
monitoring_agent = MonitoringAgent(app, app.logger, app.db, app.sse_broadcaster)
# --- ИЗМЕНЕНИЕ: Создаем и запускаем нового агента ---
downloader_agent = DownloaderAgent(app, app.logger, app.db, app.sse_broadcaster)

agent.start()
monitoring_agent.start()
downloader_agent.start()

def shutdown_agents():
    agent.shutdown()
    monitoring_agent.shutdown()
    # --- ИЗМЕНЕНИЕ: Добавляем остановку нового агента ---
    downloader_agent.shutdown()

atexit.register(shutdown_agents)

app.agent = agent
app.scanner_agent = monitoring_agent
# --- ИЗМЕНЕНИЕ: Добавляем ссылку на нового агента в приложение ---
app.downloader_agent = downloader_agent


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)