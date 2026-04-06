import logging
import os
from collections.abc import Callable
from pathlib import Path

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename
from werkzeug.wrappers import Response

from picobrew_server.beerxml.picobrew_parser import PicoBrewRecipe, PicoBrewRecipeParser
from picobrew_server.utils.constants import ALLOWED_FILE_EXTENSIONS

logger = logging.getLogger(__name__)
frontend = Blueprint("frontend", __name__)


# -------- Routes --------
@frontend.route("/")
def index() -> str:
    return render_template("index.html")


@frontend.route("/recipes")
def render_recipes() -> str:
    return render_template("recipes.html", recipes=get_recipes())


def get_recipes(recipe_path: str = "recipes") -> list[PicoBrewRecipe]:
    files = [filename for filename in Path(recipe_path).glob("**/*") if filename.suffix in ALLOWED_FILE_EXTENSIONS]

    recipes = [get_recipe(filename) for filename in files]
    return [y for x in recipes for y in x]  # flatten


def get_recipe(filename: Path) -> list[PicoBrewRecipe]:
    try:
        parser = PicoBrewRecipeParser()
        return parser.parse(filename)

    except Exception as error:
        logger.error("Failed to parse recipe %s. %s", filename, error)
        return []


@frontend.route("/upload", methods=["POST"])
def upload_recipe() -> Response:
    redirect_url = ".index"
    for file in request.files.getlist("recipes"):
        if not file.filename:
            continue

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
def validate() -> str:
    filename = Path(session["recipe_file"])
    recipe = get_recipe(filename)[0]
    return render_template("validate.html", recipe=recipe)


@frontend.route("/submit_eula", methods=["POST"])
def submit_eula() -> Response:
    redirect_url = ".render_recipes"
    form_data = request.form

    if not form_data.getlist("accept_eula") or form_data.getlist("action") == "cancel":
        os.remove(session["recipe_file"])
        redirect_url = ".index"

    return redirect(url_for(redirect_url))


# -------- Template Utility --------
@frontend.context_processor
def utility_processor() -> dict[str, Callable[..., str]]:
    def format_weight(amount: float, _unit: str = "kg") -> str:
        if amount < 1.0:
            return "{:.0f}{}".format(amount * 1000, "g")
        return "{:.2f}{}".format(amount, "kg")

    def format_time(time: float) -> str:
        if time < 24 * 60:
            return "{:.0f}{}".format(time, "min")
        return "{:.0f}{}".format(time / (24 * 60), "days")

    def format_volume(volume: float, unit: str = "L") -> str:
        return f"{volume:.2f}{unit}"

    def format_float(value: float, trailing_numbers: int) -> str:
        return "{0:.{1}f}".format(value, trailing_numbers)

    return dict(
        format_weight=format_weight,
        format_time=format_time,
        format_volume=format_volume,
        format_float=format_float,
    )
