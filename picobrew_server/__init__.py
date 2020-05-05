# System imports
from flask_cors import CORS
from flask import Flask
from picobrew_server.blueprints import frontend, picobrew_api, errors

app = Flask(__name__)
CORS(app)

app.config.update(
    SECRET_KEY="asassdfs", CORS_HEADERS="Content-Type", UPLOAD_FOLDER="recipes"
)

# ----- Routes ----------
app.register_blueprint(frontend.frontend)
app.register_blueprint(errors.errors)
app.register_blueprint(picobrew_api.picobrew_api)

