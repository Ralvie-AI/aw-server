import atexit
from datetime import datetime, timedelta
import json
import logging
import os
from pathlib import Path
import platform
import re
from typing import Dict, List, Optional

from flask import Blueprint, Flask, current_app, send_from_directory
import flask.json.provider
from flask_cors import CORS
from sd_core.dirs import get_data_dir
import sd_datastore
from sd_datastore import Datastore
from werkzeug.serving import make_server

from . import rest, screen_shot
from .api import ServerAPI
from .log import FlaskLogHandler

logger = logging.getLogger(__name__)

APP_FOLDER = os.path.dirname(os.path.abspath(__file__))
STATIC_FOLDER = os.path.join(APP_FOLDER, "static")

root = Blueprint("root", __name__, url_prefix="/")


# ------------------------------------------------------------------
# Runtime Port Discovery File
# ------------------------------------------------------------------
def _get_runtime_port_file() -> Path:
    return Path(get_data_dir("sd-server")) / "server_runtime.json"


def _remove_runtime_port() -> None:
    port_file = _get_runtime_port_file()
    try:
        if port_file.exists():
            data = json.loads(port_file.read_text(encoding="utf-8"))
            if data.get("pid") == os.getpid():
                port_file.unlink(missing_ok=True)
    except Exception:
        pass


def _write_runtime_port(port: int) -> None:
    port_file = _get_runtime_port_file()
    port_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = port_file.with_suffix(".tmp")
    tmp_file.write_text(
        json.dumps({"port": port, "pid": os.getpid()}),
        encoding="utf-8",
    )
    os.replace(tmp_file, port_file)  # Atomic replace prevents partial reads
    atexit.register(_remove_runtime_port)


# ------------------------------------------------------------------
# Keyring Integrity Check (Windows)
# ------------------------------------------------------------------
def is_valid_keyring_file() -> tuple[bool, Optional[str]]:
    local_app_data = os.getenv("LOCALAPPDATA")
    if not local_app_data:
        return False, None

    cfg_file = os.path.join(local_app_data, "Python Keyring", "keyring_pass.cfg")
    logger.info("Checking keyring file %s", cfg_file)
    if os.path.exists(cfg_file):
        with open(cfg_file, "rb") as f:
            chunk = f.read(1024)
        return b"\x00" in chunk, cfg_file
    return False, None


# ------------------------------------------------------------------
# Flask Application & JSON Provider
# ------------------------------------------------------------------
class CustomJSONProvider(flask.json.provider.DefaultJSONProvider):
    def default(self, obj, *args, **kwargs):
        try:
            if isinstance(obj, datetime):
                return obj.isoformat()
            if isinstance(obj, timedelta):
                return obj.total_seconds()
        except TypeError:
            pass
        return super().default(obj)


class AWFlask(Flask):
    def __init__(
        self,
        host: str,
        testing: bool,
        storage_method=None,
        cors_origins: Optional[List[str]] = None,
        custom_static: Optional[Dict[str, str]] = None,
        static_folder: str = STATIC_FOLDER,
        static_url_path: str = "",
    ) -> None:
        self.json_provider_class = CustomJSONProvider
        self.json_provider_class.compact = not testing

        super().__init__(
            "sd-server",
            static_folder=static_folder,
            static_url_path=static_url_path,
        )

        self.config["HOST"] = host
        self.config["PORT"] = None

        with self.app_context():
            _config_cors(list(cors_origins or []), testing)

        if storage_method is None:
            storage_method = sd_datastore.get_storage_methods()["memory"]

        db = Datastore(storage_method, testing=testing)
        self.api = ServerAPI(db=db, testing=testing)
        self.api.ralvie_server_queue.start()
        self.api.screen_shot_queue.start()

        self.register_blueprint(root)
        self.register_blueprint(rest.blueprint)
        self.register_blueprint(screen_shot.blueprint)


def _config_cors(cors_origins: List[str], testing: bool) -> None:
    if cors_origins:
        logger.warning(
            "Running with additional allowed CORS origins specified through config "
            "or CLI argument (could be a security risk): %s",
            cors_origins,
        )

    allowed_origins: list = list(cors_origins)

    # Allow loopback origins on any dynamic ephemeral port (e.g., QWebEngineView / local UI)
    allowed_origins.extend(
        [
            re.compile(r"^http://127\.0\.0\.1(:\d+)?$"),
            re.compile(r"^http://localhost(:\d+)?$"),
            "moz-extension://*",
        ]
    )

    if testing:
        allowed_origins.append("http://127.0.0.1:27180/*")

    CORS(current_app, resources={r"/api/*": {"origins": allowed_origins}})


# ------------------------------------------------------------------
# Static Routes
# ------------------------------------------------------------------
@root.route("/")
def static_root():
    return current_app.send_static_file("index.html")


@root.route("/pages/<path:path>")
def static_home_root(path: str):
    return current_app.send_static_file("index.html")


@root.route("/css/<path:path>")
def static_css(path: str):
    return send_from_directory(os.path.join(STATIC_FOLDER, "css"), path)


@root.route("/js/<path:path>")
def static_js(path: str):
    return send_from_directory(os.path.join(STATIC_FOLDER, "js"), path)

@root.route("/favicon.ico")
def favicon():
    return "", 204

# ------------------------------------------------------------------
# Server Entrypoint (Called only from sd_server.main)
# ------------------------------------------------------------------
def _start(
    storage_method,
    host: str,
    port: int,
    testing: bool = False,
    cors_origins: Optional[List[str]] = None,
    custom_static: Optional[Dict[str, str]] = None,
) -> None:
    if platform.system() == "Windows":
        is_file_corrupted, file_name = is_valid_keyring_file()
        if is_file_corrupted and file_name:
            logger.info("%s was invalid, so it was deleted.", file_name)
            os.unlink(file_name)

    app = AWFlask(
        host=host,
        testing=testing,
        storage_method=storage_method,
        cors_origins=cors_origins,
        custom_static=custom_static,
    )
    app.debug = testing

    server = None
    try:
        # When port=0, the OS binds a free ephemeral port immediately
        server = make_server(
            host=host,
            port=port,
            app=app,
            threaded=True,
            request_handler=FlaskLogHandler,
        )
        assigned_port = server.socket.getsockname()[1]
        app.config["PORT"] = assigned_port

        _write_runtime_port(assigned_port)
        logger.info("sd-server listening on http://%s:%d", host, assigned_port)

        server.serve_forever()
    except OSError as exc:
        logger.exception("Failed to start sd-server: %s", exc)
        raise
    finally:
        _remove_runtime_port()
        if server is not None:
            server.server_close()