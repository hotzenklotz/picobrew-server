import logging
import os
from pathlib import Path

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

from picobrew_server.beerxml.picobrew_parser import PicoBrewRecipe, PicoBrewRecipeParser
from picobrew_server.utils.constants import ALLOWED_FILE_EXTENSIONS

logger = logging.getLogger()
frontend = Blueprint("frontend", __name__)


# -------- Routes --------
@frontend.route("/")
def index():
    return render_template("index.html")


@frontend.route("/recipes")
def render_recipes():
    return render_template("recipes.html", recipes=get_recipes())


def get_recipes(recipe_path: str = "recipes"):

    files = [
        filename
        for filename in Path(recipe_path).glob("**/*")
        if filename.suffix in ALLOWED_FILE_EXTENSIONS
    ]

    recipes = [get_recipe(filename) for filename in files]
    recipes = [y for x in recipes for y in x]  # flatten

    return recipes


def get_recipe(filename: Path) -> list[PicoBrewRecipe]:
    try:
        parser = PicoBrewRecipeParser()
        return parser.parse(filename)

    # pylint: disable=broad-except
    except Exception as error:
        logger.error("Failed to parse recipe %s. %s", filename, error)
        return []


@frontend.route("/upload", methods=["POST"])
def upload_recipe():

    redirect_url = ".index"
    for file in request.files.getlist("recipes"):
        file_directory = Path("recipes")
        file_directory.mkdir(exist_ok=True)

        filename = file_directory.joinpath(secure_filename(file.filename))

        if filename.suffix in ALLOWED_FILE_EXTENSIONS:
            file.save(filename)
            redirect_url = ".validate"
            session["recipe_file"] = str(filename)
        else:
            flash(f"Invalid BeerXML file <{file.filename}>.")

    return redirect(url_for(redirect_url))


@frontend.route("/validate")
def validate():

    filename = Path(session["recipe_file"])
    recipe = get_recipe(filename)[0]
    return render_template("validate.html", recipe=recipe)


@frontend.route("/submit_eula", methods=["POST"])
def submit_eula():

    redirect_url = ".render_recipes"
    form_data = request.form

    if not form_data.getlist("accept_eula") or form_data.getlist("action") == "cancel":
        file = session["recipe_file"]
        os.remove(file)
        redirect_url = ".index"

    return redirect(url_for(redirect_url))


# -------- Template Utility --------
@frontend.context_processor
def utility_processor():
    def format_weight(amount, _unit="kg"):
        if amount < 1.0:
            format_string = "{:.0f}{}".format(amount * 1000, "g")
        else:
            format_string = "{:.2f}{}".format(amount, "kg")
        return format_string

    def format_time(time):
        if time < 24 * 60:
            format_string = "{:.0f}{}".format(time, "min")
        else:
            format_string = "{:.0f}{}".format(time / (24 * 60), "days")
        return format_string

    def format_volume(volume, unit="L"):
        return f"{volume:.2f}{unit}"

    def format_float(value, trailing_numbers):
        return "{0:.{1}f}".format(value, trailing_numbers)

    return dict(
        format_weight=format_weight,
        format_time=format_time,
        format_volume=format_volume,
        format_float=format_float,
    )
