import flask

from flask import Blueprint, request, flash, redirect, url_for, render_template, session

errors = Blueprint("errors", __name__)

# -------- Routes --------
@errors.app_errorhandler(404)
def error_404(error):
    return render_template("404.html"), 404

@errors.app_errorhandler(500)
def error_500(error):
    return render_template("500.html"), 500
