from flask import *
from os import path
from werkzeug import secure_filename

frontend = Blueprint("frontend", __name__)

@frontend.route("/")
def index():
    return render_template("index.html")

@frontend.route("/recipes")
def recipes():
    return render_template("recipes.html")


@frontend.route("/upload", methods=["POST"])
def uploadVideo():

    def isAllowed(filename):
        return len(filter(lambda ext: ext in filename, ["xml", "beerxml"])) > 0

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
