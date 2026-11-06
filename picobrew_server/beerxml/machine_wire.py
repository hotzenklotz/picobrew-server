"""Encode programs for the recipe-list parser of Zymatic firmware 1.1.14.

The firmware copies every field into a fixed-size buffer without bounds checks,
rejects (WiFi) or drops (Ethernet) bytes outside 0x01-0x7E, and splits fields on
',', '/', '|' and '#'. Everything sent to the machine is therefore made to fit
here, on the fly. Stored recipes are never modified.
"""

import logging
import re
import unicodedata
from dataclasses import dataclass

from picobrew_server.beerxml.picobrew_recipe import PicoBrewRecipe, get_hash

logger = logging.getLogger(__name__)

MAX_RECIPES = 10  # g_recipes[10]; the parser stops reading after ten records
MAX_STEPS = 25  # Recipe.steps[25]; more steps overwrite the next recipe
MAX_NAME_LENGTH = 20  # Recipe.name[21] and the step-name token[21]
MAX_RECORD_LENGTH = 511  # the Ethernet reader buffers one record in line[512]
MAX_FIELD_VALUE = 255  # temperature, time, location and drain are uint8_t

# Spelled-out replacements for characters that Unicode decomposition would drop or mangle.
TRANSLITERATIONS = str.maketrans(
    {
        "Ä": "Ae",
        "Ö": "Oe",
        "Ü": "Ue",
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "ß": "ss",
        "Æ": "AE",
        "æ": "ae",
        "Ø": "O",
        "ø": "o",
        "Œ": "OE",
        "œ": "oe",
        "Ł": "L",
        "ł": "l",
        "Đ": "D",
        "đ": "d",
        "–": "-",
        "—": "-",
        "‘": "'",
        "’": "'",
        "“": '"',
        "”": '"',
    }
)
UNSAFE_CHARACTERS = re.compile(r"[,/|#\x00-\x1f\x7f]")


@dataclass(frozen=True)
class MachineProgram:
    """One program as the machine sees it: its wire ID and its encoded list record."""

    id: str
    name: str
    record: str  # "NAME/ID/STEP,TEMP,TIME,LOCATION,DRAIN/.../"


def wire_text(value: str | None, limit: int, fallback: str) -> str:
    """Return printable ASCII without protocol delimiters, at most `limit` characters."""
    text = (value or "").translate(TRANSLITERATIONS)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = " ".join(UNSAFE_CHARACTERS.sub(" ", text).split())
    return text[:limit].rstrip() or fallback


def wire_number(value: str, label: str, recipe_name: str) -> int:
    number = int(value)
    clamped = min(max(number, 0), MAX_FIELD_VALUE)
    if clamped != number:
        logger.warning("Recipe %r: %s %d sent to the machine as %d", recipe_name, label, number, clamped)
    return clamped


def encode_record(recipe_name: str, program_id: str, steps: list[tuple[str, int, int, int, int]]) -> str:
    serialized = "".join(f"{name},{temp},{time},{location},{drain}/" for name, temp, time, location, drain in steps)
    return f"{recipe_name}/{program_id}/{serialized}"


