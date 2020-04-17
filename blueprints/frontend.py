import os
import logging
import flask

from pathlib import Path, PosixPath
from typing import Text, List
from functools import reduce

from flask import Blueprint, request, flash, redirect, url_for, render_template, session
from werkzeug.utils import secure_filename
from beerxml.picobrew_parser import PicoBrewRecipeParser, PicoBrewRecipe

from utils.constants import ALLOWED_FILE_EXTENSIONS

logger = logging.getLogger()
frontend = Blueprint("frontend", __name__)

# -------- Routes --------
@frontend.route("/")
def index():
    return render_template("index.html")

@frontend.route("/recipes")
def recipes():
    return render_template("recipes.html", recipes=get_recipes())

def get_recipes(recipe_path: Text = "recipes"):

    path = Path("recipes")
    files = [filename for filename in Path("recipes").glob("**/*") if filename.suffix in ALLOWED_FILE_EXTENSIONS]
    
    recipes = [get_recipe(filename) for filename in files]
    recipes = reduce(lambda x,y: x+y, recipes) # flatten

    return recipes

def get_recipe(filename: PosixPath) -> List[PicoBrewRecipe]:
    try:
        parser = PicoBrewRecipeParser()
        return parser.parse(filename)

    except Exception as e:
        logger.error(f"Failed to parse recipe {filename}. {e}")
        return []

@frontend.route("/upload", methods=["POST"])
def uploadRecipe():

    redirect_url = ".index"
    for file in request.files.getlist("recipes"):

        filename = Path().joinpath("recipes", secure_filename(file.filename))
    
        if filename.suffix in ALLOWED_FILE_EXTENSIONS:
            file.save(filename)
            redirect_url = ".validate"
            session["recipe_file"] = str(filename)
        else:
            flash("Invalid BeerXML file <%s>." % file.filename)

    return redirect(url_for(redirect_url))


@frontend.route("/validate")
def validate():

    filename = Path(session["recipe_file"])
    recipe = get_recipe(filename)[0]
    return render_template("validate.html", recipe=recipe)

@frontend.route("/validate_recipe", methods=["POST"])
def validate_recipe():

    redirect_url = ".recipes"
    form_data = request.form

    if not form_data.getlist("accept_eula") or form_data.getlist("action") == "cancel":
        file = session["recipe_file"]
        os.remove(file)
        redirect_url = ".index"

    return redirect(url_for(redirect_url))

# -------- Template Utility --------
@frontend.context_processor
def utility_processor():

    def format_weight(amount, unit="kg"):
        if amount < 1.0:
            format = "{0:.0f}{1}".format(amount * 1000, "g")
        else:
            format = "{0:.2f}{1}".format(amount, "kg")
        return format

    def format_time(time):
        if time < 24 * 60:
            format = "{0:.0f}{1}".format(time, "min")
        else:
            format  = "{0:.0f}{1}".format(time / (24 * 60), "days")
        return format

    def format_volume(volume, unit="l"):
        return "{0:.2f}{1}".format(volume, unit)

    def format_float(value, trailing_numbers):
        return "{0:.{1}f}".format(value, trailing_numbers)

    return dict(
        format_weight=format_weight,
        format_time=format_time,
        format_volume=format_volume,
        format_float=format_float
    )