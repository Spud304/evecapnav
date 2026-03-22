import os
import logging

from dotenv import load_dotenv

from src.models.models import db
from src.application import Application
from src.celery_app import celery_init_app
from src.routes import RouteBlueprint, init_route_data

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

STATIC_DB = os.environ.get("STATIC_DB", "sqlite-latest")

instance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance")
app = Application(__name__, instance_path=instance_path)

app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{STATIC_DB}.sqlite"
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")
app.config.from_mapping(
    CELERY={
        "broker_url": os.environ.get("CELERY_BROKER_URL", "redis://localhost:6380/0"),
        "result_backend": os.environ.get(
            "CELERY_RESULT_BACKEND", "redis://localhost:6380/0"
        ),
        "task_ignore_result": False,
        "beat_schedule": {
            "poll-system-stats": {
                "task": "src.tasks.poll_system_stats",
                "schedule": 3600.0,
            },
        },
    },
)

db.init_app(app)
celery_app = celery_init_app(app)

route_blueprint = RouteBlueprint("routes", __name__)
app.register_blueprint(route_blueprint)

# Only init route data for the web app, not celery workers
if os.environ.get("CELERY_WORKER") != "1":
    init_route_data(app)

if __name__ == "__main__":
    app.run(debug=False, host="localhost", port=6001)
