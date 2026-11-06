import json
import logging
import re
import sqlite3
import uuid
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, abort
from marshmallow import validate
from webargs import fields
from webargs.flaskparser import use_kwargs

from picobrew_server.blueprints.frontend import get_recipes
from picobrew_server.session_store import get_store, parse_int
from picobrew_server.utils.constants import CLEANING_PROGRAMS, LOCAL_USER, MACHINE_PATH, SYSTEM_USER

picobrew_api = Blueprint("picobrew_api", __name__)
logger = logging.getLogger(__name__)

# Firmware 1.1.14 uses eight route families, including three spellings of session logging.


# ----------- MACHINE SETUP -----------
@picobrew_api.route("/API/zymaticFirmwareCheck")
@use_kwargs(
    {
        "machine": fields.Str(required=True, validate=validate.Length(min=1)),
        "ver": fields.Int(required=True, validate=validate.Range(min=0)),
        "maj": fields.Int(required=True, validate=validate.Range(min=0)),
        "min": fields.Int(required=True, validate=validate.Range(min=0)),
    },
    location="query",
)
def check_firmware(machine: str, ver: int, maj: int, min: int) -> str:
    # This server does not distribute application firmware images.
    return "#F#"


@picobrew_api.route("/API/usersetup")
@use_kwargs(
    {
        "machine": fields.Str(required=True, validate=validate.Length(min=1)),
        "admin": fields.Int(required=True, validate=validate.OneOf([0])),
    },
    location="query",
)
def get_machine_accounts(machine: str, admin: int) -> str:
    # Every machine uses the same local recipe library. The firmware needs a
    # 32-character ID, a name of at most 20 characters, and a trailing record separator.
    return f"#{LOCAL_USER}/PicoBrew Server|#"


