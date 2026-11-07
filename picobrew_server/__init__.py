import logging
import os
import secrets
from pathlib import Path

from flask import Flask
from flask_cors import CORS

from picobrew_server.blueprints import brew_sessions, errors, frontend, picobrew_api, programs
from picobrew_server.session_store import BrewSessionStore
from picobrew_server.utils.constants import BREW_DATABASE, SESSION_PATH

logger = logging.getLogger(__name__)


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)

    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", secrets.token_hex(32)),
        CORS_HEADERS="Content-Type",
        UPLOAD_FOLDER="recipes",
        BREW_DATABASE=BREW_DATABASE,
        LEGACY_SESSION_PATH=SESSION_PATH,
    )

    if config:
        app.config.update(config)

    CORS(app)

    app.register_blueprint(frontend.frontend)
    app.register_blueprint(errors.errors)
    app.register_blueprint(picobrew_api.picobrew_api)
    app.register_blueprint(programs.programs)
    app.register_blueprint(brew_sessions.brew_sessions)

    import_legacy_sessions(app)
    return app


def import_legacy_sessions(app: Flask) -> None:
    """Import JSON logs from earlier versions once at startup, so no machine request has to wait for it."""
    legacy_path = app.config.get("LEGACY_SESSION_PATH")
    if not legacy_path:
        return
    try:
        BrewSessionStore(app.config["BREW_DATABASE"]).import_legacy_json(Path(legacy_path))
    except Exception:
        # Never keep the server from starting; files that were not imported are retried next start.
        logger.exception("Could not import legacy session logs from %s", legacy_path)
