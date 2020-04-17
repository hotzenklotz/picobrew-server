# System imports
from flask_cors import CORS
from flask import *
from blueprints import frontend, picobrew_API, errors

app = Flask(__name__)
CORS(app)

app.config.update(
    SECRET_KEY = "asassdfs",
    CORS_HEADERS = "Content-Type",
    UPLOAD_FOLDER = "recipes"
)

# ----- Routes ----------
app.register_blueprint(frontend.frontend)
app.register_blueprint(errors.errors)
app.register_blueprint(picobrew_API.picobrew_api)

if __name__ == "__main__":

    # Start the Flask app
    app.run(host="0.0.0.0", port=5000)
