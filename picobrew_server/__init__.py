import os
import secrets

from flask import Flask
from flask_cors import CORS

from picobrew_server.blueprints import brew_sessions, errors, frontend, picobrew_api, programs
from picobrew_server.utils.constants import BREW_DATABASE, SESSION_PATH


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

    return app
