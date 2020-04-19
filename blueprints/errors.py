from flask import Blueprint, render_template

errors = Blueprint("errors", __name__)

# -------- Routes --------
@errors.app_errorhandler(404)
def error_404(_error):
    return render_template("404.html"), 404


@errors.app_errorhandler(500)
def error_500(_error):
    return render_template("500.html"), 500
