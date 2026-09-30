import pytest
from pybeerxml.hop import Hop
from pybeerxml.mash import Mash
from pybeerxml.mash_step import MashStep

from picobrew_server.beerxml.picobrew_program_step import PicoBrewProgramStep, PicoBrewZymaticProgram
from picobrew_server.beerxml.picobrew_recipe import PicoBrewRecipe
from picobrew_server.beerxml.program_guidance import from_recipe, program_templates, program_warnings, row
from picobrew_server.blueprints.programs import parse_steps


def recipe(*hop_times, boil=60, rests=None):
    return PicoBrewRecipe(
        name="Template Ale",
        type="All Grain",
        boil_time=boil,
        hops=[Hop(name=f"Hop {i}", use="boil", time=time) for i, time in enumerate(hop_times)],
        mash=Mash(steps=rests or [MashStep(name="Mash rest", type="Infusion", step_temp=67, step_time=90)]),
    )


def messages(rows, source=None):
    return " ".join(warning["message"] for warning in program_warnings(rows, source or recipe()))


def test_builtin_starters_are_valid_and_have_no_sequence_warnings():
    source = recipe(60, 10, 2)
    for starter in program_templates(source, []):
        steps, errors = parse_steps(starter.rows)
        assert not errors
        assert steps
        assert not program_warnings(starter.rows, source)
        assert steps[-2].location == "Pause"
        assert steps[-1].location == "PassThrough"


def test_hop_times_are_intervals_not_repeated_full_durations():
    starter = from_recipe(recipe(60, 10, 2))
    adjuncts = [r for r in starter.rows if r["location"].startswith("Adjunct")]
    assert [(r["location"], r["time"], r["drain"]) for r in adjuncts] == [
        ("Adjunct1", "50", "0"),
        ("Adjunct2", "8", "0"),
        ("Adjunct3", "2", "5"),
    ]


def test_boil_before_first_hop_and_shared_hop_compartment():
    starter = from_recipe(recipe(10, 10, 2))
    timed_boil = [r for r in starter.rows if r["temp"] == "97" and int(r["time"]) > 0]
    assert [(r["location"], r["time"]) for r in timed_boil] == [
        ("PassThrough", "50"),
        ("Adjunct1", "8"),
        ("Adjunct2", "2"),
    ]
    assert sum(int(r["time"]) for r in timed_boil) == 60


def test_mash_rests_and_final_drain_follow_recipe_profile():
    source = recipe(
        rests=[
            MashStep(name="Protein / rest", step_temp=50, step_time=20),
            MashStep(name="Conversion", step_temp=67, step_time=60),
        ]
    )
    starter = from_recipe(source)
    rests = [r for r in starter.rows if r["location"] == "Mash"]
    assert [(r["temp"], r["time"], r["drain"]) for r in rests] == [("50", "20", "0"), ("67", "60", "8")]
    assert rests[0]["name"] == "Protein rest"
    assert not parse_steps(starter.rows)[1]


def test_missing_recipe_profile_uses_explicit_defaults():
    starter = from_recipe(PicoBrewRecipe(name="Bare recipe"))
    assert starter.rows[1] == row("Mash rest", 67, 90, "Mash", 8)
    assert any("No mash profile" in note for note in starter.notes)
    assert any("60 minutes" in note for note in starter.notes)
    assert any(r["name"] == "Boil" and r["location"] == "PassThrough" for r in starter.rows)


def test_extract_starter_does_not_invent_mashing_or_warn_missing_mash():
    source = recipe(60)
    source.type = "Extract"
    starter = from_recipe(source)
    assert not any(r["location"] == "Mash" for r in starter.rows)
    assert not program_warnings(starter.rows, source)


def test_excess_hop_times_and_unsupported_profiles_are_not_silently_dropped():
    assert from_recipe(recipe(60, 30, 15, 10, 2)).unavailable
    assert from_recipe(recipe(rests=[MashStep(type="Decoction", step_temp=67, step_time=60)])).unavailable
    assert from_recipe(recipe(rests=[MashStep(step_temp="unknown", step_time=60)])).unavailable


def test_non_boil_hops_are_excluded_with_a_visible_note():
    source = recipe(60)
    source.hops.append(Hop(use="Dry Hop", time=10080))
    starter = from_recipe(source)
    assert not starter.unavailable
    assert len([r for r in starter.rows if r["location"].startswith("Adjunct")]) == 1
    assert any("Dry hops" in note for note in starter.notes)


def test_inconsistent_boil_duration_and_rounding_are_explained():
    source = recipe(90.2, 10, boil=60)
    source.mash.steps[0].step_temp = 66.8
    starter = from_recipe(source)
    assert starter.rows[1]["temp"] == "67"
    assert any("rounded" in note for note in starter.notes)
    assert any("90 minutes" in note for note in starter.notes)
    assert sum(int(r["time"]) for r in starter.rows if r["temp"] == "97") == 90


def test_copy_keeps_all_step_fields_and_does_not_mutate_source():
    source = recipe()
    source.filename = "original.xml"
    source.zymatic = PicoBrewZymaticProgram(
        steps=[
            PicoBrewProgramStep(name="Custom rest", temp=68, time=55, location="Mash", drain=7),
        ]
    )
    before = source.model_dump()
    starter = program_templates(recipe(), [source])[-1]
    assert starter.id.startswith("copy-")
    assert parse_steps(starter.rows)[0] == source.steps
    assert source.model_dump() == before


@pytest.mark.parametrize(
    "rows,expected",
    [
        ([row("Hop", 97, 10, "Adjunct1"), row("Mash", 67, 60, "Mash")], "before mashing"),
        (
            [row("Mash", 67, 60, "Mash"), row("Hop", 97, 10, "Adjunct1"), row("Mash again", 67, 20, "Mash")],
            "Mashing occurs after",
        ),
        (
            [row("Mash", 67, 60, "Mash"), row("Hop 3", 97, 10, "Adjunct3"), row("Hop 2", 97, 2, "Adjunct2")],
            "run backwards",
        ),
        ([row("Mash", 67, 0, "Mash")], "no timed rest"),
        ([row("Boil", 97, 60, "PassThrough"), row("Chill", 18, 10, "PassThrough")], "without a pause"),
    ],
)
def test_sequence_warnings(rows, expected):
    assert expected in messages(rows)


def test_warning_points_to_step_and_clears_when_sequence_is_fixed():
    bad = [row("Hop", 97, 10, "Adjunct1"), row("Mash", 67, 60, "Mash")]
    assert any(w["step"] == 1 for w in program_warnings(bad, recipe()))
    assert not program_warnings(list(reversed(bad)), recipe())


def test_warning_checks_tolerate_incomplete_editor_fields():
    partial = {"name": "", "location": "Mash", "temp": "", "time": "", "drain": ""}
    assert not program_warnings([partial], recipe())