def encode_recipe(recipe: PicoBrewRecipe, program_id: str) -> MachineProgram | None:
    """Encode a recipe for the machine, or return None if it cannot be sent safely."""
    label = recipe.name or recipe.filename
    if not recipe.zymatic or not recipe.steps:
        return None
    if len(recipe.steps) > MAX_STEPS:
        count = len(recipe.steps)
        logger.warning("Recipe %r has %d steps; the machine supports %d. Not sent.", label, count, MAX_STEPS)
        return None

    # Clean step names first so the recipe's own serialization (including any unit
    # conversion) can be split back into fields. The copy leaves the stored recipe untouched.
    names = [wire_text(step.name, MAX_NAME_LENGTH, f"Step {index}") for index, step in enumerate(recipe.steps, 1)]
    steps = [step.model_copy(update={"name": name}) for step, name in zip(recipe.steps, names)]
    copy = recipe.model_copy(update={"zymatic": recipe.zymatic.model_copy(update={"steps": steps})})
    try:
        fields = [step.split(",") for step in copy.get_recipe_steps().split("/")]
        numbers = [
            (
                wire_number(temp, "temperature", label),
                wire_number(time, "time", label),
                wire_number(location, "location", label),
                wire_number(drain, "drain time", label),
            )
            for _name, temp, time, location, drain in fields
        ]
    # OverflowError: a non-finite value such as <TEMP>inf</TEMP> cannot become an int.
    except (AssertionError, KeyError, OverflowError, ValueError) as error:
        logger.warning("Recipe %r has an incomplete or invalid machine program (%r). Not sent.", label, error)
        return None

    recipe_name = wire_text(recipe.name, MAX_NAME_LENGTH, "Recipe")
    # Shorten step names until the record fits the Ethernet reader's buffer.
    for limit in range(MAX_NAME_LENGTH, 0, -1):
        record = encode_record(
            recipe_name,
            program_id,
            [(name[:limit].rstrip(), *values) for name, values in zip(names, numbers)],
        )
        if len(record) <= MAX_RECORD_LENGTH:
            if limit < MAX_NAME_LENGTH:
                logger.warning("Recipe %r: step names shortened to %d characters for the machine", label, limit)
            return MachineProgram(id=program_id, name=recipe_name, record=record)
    logger.warning("Recipe %r does not fit the machine's record buffer. Not sent.", label)
    return None


def program_id(recipe: PicoBrewRecipe) -> str:
    # The first recipe of a file keeps the historical filename hash so existing
    # sessions stay recoverable; later recipes in the same file need their own ID.
    if recipe.source_index == 0:
        return recipe.id
    return get_hash(f"{recipe.filename}:{recipe.source_index}")


def assign_program_ids(recipes: list[PicoBrewRecipe]) -> list[tuple[str, PicoBrewRecipe]]:
    """Give every recipe a unique program ID without encoding it.

    IDs depend only on the set of recipe paths, never on whether a recipe can be
    sent: within a group of recipes that share a filename-based ID, the one with
    the first source path keeps it and the others are disambiguated by path.
    """
    first_claim: dict[str, str] = {}
    for recipe in recipes:
        key = program_id(recipe)
        first_claim[key] = min(first_claim.get(key, recipe.source_file), recipe.source_file)

    assigned = []
    seen: set[str] = set()
    for recipe in recipes:
        identifier = program_id(recipe)
        if first_claim[identifier] != recipe.source_file or identifier in seen:
            # Same filename in another folder: disambiguate by the full path.
            identifier = get_hash(f"{recipe.source_file}:{recipe.source_index}")
        if identifier in seen:
            logger.warning("Recipe %r has a duplicate program ID. Not sent.", recipe.name)
            continue
        seen.add(identifier)
        assigned.append((identifier, recipe))
    return assigned


def machine_programs(recipes: list[PicoBrewRecipe]) -> list[MachineProgram]:
    """Encode every sendable recipe with a unique, stable program ID."""
    programs = (encode_recipe(recipe, identifier) for identifier, recipe in assign_program_ids(recipes))
    return [program for program in programs if program is not None]


def find_machine_program(recipes: list[PicoBrewRecipe], identifier: str) -> MachineProgram | None:
    """Encode only the recipe with the given program ID, if it is sendable."""
    for assigned, recipe in assign_program_ids(recipes):
        if assigned == identifier:
            return encode_recipe(recipe, identifier)
    return None


def encode_list(programs: list[MachineProgram]) -> str:
    """Frame records as a recipe list. An empty list is '##', which the firmware reports as 'no recipes'."""
    if len(programs) > MAX_RECIPES:
        skipped = ", ".join(repr(program.name) for program in programs[MAX_RECIPES:])
        logger.warning("The machine shows at most %d recipes. Not sent: %s", MAX_RECIPES, skipped)
        programs = programs[:MAX_RECIPES]
    if not programs:
        return "##"
    return f"#{'|'.join(program.record for program in programs)}|#"
