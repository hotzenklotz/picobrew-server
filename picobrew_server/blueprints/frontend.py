import logging
import re
import shutil
import uuid
from collections.abc import Callable
from pathlib import Path

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename
from werkzeug.wrappers import Response

from picobrew_server.beerxml.picobrew_parser import PicoBrewRecipe, PicoBrewRecipeParser
from picobrew_server.utils.constants import ALLOWED_FILE_EXTENSIONS

logger = logging.getLogger(__name__)
frontend = Blueprint("frontend", __name__)


# -------- Routes --------
@frontend.route("/")
def index() -> str:
    return render_recipes()


@frontend.route("/import")
def import_recipes() -> str:
    return render_template("index.html")


@frontend.route("/recipes")
def render_recipes() -> str:
    return render_template("recipes.html", recipes=get_recipes())


def get_recipes(recipe_path: str | None = None) -> list[PicoBrewRecipe]:
    directory = Path(recipe_path or current_app.config["UPLOAD_FOLDER"])
    files = [
        filename
        for filename in sorted(directory.glob("**/*"))
        if filename.is_file()
        and filename.suffix.lower() in ALLOWED_FILE_EXTENSIONS
        and not any(part.startswith(".") for part in filename.relative_to(directory).parts)
    ]

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
    discard_pending_import()
    directory = Path(current_app.config["UPLOAD_FOLDER"])
    import_id = uuid.uuid4().hex
    pending = directory / ".pending" / import_id
    pending.mkdir(parents=True)
    session["pending_import"] = import_id

    for file in request.files.getlist("recipes"):
        if not file.filename:
            continue

        name = secure_filename(file.filename)
        filename = pending / name
        if not name or filename.suffix.lower() not in ALLOWED_FILE_EXTENSIONS:
            flash(f"{file.filename}: choose a BeerXML file (.xml or .beerxml).", "danger")
            continue
        if (directory / name).exists() or filename.exists():
            flash(f"{name}: a file with this name already exists. Rename it to import a separate copy.", "warning")
            continue
        file.save(filename)
        if not get_recipe(filename):
            filename.unlink()
            flash(f"{name}: no readable recipes found. Check the BeerXML export and try again.", "danger")

    if any(pending.iterdir()):
        return redirect(url_for(".validate"))
    discard_pending_import()
    flash("No new recipes to review. Choose one or more BeerXML files.", "warning")
    return redirect(url_for(".import_recipes"))


def pending_import() -> Path | None:
    import_id = session.get("pending_import", "")
    if not isinstance(import_id, str) or not re.fullmatch(r"[0-9a-f]{32}", import_id):
        return None
    directory = Path(current_app.config["UPLOAD_FOLDER"]) / ".pending" / import_id
    return directory if directory.is_dir() else None


def discard_pending_import() -> None:
    directory = pending_import()
    if directory is not None:
        shutil.rmtree(directory)
    session.pop("pending_import", None)


@frontend.route("/validate")
def validate() -> str | Response:
    directory = pending_import()
    if directory is None:
        return redirect(url_for(".import_recipes"))
    recipes = [recipe for filename in sorted(directory.iterdir()) for recipe in get_recipe(filename)]
    if not recipes:
        discard_pending_import()
        flash("No readable recipes remain in this import. Please choose your files again.", "danger")
        return redirect(url_for(".import_recipes"))
    return render_template("validate.html", recipes=recipes)


@frontend.route("/submit_eula", methods=["POST"])
def submit_eula() -> Response:
    directory = pending_import()
    if directory is None:
        return redirect(url_for(".import_recipes"))
    if request.form.get("action") == "cancel":
        discard_pending_import()
        flash("Import cancelled. Your library has not changed.", "neutral")
        return redirect(url_for(".import_recipes"))
    if not request.form.get("accept_eula"):
        flash("Review the recipes and confirm the checkbox before adding them.", "warning")
        return redirect(url_for(".validate"))

    files = sorted(directory.iterdir())
    parsed_files = [get_recipe(filename) for filename in files]
    if not files or not all(parsed_files):
        flash("Some files could not be read. Cancel this import and choose your files again.", "danger")
        return redirect(url_for(".validate"))
    recipes = [recipe for batch in parsed_files for recipe in batch]
    added: list[Path] = []
    try:
        for filename in files:
            destination = Path(current_app.config["UPLOAD_FOLDER"]) / filename.name
            # Both paths are on the same filesystem. Linking publishes the complete
            # file atomically and refuses to overwrite an existing recipe.
            destination.hardlink_to(filename)
            added.append(destination)
    except OSError:
        for filename in added:
            filename.unlink()
        logger.exception("Could not complete recipe import")
        flash("Could not add these files. Check for duplicate filenames and try again.", "danger")
        return redirect(url_for(".validate"))

    discard_pending_import()
    count = len(recipes)
    available = sum(bool(recipe.steps) for recipe in recipes)
    flash(
        f"Added {count} recipe{'s' if count != 1 else ''} to your library. {available} available to your machine.",
        "success",
    )
    return redirect(url_for(".index"))


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
    def format_weight(amount: float | str | None, _unit: str = "kg") -> str:
        number = to_float(amount)
        if number is None:
            return "n/a"
        if number < 1.0:
            return "{:.0f}{}".format(number * 1000, "g")
        return "{:.2f}{}".format(number, "kg")

    def format_time(time: float | str | None) -> str:
        number = to_float(time)
        if number is None:
            return "n/a"
        if number < 24 * 60:
            return "{:.0f}{}".format(number, "min")
        return "{:.0f}{}".format(number / (24 * 60), "days")

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
