import json
import logging
import re
import time
import uuid
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, abort
from marshmallow import validate
from webargs import fields
from webargs.flaskparser import use_kwargs

from picobrew_server.blueprints.frontend import get_recipes
from picobrew_server.utils.constants import LOCAL_USER, MACHINE_PATH, SESSION_ERROR_PATH, SESSION_PATH, SYSTEM_USER

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
    # Separate event files retain repeated reports without changing recovery data.
    save_api_record(
        SESSION_ERROR_PATH,
        uuid.uuid4().hex,
        {
            "machine_id": machine,
            "session_id": session,
            "errorcode": errorcode,
            "reported_at": datetime.now(timezone.utc).isoformat(),
        },
    )
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
        return create_new_session(recipe)
    if session is not None:
        return log_to_session(session, code, data, step)
    abort(500)


def create_new_session(recipe_id: str) -> str:
    session_id = uuid.uuid4().hex[:32]

    recipe_name = next((r.name for r in get_recipes() if r.id == recipe_id), None)

    session_data = {
        "date": time.strftime("%x"),
        "recipe_id": recipe_id,
        "recipe_name": recipe_name,
        "session_id": session_id,
        "steps": [],
    }

    try:
        session_directory = Path(SESSION_PATH)
        session_directory.mkdir(exist_ok=True)

        with session_directory.joinpath(f"{session_id}.json").open("w") as out_file:
            json.dump(session_data, out_file, indent=2)

    except OSError as error:
        logger.error("Could not create new session storage file. %s", error)
        return "##"

    return f"#{session_id}#"


def log_to_session(session_id: str, code: str, data: str | None, step: str | None) -> str:
    code_int = int(code)

    try:
        session_directory = Path(SESSION_PATH)
        session_directory.mkdir(exist_ok=True)

        with session_directory.joinpath(f"{session_id}.json").open("r") as in_file:
            session_data = json.load(in_file)

        if code_int == 1:
            # new program step e.g. "Heating"
            session_data["steps"].append({"name": data, "temperatures": {}})

        elif code_int == 2:
            # temperature data for current step
            temps = re.findall(r"/([0-9]+)", data or "")
            current_time = time.strftime("%X")
            session_data["steps"][-1]["temperatures"][current_time] = temps
            session_data["machine_state"] = step

        elif code_int == 3:
            # end session
            session_data["steps"].append({"name": "Session Ended"})

        with session_directory.joinpath(f"{session_id}.json").open("w") as out_file:
            json.dump(session_data, out_file, indent=2)

    except OSError as error:
        logger.error("Couldn't save heating log to file. %s", error)

    return ""


# ----------- SESSION RECOVERY -----------
@picobrew_api.route("/API/recoversession")
@use_kwargs(
    {"session": fields.Str(required=True), "code": fields.Int(required=True)},
    location="query",
)
def parse_session_recovery_request(session: str, code: int) -> str:
    try:
        with Path(SESSION_PATH).joinpath(f"{session}.json").open("r") as in_file:
            session_data = json.load(in_file)

        if code == 0:
            matching = [r for r in get_recipes() if r.id == session_data["recipe_id"]]
            if not matching:
                logger.error("Unable to resume session %s: recipe_id not found", session)
                abort(500)
            return f"#{matching[0].serialize()}|!#"

        if code == 1:
            return f"#{session_data['machine_state']}#"

    except OSError as error:
        logger.error("Unable to resume session %s. %s", session, error)
        abort(500)

    abort(500)
