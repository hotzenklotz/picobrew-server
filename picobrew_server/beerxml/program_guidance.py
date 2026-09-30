"""Advisory brew checks and editable starters for Zymatic programs."""

import math
import re
from dataclasses import dataclass

from picobrew_server.beerxml.picobrew_recipe import PicoBrewRecipe

StepRow = dict[str, str]


@dataclass
class ProgramTemplate:
    id: str
    label: str
    description: str
    rows: list[StepRow]
    notes: list[str]
    unavailable: str = ""


def number(value: object) -> float | None:
    try:
        result = float(str(value))
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def program_warnings(rows: list[StepRow], recipe: PicoBrewRecipe) -> list[dict]:
    """Heuristics only: unusual sequences can be intentional."""
    warnings = []
    mash_rows = [i for i, row in enumerate(rows) if row.get("location") == "Mash"]
    needs_mash = (recipe.type or "").lower() != "extract"
    if rows and not mash_rows and needs_mash:
        warnings.append({"step": None, "message": "No mash step is present. Review whether this recipe needs mashing."})
    if mash_rows:
        times = [number(rows[i].get("time")) for i in mash_rows]
        if all(time is not None for time in times) and not any(time is not None and time > 0 for time in times):
            warnings.append(
                {"step": None, "message": "The mash has no timed rest. A time of 0 provides no timed hold."}
            )
    mash_seen = False
    boil_seen = False
    paused_after_boil = False
    highest_adjunct = 0
    for index, row in enumerate(rows, 1):
        location = row.get("location", "")
        temp = number(row.get("temp"))
        time = number(row.get("time"))
        if location == "Mash":
            if boil_seen:
                warnings.append(
                    {"step": index, "message": "Mashing occurs after a boil or adjunct step. Check the order."}
                )
            mash_seen = True
        if re.fullmatch(r"Adjunct[1-4]", location):
            if not mash_seen and (needs_mash or mash_rows):
                warnings.append({"step": index, "message": "An adjunct step occurs before mashing. Check the order."})
            adjunct = int(location[-1])
            if adjunct < highest_adjunct:
                warnings.append({"step": index, "message": "Adjunct compartments run backwards. Check the hop order."})
            highest_adjunct = max(highest_adjunct, adjunct)
            boil_seen = True
            paused_after_boil = False
        if temp is not None and temp >= 90:
            boil_seen = True
            paused_after_boil = False
        if location == "Pause" and boil_seen:
            paused_after_boil = True
        if (
            boil_seen
            and not paused_after_boil
            and location == "PassThrough"
            and temp is not None
            and temp <= 40
            and time is not None
            and time > 0
        ):
            warnings.append(
                {"step": index, "message": "Cooling follows the boil without a pause to connect the chiller."}
            )
    return warnings


def row(name: str, temp: float, time: float, location: str, drain: float = 0) -> StepRow:
    # Machine protocol fields cannot contain delimiters. Recipe names may.
    name = " ".join(re.sub(r"[,/|#\r\n]", " ", name).split())
    return {
        "name": name,
        "temp": str(round(temp)),
        "time": str(round(time)),
        "location": location,
        "drain": str(round(drain)),
    }


def recipe_rows(recipe: PicoBrewRecipe) -> list[StepRow]:
    return [
        {
            field: ""
            if (value := getattr(step, field)) is None
            else (f"{value:g}" if isinstance(value, float) else str(value))
            for field in ["name", "temp", "time", "location", "drain"]
        }
        for step in recipe.steps
    ]


def mash_program(rests: list[tuple[str, float, float]]) -> list[StepRow]:
    result = []
    for index, (name, temp, time) in enumerate(rests):
        result.extend(
            [
                row(f"Heat to {name}", temp, 0, "PassThrough"),
                row(name, temp, time, "Mash", 8 if index == len(rests) - 1 else 0),
            ]
        )
    return result


def finish_program() -> list[StepRow]:
    return [row("Connect chiller", 18, 0, "Pause"), row("Chill", 18, 10, "PassThrough", 10)]


DEFAULT_NOTES = [
    "Starter values follow the bundled Zymatic examples. Review temperatures, durations, and drain times "
    "for your setup.",
    "Boil defaults to 97°C; chilling defaults to 18°C for 10 minutes after a user-action pause.",
]


