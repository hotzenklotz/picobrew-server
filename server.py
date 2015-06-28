# System imports
import sys, requests
from flask.ext.cors import CORS
from flask import *
from blueprints import frontend, picobrew_API

app = Flask(__name__)
CORS(app)

# ----- Routes ----------
app.register_blueprint(frontend.frontend)
app.register_blueprint(picobrew_API.picobrew_api)

if __name__ == "__main__":
    # Start the server
    app.config.update(
        DEBUG = True,
        SECRET_KEY = "asassdfs",
        CORS_HEADERS = "Content-Type",
        UPLOAD_FOLDER = "recipes"
    )

    # Start the Flask app
    app.run(port=9000)
