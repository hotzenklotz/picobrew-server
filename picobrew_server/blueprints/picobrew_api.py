import json
import logging
import re
import time
import uuid
from pathlib import Path

from flask import Blueprint, abort, request
from webargs import fields
from webargs.flaskparser import parser, use_kwargs

from picobrew_server.blueprints.frontend import get_recipe, get_recipes
from picobrew_server.utils.constants import SESSION_PATH, SYSTEM_USER

picobrew_api = Blueprint("picobrew_api", __name__)
logger = logging.getLogger()

# Unfortunately the PicoBrew API ony consist of three overloaded routes.


# ----------- RECIPES -----------
@picobrew_api.route("/API/SyncUser")
@picobrew_api.route("/API/SyncUSer")
@use_kwargs(
    {"user": fields.Str(required=True), "machine": fields.Str(required=True)},
    location="querystring",
)
def parse_recipe_request(user: str, machine: str):
    if user == SYSTEM_USER:
        return get_cleaning_recipes()
    if machine != "":
        return get_picobrew_recipes()

    # default response
    return "\r\n##"


@picobrew_api.route("/API/checksync")
@use_kwargs({"user": fields.Str(required=True)}, location="querystring")
def check_sync(user):
    return "\r\n#!#"


def get_cleaning_recipes():
    return (
        "#Cleaning v1/7f489e3740f848519558c41a036fe2cb"
        "/Heat Water,152,0,0,0/Clean Mash,152,15,1,5/Heat to Temp,152,0,0,0"
        "/Adjunct,152,3,2,1/Adjunct,152,2,3,1/Adjunct,152,2,4,1/Adjunct,152,2,5,1"
        "/Heat to Temp,207,0,0,0/Clean Mash,207,10,1,0/Clean Mash,207,2,1,0"
        "/Clean Adjunct,207,2,2,0/Chill,120,10,0,2"
        "/|Rinse v3/0160275741134b148eff90acdd5e462f/Rinse,0,2,0,5/|#"
    )


def get_picobrew_recipes():
    all_recipes = get_recipes()

    # only send recipes with valid brewing instructions "steps" to the machine
    recipes = [recipe.serialize() for recipe in all_recipes if len(recipe.steps) > 0]
    recipes = "|".join(recipes)

    return f"#{recipes}|#"


# ----------- SESSION LOGGING -----------
@picobrew_api.route("/API/LogSession")
@picobrew_api.route("/API/logSession")
@picobrew_api.route("/API/logsession")
def parse_start_new_session():
    args = parser.parse(
        {
            "recipe": fields.Str(),
            "session": fields.Str(),
            "user": fields.Str(),
            "code": fields.Str(required=True),
            "firm": fields.Str(),
            "machine": fields.Str(),
            "data": fields.Str(),
            "state": fields.Str(),
            "step": fields.Str(),
        },
        request,
        location="querystring",
    )

    if "recipe" in args:
        return create_new_session(args["recipe"], args)

    if "session" in args:
        return log_to_session(args["session"], args)

    # default fallthrough
    abort(500)


def create_new_session(recipe_id: str, _args) -> str:
    session_id = uuid.uuid4().hex[:32]
    session_file = f"{session_id}.json"

    recipe_name = None

    for recipe in get_recipes():
        if recipe.id == recipe_id:
            recipe_name = recipe.name

    session_data = {
        "date": time.strftime("%x"),
        "recipe_id": recipe_id,
        "recipe_name": recipe_name,
        "session_id": session_id,
        "steps": [],
    }

    try:
        session_directory = Path(SESSION_PATH)
        if not session_directory.exists():
            session_directory.mkdir(exist_ok=True)

        with session_directory.joinpath(session_file).open("w") as out_file:
            json.dump(session_data, out_file, indent=2)

    except OSError as error:
        logger.error("Could create new session storage file. %s", error)
        return "##"

    return f"#{session_id}#"


def log_to_session(session_id: str, args) -> str:
    session_file = f"{session_id}.json"
    code = int(args["code"])

    try:
        session_directory = Path(SESSION_PATH)
        if not session_directory.exists():
            session_directory.mkdir(exist_ok=True)

        with session_directory.joinpath(session_file).open("r") as in_file:
            session = json.load(in_file)

        if code == 1:
            # new program step e.g. "Heating"

            session_step = {"name": args["data"], "temperatures": {}}
            session["steps"].append(session_step)

        elif code == 2:
            # temperature data for current step

            temps = re.findall(r"/([0-9]+)", args["data"])
            current_time = time.strftime("%X")

            session_step = session["steps"][-1]
            session_step["temperatures"][current_time] = temps

            session["machine_state"] = args["step"]

        elif code == 3:
            # end session

            session["steps"].append({"name": "Session Ended"})

        with session_directory.joinpath(session_file).open("w") as out_file:
            json.dump(session, out_file, indent=2)

    except OSError as error:
        logging.error("Couldn't save heating log to file. %s", error)

    return ""


# ----------- SESSION RECOVERY -----------
@picobrew_api.route("/API/recoversession")
@use_kwargs(
    {"session": fields.Str(required=True), "code": fields.Int(required=True)},
    location="querystring",
)
def parse_session_recovery_request(session, code) -> str:
    try:
        session_file = f"{session}.json"

        with Path(SESSION_PATH).joinpath(session_file).open("r") as in_file:
            session = json.load(in_file)

        if code == 0:
            # return a recipe — look up by stored recipe_id (filename is not saved in session)
            matching = [r for r in get_recipes() if r.id == session["recipe_id"]]
            if not matching:
                logging.error("Unable to resume session %s: recipe_id not found", session)
                abort(500)
            return f"#{matching[0].serialize()}|!#"

        elif code == 1:
            # return machine params
            return f"#{session['machine_state']}#"

    except OSError as error:
        logging.error("Unable to resume session %s. %s", session, error)
        abort(500)

    # default fallthrough
    abort(500)
