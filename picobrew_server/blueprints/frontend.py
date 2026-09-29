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
def to_float(value: float | str | None) -> float | None:
    # BeerXML fields are lenient: a non-numeric value in the file arrives here as a string
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


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

    def format_float(value: float | str | None, trailing_numbers: int) -> str:
        number = to_float(value)
        if number is None:
            return "n/a"
        return "{0:.{1}f}".format(number, trailing_numbers)

    # Standard SRM to hex color mapping (https://en.wikipedia.org/wiki/Standard_Reference_Method)
    SRM_COLORS = [
        "#FFE699",
        "#FFD878",
        "#FFCA5A",
        "#FFBF42",
        "#FBB123",
        "#F8A600",
        "#F39C00",
        "#EA8F00",
        "#E58500",
        "#DE7C00",
        "#D77200",
        "#CF6900",
        "#CB6200",
        "#C35900",
        "#BB5100",
        "#B54C00",
        "#B04500",
        "#A63E00",
        "#A13700",
        "#9B3200",
        "#952D00",
        "#8E2900",
        "#882300",
        "#821E00",
        "#7B1A00",
        "#771900",
        "#701400",
        "#6A0E00",
        "#660D00",
        "#5E0B00",
        "#5A0A02",
        "#600903",
        "#520907",
        "#4C0505",
        "#470606",
        "#440607",
        "#3F0708",
        "#3B0607",
        "#3A070B",
        "#36080A",
    ]

    def srm_color(srm: float | str | None) -> str:
        value = to_float(srm)
        if value is None:
            return SRM_COLORS[5]

        index = max(1, min(round(value), len(SRM_COLORS)))
        return SRM_COLORS[index - 1]

    return dict(
        format_weight=format_weight,
        format_time=format_time,
        format_volume=format_volume,
        format_float=format_float,
        srm_color=srm_color,
    )
