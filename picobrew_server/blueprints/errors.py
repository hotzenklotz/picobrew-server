from flask import Blueprint, render_template, request

errors = Blueprint("errors", __name__)


def machine_error(status: int, message: str) -> tuple[str, int, dict[str, str]] | None:
    # The machine treats the text after the first '#' as a payload, and the HTML
    # error pages contain '#'. Answer machine API paths in plain text instead.
    if request.path.startswith("/API/"):
        return f"{status} {message}\n", status, {"Content-Type": "text/plain; charset=utf-8"}
    return None


# -------- Routes --------
@errors.app_errorhandler(404)
def error_404(_error):
    return machine_error(404, "Not Found") or (render_template("404.html"), 404)


@errors.app_errorhandler(500)
def error_500(_error):
    return machine_error(500, "Internal Server Error") or (render_template("500.html"), 500)
