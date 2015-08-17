from flask import *
from webargs import Arg
from webargs.flaskparser import use_kwargs, FlaskParser
from frontend import get_recipes


SYSTEM_USER = "00000000000000000000000000000000"
arg_parser = FlaskParser()

picobrew_api = Blueprint("picobrew_api", __name__)

# Unfortunately the PicoBrew API ony consist of three overloaded routes.

# ----------- RECIPES -----------
@picobrew_api.route("/API/SyncUser")
@use_kwargs({"user": Arg(str), "machine": Arg(str)})
def parse_recipe_request(user, machine):

    if user == SYSTEM_USER:
        return getCleaningRecipes()
    else:
        if machine:
            return getAllRecipes()

    # default response
    return "\r\n##"


def getCleaningRecipes():
    return "cleaning"


def getAllRecipes():

    recipes = map(lambda recipe: recipe.serialize(), get_recipes())
    recipes = "|\n".join(recipes)

    return "#{0}|#".format(recipes)


# ----------- SESSION LOGGING -----------
@picobrew_api.route("/API/LogSession")
@use_kwargs({"session": Arg(str), "recipe": Arg(str)})
def parse_session_request(session, recipe):

    if recipe:
        args = arg_parser.parse({"user": Arg(str), "firm": Arg(str), "machine": Arg(str)})
        return create_new_session(recipe, args)

    if session:
        args = arg_parser.parse({"data": Arg(str), "state": Arg(str), "step": Arg(int), "code": Arg(int)})
        return log_to_session(session, args)

    # default fallthrough
    abort()


def create_new_session(recipeId, args):
    raise NotImplementedError()
    # return sessionID


def log_to_session(sessionId, args):
    raise NotImplementedError()
    # return ""

# ----------- SESSION RECOVERY -----------
@picobrew_api.route("/API/recoversession")
@use_kwargs({"session": Arg(str), "code": Arg(int)})
def parse_session_recovery_request(session, code):

    if code == 0:
        raise NotImplementedError()
        # return recipe

    elif code == 1:
        raise NotImplementedError()
        # return machine params

    # default fallthrough
    abort()
