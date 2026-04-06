import os
import secrets

from flask import Flask
from flask_cors import CORS

from picobrew_server.blueprints import errors, frontend, picobrew_api


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)

    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", secrets.token_hex(32)),
        CORS_HEADERS="Content-Type",
        UPLOAD_FOLDER="recipes",
    )

    if config:
        app.config.update(config)

    CORS(app)

    app.register_blueprint(frontend.frontend)
    app.register_blueprint(errors.errors)
    app.register_blueprint(picobrew_api.picobrew_api)

    return app
