import os
from flask import *
from os import path
from werkzeug import secure_filename
from beerxml import parser as BeerXmlParser

frontend = Blueprint("frontend", __name__)
FILE_EXTENSIONS = ["xml", "beerxml"]

@frontend.route("/")
def index():
    return render_template("index.html")

@frontend.route("/recipes")
def recipes():

    files = filter(filter_by_extensions , os.listdir("recipes"))
    files = [path.join("recipes", filename) for filename in files]
    recipes = []
    for file in files:
        recipes += BeerXmlParser.parse_beerxml(file)

    return render_template("recipes.html", recipes=recipes)


@frontend.route("/upload", methods=["POST"])
def uploadVideo():

    def isAllowed(filename):
        return len(filter_by_extensions(filename)) > 0

    redirect_page = ".index"
    print request.files

    for file in request.files.getlist("recipes"):
      print file.filename, isAllowed(file.filename)
      if isAllowed(file.filename):
        filename = secure_filename(file.filename)
        file.save(path.join("recipes", filename))
        redirect_page = ".recipes"
      else:
        flash("Invalid BeerXML file <%s>." % file.filename)

    return redirect(url_for(redirect_page))

# Utility
def filter_by_extensions(filename):
    return filter(lambda ext: ext in filename, ["xml", "beerxml"])

# Template Utility
@frontend.context_processor
def utility_processor():

    def format_weight(amount, unit="kg"):
        return "{0:.2f}{1}".format(amount, unit)

    def format_time(time):
        if time < 24 * 60:
            format = "{0:.0f}{1}".format(time, "min")
        else:
            format  = "{0:.0f}{1}".format(time / (24 * 60), "days")
        return format

    def format_volume(volume, unit="l"):
        return "{0:.2f}{1}".format(volume, unit)

    return dict(
        format_weight=format_weight,
        format_time=format_time,
        format_volume=format_volume
    )