@picobrew_api.route("/API/firstSetup")
@use_kwargs(
    {
        "machine": fields.Str(required=True, validate=validate.Length(min=1)),
        "admin": fields.Int(required=True, validate=validate.OneOf([0])),
    },
    location="query",
)
def register_machine(machine: str, admin: int) -> str:
    machine_id, separator, sensor_list = machine.partition("|")
    if not machine_id or not separator:
        abort(422)

    sensors: dict[str, str] = {}
    for pair in sensor_list.split("/"):
        match = re.fullmatch(r"([^|/,]+),([1-4])", pair)
        if match is None or match[2] in sensors:
            abort(422)
        sensors[match[2]] = match[1]
    if set(sensors) != {"1", "2", "3", "4"}:
        abort(422)

    # Derive the filename rather than using a device-supplied identifier as a path.
    record_id = uuid.uuid5(uuid.NAMESPACE_URL, machine_id).hex
    save_api_record(
        MACHINE_PATH,
        record_id,
        {
            "machine_id": machine_id,
            "user_id": LOCAL_USER,
            "sensors": sensors,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return ""


def save_api_record(directory: str, record_id: str, record: dict[str, object]) -> None:
    record_directory = Path(directory)
    temporary_file = record_directory / f".{uuid.uuid4().hex}.tmp"
    try:
        record_directory.mkdir(parents=True, exist_ok=True)
        with temporary_file.open("x") as out_file:
            json.dump(record, out_file, indent=2)
        temporary_file.replace(record_directory / f"{record_id}.json")
    except OSError:
        logger.exception("Could not save API record in %s", record_directory)
        abort(500)
    finally:
        with suppress(OSError):
            temporary_file.unlink(missing_ok=True)


# ----------- SESSION ERRORS -----------
@picobrew_api.route("/API/sessionerror")
@use_kwargs(
    {
        "machine": fields.Str(required=True, validate=validate.Length(min=1)),
        "session": fields.Str(required=True),
        "errorcode": fields.Int(required=True, validate=validate.Range(min=0)),
    },
    location="query",
)
def report_session_error(machine: str, session: str, errorcode: int) -> str:
    # Error reports may arrive after a reset, before this server knows the session.
    # Each report is kept as its own event without changing recovery data.
    try:
        get_store().record_error(machine, session, errorcode)
    except (OSError, sqlite3.Error):
        logger.exception("Could not save session error report")
        abort(500)
    return ""


# ----------- RECIPES -----------
@picobrew_api.route("/API/SyncUser")
@picobrew_api.route("/API/SyncUSer")
@use_kwargs(
    {"user": fields.Str(required=True), "machine": fields.Str(required=True)},
    location="query",
)
def parse_recipe_request(user: str, machine: str) -> str:
    if user == SYSTEM_USER:
        return get_cleaning_recipes()
    if machine != "":
        return get_picobrew_recipes()

    # default response
    return "\r\n##"


@picobrew_api.route("/API/checksync")
@use_kwargs({"user": fields.Str(required=True)}, location="query")
def check_sync(user: str) -> str:
    return "\r\n#!#"


def get_cleaning_recipes() -> str:
    return (
        "#Cleaning v1/7f489e3740f848519558c41a036fe2cb"
        "/Heat Water,152,0,0,0/Clean Mash,152,15,1,5/Heat to Temp,152,0,0,0"
        "/Adjunct,152,3,2,1/Adjunct,152,2,3,1/Adjunct,152,2,4,1/Adjunct,152,2,5,1"
        "/Heat to Temp,207,0,0,0/Clean Mash,207,10,1,0/Clean Mash,207,2,1,0"
        "/Clean Adjunct,207,2,2,0/Chill,120,10,0,2"
        "/|Rinse v3/0160275741134b148eff90acdd5e462f/Rinse,0,2,0,5/|#"
    )


def get_picobrew_recipes() -> str:
    recipes = [r.serialize() for r in get_recipes() if len(r.steps) > 0]
    return f"#{'|'.join(recipes)}|#"


# ----------- SESSION LOGGING -----------
@picobrew_api.route("/API/LogSession")
@picobrew_api.route("/API/logSession")
@picobrew_api.route("/API/logsession")
@use_kwargs(
    {
        "recipe": fields.Str(load_default=None),
        "session": fields.Str(load_default=None),
        "code": fields.Str(required=True),
        "data": fields.Str(load_default=None),
        "step": fields.Str(load_default=None),
        "user": fields.Str(load_default=None),
        "firm": fields.Str(load_default=None),
        "machine": fields.Str(load_default=None),
        "state": fields.Str(load_default=None),
    },
    location="query",
)
def parse_session_request(
    code: str,
    recipe: str | None = None,
    session: str | None = None,
    data: str | None = None,
    step: str | None = None,
    user: str | None = None,
    firm: str | None = None,
    machine: str | None = None,
    state: str | None = None,
) -> str:
    if recipe is not None:
        return create_new_session(recipe, user, machine, firm)
    if session is not None:
        return log_to_session(session, code, data, step, parse_int(state))
    abort(500)


def create_new_session(recipe_id: str, user: str | None, machine: str | None, firmware: str | None) -> str:
    session_id = uuid.uuid4().hex
    is_cleaning = user == SYSTEM_USER or recipe_id in CLEANING_PROGRAMS
    recipe_name = CLEANING_PROGRAMS.get(recipe_id) or next((r.name for r in get_recipes() if r.id == recipe_id), None)

    try:
        get_store().create_session(
            session_id,
            recipe_id=recipe_id,
            recipe_name=recipe_name,
            kind="cleaning" if is_cleaning else "brew",
            user_id=user,
            machine_id=machine,
            firmware=firmware,
        )
    except (OSError, sqlite3.Error):
        logger.exception("Could not create brew session")
        return "##"

    return f"#{session_id}#"


def log_to_session(session_id: str, code: str, data: str | None, step: str | None, state: int | None) -> str:
    code_int = parse_int(code)
    try:
        store = get_store()
        if code_int == 1:
            # new program step, e.g. "Heating"
            found = store.record_step(session_id, data, state)
        elif code_int == 2:
            # temperature readings plus the recovery snapshot for the current step
            found = store.record_reading(session_id, data, step, state)
        elif code_int == 3:
            found = store.end_session(session_id)
        else:
            logger.warning("Ignoring session log with unknown code %r", code)
            return ""
        if not found:
            logger.warning("Ignoring log for unknown session %s", session_id)
    except (OSError, sqlite3.Error):
        # The firmware does not read an acknowledgment, so keep brewing even if logging fails.
        logger.exception("Could not save session log for %s", session_id)

    return ""


# ----------- SESSION RECOVERY -----------
@picobrew_api.route("/API/recoversession")
@use_kwargs(
    {"session": fields.Str(required=True), "code": fields.Int(required=True)},
    location="query",
)
def parse_session_recovery_request(session: str, code: int) -> str:
    try:
        session_data = get_store().resume_session(session)
    except (OSError, sqlite3.Error):
        logger.exception("Unable to resume session %s", session)
        abort(500)

    if session_data is None:
        logger.error("Unable to resume unknown session %s", session)
        abort(500)

    if code == 0:
        matching = [r for r in get_recipes() if r.id == session_data["recipe_id"]]
        if not matching:
            logger.error("Unable to resume session %s: recipe_id not found", session)
            abort(500)
        return f"#{matching[0].serialize()}|!#"

    if code == 1 and session_data["recovery_snapshot"] is not None:
        return f"#{session_data['recovery_snapshot']}#"

    abort(500)
