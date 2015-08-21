import os
from flask import *
from os import path
from werkzeug import secure_filename
from beerxml.picobrew_parser import PicoBrewParser as BeerXMLParser

frontend = Blueprint("frontend", __name__)
FILE_EXTENSIONS = ["xml", "beerxml"]

# -------- Routes --------
@frontend.route("/")
def index():
    return render_template("index.html")

@frontend.route("/recipes")
def recipes():

    return render_template("recipes.html", recipes=get_recipes())

def get_recipes(recipe_path = "recipes"):

    files = filter(filter_by_extensions , os.listdir("recipes"))
    files = [path.join(recipe_path, filename) for filename in files]

    recipes = [get_recipe(file) for file in files]
    recipes = reduce(lambda x,y: x+y, recipes) # flatten dat shit

    return recipes

def get_recipe(file):

    parser = BeerXMLParser()
    return parser.parse(file)

@frontend.route("/upload", methods=["POST"])
def uploadVideo():

    def isAllowed(filename):
        return len(filter_by_extensions(filename)) > 0

    redirect_url = ".index"
    for file in request.files.getlist("recipes"):

      if isAllowed(file.filename):
        filename = path.join("recipes", secure_filename(file.filename))
        file.save(filename)
        redirect_url = ".validate"
        session["recipe_file"] = filename
      else:
        flash("Invalid BeerXML file <%s>." % file.filename)

    return redirect(url_for(redirect_url))


@frontend.route("/validate")
def validate():

    file = session["recipe_file"]
    recipe = get_recipe(file)[0]
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

# -------- Utility --------
def filter_by_extensions(filename):
    return filter(lambda ext: ext in filename, ["xml", "beerxml"])

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