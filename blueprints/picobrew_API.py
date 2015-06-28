from flask import *
from werkzeug import secure_filename

picobrew_api = Blueprint("picobrew_api", __name__)

@picobrew_api.route("/API/SyncUser")
def initialize():
    print request.args
    return "\r\n##"
