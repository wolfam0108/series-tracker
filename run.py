import atexit
from flask import Flask
from flask_cors import CORS

from db import Database
from logger import Logger, set_db_for_logging
from sse import sse_broadcaster
from agents.agent import Agent
from agents.monitoring_agent import MonitoringAgent
from agents.downloader_agent import DownloaderAgent
from agents.slicing_agent import SlicingAgent
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
downloader_agent = DownloaderAgent(app, app.logger, app.db, app.sse_broadcaster)
slicing_agent = SlicingAgent(app, app.logger, app.db, app.sse_broadcaster)

agent.start()
monitoring_agent.start()
downloader_agent.start()
slicing_agent.start()

def shutdown_agents():
    agent.shutdown()
    monitoring_agent.shutdown()
    downloader_agent.shutdown()
    slicing_agent.shutdown()

atexit.register(shutdown_agents)

app.agent = agent
app.scanner_agent = monitoring_agent
app.downloader_agent = downloader_agent
app.slicing_agent = slicing_agent


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)