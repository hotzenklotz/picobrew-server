import logging
import math
import secrets
from dataclasses import asdict
from pathlib import Path

from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.wrappers import Response

from picobrew_server.beerxml.picobrew_parser import PicoBrewRecipeParser
from picobrew_server.beerxml.picobrew_program_step import LOCATION_IDS, PicoBrewProgramStep
from picobrew_server.beerxml.picobrew_recipe import PicoBrewRecipe
from picobrew_server.beerxml.program_editor import ProgramConflictError, revision, save_program
from picobrew_server.beerxml.program_guidance import program_templates, program_warnings
from picobrew_server.blueprints.frontend import get_recipes, pending_import
from picobrew_server.utils.constants import ALLOWED_FILE_EXTENSIONS

logger = logging.getLogger(__name__)
programs = Blueprint("programs", __name__)
LOCATIONS = {
    "PassThrough": "Pass through",
    "Mash": "Mash",
    "Adjunct1": "Adjunct 1",
    "Adjunct2": "Adjunct 2",
    "Adjunct3": "Adjunct 3",
    "Adjunct4": "Adjunct 4",
    "Pause": "Pause / user action",
}


@programs.app_context_processor
def editor_utilities() -> dict:
    def program_url(recipe: PicoBrewRecipe, scope: str = "library") -> str:
        base = pending_import() if scope == "import" else Path(current_app.config["UPLOAD_FOLDER"])
        if base is None:
            return url_for("frontend.import_recipes")
        relative = Path(recipe.source_file).relative_to(base).as_posix()
        return url_for(
            "programs.edit_program",
            scope=scope,
            file=relative,
            recipe=recipe.source_index,
            batch=session.get("pending_import") if scope == "import" else None,
        )

    return {"program_url": program_url}


def resolve_target() -> tuple[Path, int, str]:
    scope = request.args.get("scope", "library")
    if scope == "import":
        base = pending_import()
        if base is None or request.args.get("batch") != session.get("pending_import"):
            abort(404)
    elif scope == "library":
        base = Path(current_app.config["UPLOAD_FOLDER"])
    else:
        abort(404)
    relative = Path(request.args.get("file", ""))
    if relative.is_absolute() or "\\" in str(relative) or any(part.startswith(".") for part in relative.parts):
        abort(404)
    path = base / relative
    if relative.suffix.lower() not in ALLOWED_FILE_EXTENSIONS or not path.is_file():
        abort(404)
    # Reject escaping paths and symlinks, including symlinked parent directories.
    if not path.resolve().is_relative_to(base.resolve()) or any(
        (base / Path(*relative.parts[:i])).is_symlink() for i in range(1, len(relative.parts) + 1)
    ):
        abort(404)
    try:
        index = int(request.args.get("recipe", "0"))
    except ValueError:
        abort(404)
    if index < 0:
        abort(404)
    return path, index, scope


def parse_steps(rows: list[dict[str, str]]) -> tuple[list[PicoBrewProgramStep], list[str]]:
    errors = []
    steps = []
    if not rows:
        return [], ["Add at least one step before saving the machine program."]
    for index, row in enumerate(rows, 1):
        name = row["name"].strip()
        if not name or any(character in name for character in ",/|#\r\n"):
            errors.append(f"Step {index}: enter a name without commas, slashes, pipes, #, or line breaks.")
        if row["location"] not in LOCATION_IDS:
            errors.append(f"Step {index}: choose a valid location.")
        numbers = {}
        for field, label in [("temp", "temperature"), ("time", "duration"), ("drain", "drain time")]:
            try:
                number = float(row[field])
                if not math.isfinite(number) or not number.is_integer() or number < 0:
                    raise ValueError
                if field == "temp" and number > 110:
                    raise ValueError
                numbers[field] = number
            except ValueError:
                requirement = "a whole number from 0 to 110°C" if field == "temp" else "a non-negative whole number"
                errors.append(f"Step {index}: {label} must be {requirement}.")
        if len(numbers) == 3 and name and row["location"] in LOCATION_IDS:
            steps.append(PicoBrewProgramStep(name=name, location=row["location"], **numbers))
    return steps, errors


@programs.route("/program", methods=["GET", "POST"])
def edit_program() -> str | Response | tuple[str, int]:
    path, index, scope = resolve_target()
    try:
        document = path.read_bytes()
        recipes = PicoBrewRecipeParser().parse(path)
    except Exception:
        logger.exception("Could not load machine program from %s", path)
        abort(422)
    if index >= len(recipes):
        abort(404)
    recipe = recipes[index]
    session.setdefault("program_csrf", secrets.token_hex(32))
    current_revision = revision(document)
    back_url = url_for("frontend.validate" if scope == "import" else "frontend.index")
    rows = [
        {
            field: ""
            if (value := getattr(step, field)) is None
            else (f"{value:g}" if isinstance(value, float) else str(value))
            for field in ["name", "temp", "time", "location", "drain"]
        }
        for step in recipe.steps
    ]
    errors: list[str] = []
    status = 200
    if request.method == "POST":
        if not secrets.compare_digest(request.form.get("csrf", "").encode(), session["program_csrf"].encode()):
            abort(400)
        columns = {
            field: request.form.getlist(f"step_{field}") for field in ["name", "temp", "time", "location", "drain"]
        }
        if len({len(values) for values in columns.values()}) != 1:
            abort(400)
        rows = [dict(zip(columns, values, strict=True)) for values in zip(*columns.values(), strict=True)]
        steps, errors = parse_steps(rows)
        current_revision = request.form.get("revision", "")
        if not errors:
            try:
                save_program(path, index, steps, current_revision)
            except ProgramConflictError as error:
                errors.append(str(error))
                status = 409
            except Exception:
                logger.exception("Could not save machine program to %s", path)
                errors.append("Could not save the machine program. Your file has not been changed. Please try again.")
                status = 500
            else:
                flash(
                    f"Saved machine program for {recipe.name or 'Untitled recipe'}."
                    + (" Review the updated steps before confirming the import." if scope == "import" else ""),
                    "success",
                )
                advisories = program_warnings(rows, recipe)
                if advisories:
                    flash(
                        f"Saved with {len(advisories)} advisory warning{'s' if len(advisories) != 1 else ''}. "
                        "You can review them in the machine program editor.",
                        "warning",
                    )
                return redirect(back_url)
        if status == 200:
            status = 422
    return render_template(
        "program_editor.html",
        recipe=recipe,
        rows=rows,
        locations=LOCATIONS,
        scope=scope,
        revision=current_revision,
        errors=errors,
        back_url=back_url,
        conflict=status == 409,
        templates=[asdict(template) for template in program_templates(recipe, get_recipes())],
        warnings=program_warnings(rows, recipe),
        check_url=url_for(
            "programs.check_program",
            scope=scope,
            file=request.args.get("file"),
            recipe=index,
            batch=request.args.get("batch") if scope == "import" else None,
        ),
    ), status


@programs.route("/program/check", methods=["POST"])
def check_program() -> Response:
    path, index, _ = resolve_target()
    data = request.get_json()
    if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
        abort(400)
    rows = data["rows"]
    fields = {"name", "temp", "time", "location", "drain"}
    if any(
        not isinstance(row, dict) or set(row) != fields or any(not isinstance(v, str) for v in row.values())
        for row in rows
    ):
        abort(400)
    recipes = PicoBrewRecipeParser().parse(path)
    if index >= len(recipes):
        abort(404)
    return jsonify(warnings=program_warnings(rows, recipes[index]))
