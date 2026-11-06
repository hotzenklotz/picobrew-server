from flask import Blueprint, render_template, request

errors = Blueprint("errors", __name__)


def plain_text_error(status: int, message: str) -> tuple[str, int, dict[str, str]]:
    """An error response the machine cannot mistake for a payload.

    The firmware skips everything up to the first '#' and parses the rest as a
    payload, and the HTML error pages contain '#'.
    """
    body = f"{status} {message.replace('#', '')}\n"
    return body, status, {"Content-Type": "text/plain; charset=utf-8"}


def machine_error(status: int, message: str) -> tuple[str, int, dict[str, str]] | None:
    # Errors raised before the API blueprint's own handler runs (e.g. unknown /API/ routes).
    if request.path.startswith("/API/"):
        return plain_text_error(status, message)
    return None


# -------- Routes --------
@errors.app_errorhandler(404)
def error_404(_error):
    return machine_error(404, "Not Found") or (render_template("404.html"), 404)


@errors.app_errorhandler(500)
def error_500(_error):
    return machine_error(500, "Internal Server Error") or (render_template("500.html"), 500)
