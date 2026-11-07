import csv
import io
from datetime import datetime, timedelta
from typing import Any

from flask import Blueprint, abort, get_template_attribute, jsonify, render_template, request
from markupsafe import Markup
from werkzeug.wrappers import Response

from picobrew_server.session_store import SENSOR_INDEXES, BrewSessionStore, from_iso, get_store
from picobrew_server.utils.constants import SENSOR_LABELS, SESSION_ERROR_LABELS, TEMPERATURE_UNIT

brew_sessions = Blueprint("brew_sessions", __name__)

SESSION_KINDS = {"all": "All sessions", "brew": "Brews", "cleaning": "Cleaning & rinse"}
POLL_SECONDS = 10
# Keep checking an interrupted session, slower, since the machine can still recover and resume it.
INTERRUPTED_POLL_SECONDS = 60
# Server-side fallbacks for the formats static/js/local-time.js renders in the browser's time zone.
TIME_FORMATS = {"datetime": "%a %d %b %Y, %H:%M", "time": "%H:%M", "time-seconds": "%H:%M:%S"}


@brew_sessions.route("/sessions")
def history() -> str:
    """List every brew and cleaning session, newest first, with running sessions highlighted."""
    kind = request.args.get("kind", "all")
    if kind not in SESSION_KINDS:
        kind = "all"
    sessions = get_store().list_sessions()
    counts = {key: sum(1 for s in sessions if key == "all" or s["kind"] == key) for key in SESSION_KINDS}
    active = [s for s in sessions if s["status"] == "in_progress"]
    shown = [s for s in sessions if kind == "all" or s["kind"] == kind]
    return render_template(
        "sessions.html", sessions=shown, active=active, kind=kind, kinds=SESSION_KINDS, counts=counts
    )


@brew_sessions.route("/sessions/<session_id>")
def detail(session_id: str) -> str:
    """Show the temperature chart, steps and error reports for one session."""
    store = get_store()
    session = store.get_session(session_id) or abort(404)
    steps = store.get_steps(session_id)
    errors = store.get_errors(session_id)
    payload = session_payload(store, session, steps, errors, after_id=0)
    return render_template("session_detail.html", session=session, steps=steps, errors=errors, payload=payload)


@brew_sessions.route("/sessions/<session_id>/data.json")
def data(session_id: str) -> Response:
    """Return readings after ``after`` plus the current summary, for live chart updates."""
    store = get_store()
    session = store.get_session(session_id) or abort(404)
    after_id = request.args.get("after", 0, type=int) or 0
    steps = store.get_steps(session_id)
    errors = store.get_errors(session_id)
    payload = session_payload(store, session, steps, errors, after_id=max(after_id, 0))
    payload["html"] = {
        "summary": get_template_attribute("_session_parts.html", "summary")(session),
        "steps": get_template_attribute("_session_parts.html", "steps_table")(steps),
        "errors": get_template_attribute("_session_parts.html", "error_notice")(errors),
        "status": get_template_attribute("_session_parts.html", "status_badge")(session),
    }
    response = jsonify(payload)
    response.cache_control.no_store = True
    return response


@brew_sessions.route("/sessions/<session_id>/readings.csv")
def readings_csv(session_id: str) -> Response:
    """Download every reading as CSV, labelled with step names, for spreadsheets or further analysis."""
    store = get_store()
    session = store.get_session(session_id) or abort(404)
    step_names = {step["id"]: step["name"] for step in store.get_steps(session_id)}
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    sensors = list(SENSOR_LABELS.items())
    writer.writerow(
        ["recorded_at_utc", "elapsed_seconds", "step", "state"]
        + [f"{label} ({TEMPERATURE_UNIT}, sensor {index})" for index, label in sensors]
    )
    for reading in store.get_readings(session_id):
        recorded = from_iso(reading["recorded_at"])
        assert recorded is not None
        writer.writerow(
            [
                reading["recorded_at"],
                round((recorded - session["started_at"]).total_seconds()),
                step_names.get(reading["step_id"], ""),
                "" if reading["state"] is None else reading["state"],
            ]
            + ["" if reading[f"sensor_{index}"] is None else reading[f"sensor_{index}"] for index, _ in sensors]
        )
    filename = f"brew-session-{session['started_at']:%Y-%m-%d}-{session_id[:8]}.csv"
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def epoch_ms(moment: datetime | None) -> int | None:
    return None if moment is None else round(moment.timestamp() * 1000)


def session_payload(
    store: BrewSessionStore,
    session: dict[str, Any],
    steps: list[dict[str, Any]],
    errors: list[dict[str, Any]],
    after_id: int,
) -> dict[str, Any]:
    """Build the chart data: columnar readings plus step boundaries and error markers."""
    readings = store.get_readings(session["id"], after_id)
    columns: dict[str, list[Any]] = {"id": [], "t": [], "step_id": []}
    columns.update({f"sensor_{i}": [] for i in SENSOR_INDEXES})
    for reading in readings:
        columns["id"].append(reading["id"])
        columns["t"].append(epoch_ms(from_iso(reading["recorded_at"])))
        columns["step_id"].append(reading["step_id"])
        for index in SENSOR_INDEXES:
            columns[f"sensor_{index}"].append(reading[f"sensor_{index}"])
    return {
        "session": {
            "id": session["id"],
            "status": session["status"],
            "started_at": epoch_ms(session["started_at"]),
            "ended_at": epoch_ms(session["ended_at"]),
            "last_seen_at": epoch_ms(session["last_seen_at"]),
            "current_step": session["current_step"],
        },
        "steps": [
            {"id": step["id"], "name": step["name"], "started_at": epoch_ms(step["started_at"])} for step in steps
        ],
        "errors": [
            {
                "code": error["errorcode"],
                "label": error_label(error["errorcode"]),
                "reported_at": epoch_ms(error["reported_at"]),
            }
            for error in errors
        ],
        "sensors": [
            {"key": f"sensor_{index}", "index": index, "label": label} for index, label in SENSOR_LABELS.items()
        ],
        "unit": TEMPERATURE_UNIT,
        "readings": columns,
        "last_id": columns["id"][-1] if readings else after_id,
        "poll_seconds": {"in_progress": POLL_SECONDS, "interrupted": INTERRUPTED_POLL_SECONDS}.get(session["status"]),
    }


# -------- Template Utility --------
@brew_sessions.app_template_filter("local_datetime")
def local_datetime(moment: datetime | None, style: str = "datetime") -> Markup | str:
    """Render a ``<time>`` that the browser shows in its own time zone, with server-local text as fallback."""
    if moment is None:
        return "—"
    return Markup('<time datetime="{}" data-format="{}">{}</time>').format(
        moment.isoformat(timespec="seconds"), style, moment.astimezone().strftime(TIME_FORMATS[style])
    )


@brew_sessions.app_template_filter("duration")
def format_duration(value: timedelta | None) -> str:
    """Format a duration as ``2 h 05 min`` or ``12 min``."""
    if value is None:
        return "—"
    minutes = int(value.total_seconds() // 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes:02d} min" if hours else f"{minutes} min"


@brew_sessions.app_template_global()
def temperature(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}{TEMPERATURE_UNIT}"


@brew_sessions.app_template_global()
def error_label(code: int) -> str:
    return SESSION_ERROR_LABELS.get(code, f"Error {code}")


@brew_sessions.app_template_global()
def sensor_labels() -> dict[int, str]:
    return SENSOR_LABELS