def from_recipe(recipe: PicoBrewRecipe) -> ProgramTemplate:
    template = ProgramTemplate(
        "recipe",
        "From this BeerXML recipe",
        "Use the recipe’s mash rests, boil duration, and timed boil-hop additions.",
        [],
        list(DEFAULT_NOTES),
    )
    rests: list[tuple[str, float, float]] = []
    if (recipe.type or "").lower() != "extract":
        for step in recipe.mash.steps if recipe.mash else []:
            if (step.type or "").lower() == "decoction":
                template.unavailable = "Decoction mash profiles need a custom machine program. Use another starter."
                return template
            temp, time = number(step.step_temp), number(step.step_time)
            if temp is None or not 0 <= temp <= 110 or time is None or time <= 0:
                template.unavailable = "A mash rest has missing or invalid temperature/time. Use another starter."
                return template
            rests.append((step.name or "Mash rest", temp, time))
        if not rests:
            rests = [("Mash rest", 67, 90)]
            template.notes.append("No mash profile was found; the draft uses a 67°C, 90-minute mash rest.")
    result = mash_program(rests)
    boil = number(recipe.boil_time)
    if boil is None or boil <= 0:
        boil = 60
        template.notes.append("No usable boil duration was found; the draft uses 60 minutes.")
    hop_times = set()
    for hop in recipe.hops:
        if (hop.use or "").lower() != "boil":
            continue
        time = number(hop.time)
        if time is None or time < 0:
            template.unavailable = "A boil hop has a missing or invalid time. Use another starter."
            return template
        hop_times.add(round(time))
    if len(hop_times) > 4:
        template.unavailable = "This recipe has more than four timed hop additions. A custom program is needed."
        return template
    if any((hop.use or "").lower() != "boil" for hop in recipe.hops):
        template.notes.append(
            "Dry hops, aroma additions, and other non-boil hops are not included in this machine draft."
        )
    if (
        any(temp != round(temp) or time != round(time) for _, temp, time in rests)
        or any(
            hop.time is not None and hop.time != round(hop.time)
            for hop in recipe.hops
            if (hop.use or "").lower() == "boil"
        )
        or boil != round(boil)
    ):
        template.notes.append("Fractional temperatures and times are rounded to whole machine units.")
    boil = round(boil)
    times = sorted(hop_times, reverse=True)
    if times and times[0] > boil:
        boil = times[0]
        template.notes.append(
            f"A hop time exceeds the recipe’s boil duration; the draft uses {boil} minutes. Review this."
        )
    result.append(row("Heat to boil", 97, 0, "PassThrough"))
    if times:
        if boil > times[0]:
            result.append(row("Boil before hops", 97, boil - times[0], "PassThrough"))
        for index, remaining in enumerate(times):
            following = times[index + 1] if index + 1 < len(times) else 0
            result.append(
                row(
                    f"Hop addition {index + 1}",
                    97,
                    remaining - following,
                    f"Adjunct{index + 1}",
                    5 if index == len(times) - 1 else 0,
                )
            )
        template.notes.append(
            "Hops with the same addition time share a compartment. Step durations are intervals between additions."
        )
    else:
        result.append(row("Boil", 97, boil, "PassThrough"))
        template.notes.append("No timed boil hops were found; the boil circulates through Pass through.")
    template.rows = result + finish_program()
    return template


def program_templates(recipe: PicoBrewRecipe, library: list[PicoBrewRecipe]) -> list[ProgramTemplate]:
    boil = [row("Heat to boil", 97, 0, "PassThrough"), row("Hop addition 1", 97, 60, "Adjunct1", 5)]
    result = [
        from_recipe(recipe),
        ProgramTemplate(
            "single",
            "Single-infusion mash",
            "One mash rest at 67°C for 90 minutes, then a 60-minute boil.",
            mash_program([("Mash rest", 67, 90)]) + boil + finish_program(),
            list(DEFAULT_NOTES),
        ),
        ProgramTemplate(
            "multi",
            "Multi-step mash",
            "Mash at 67°C for 30 minutes, 68°C for 60 minutes, then mash out at 79°C.",
            mash_program([("Mash 1", 67, 30), ("Mash 2", 68, 60), ("Mash out", 79, 10)]) + boil + finish_program(),
            list(DEFAULT_NOTES),
        ),
    ]
    for index, source in enumerate(library):
        if source.steps:
            result.append(
                ProgramTemplate(
                    f"copy-{index}",
                    f"Copy: {source.name or 'Untitled recipe'} · {source.filename} (recipe {source.source_index + 1})",
                    "Copy this saved program into your draft, including its step order, locations, and drain times.",
                    recipe_rows(source),
                    ["Review the copied program for this recipe before saving."],
                )
            )
    return result
