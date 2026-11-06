import re

from picobrew_server.beerxml.machine_wire import (
    MAX_RECORD_LENGTH,
    encode_list,
    find_machine_program,
    machine_programs,
    wire_text,
)
from picobrew_server.beerxml.picobrew_program_step import PicoBrewProgramStep, PicoBrewZymaticProgram
from picobrew_server.beerxml.picobrew_recipe import PicoBrewRecipe, get_hash

# What the firmware's recipe-list parser can hold: printable ASCII, no delimiters.
SAFE_FIELD = re.compile(r"[\x20-\x7e]{1,20}")


def make_recipe(name="Ale", steps=None, filename="ale.xml", index=0, location="Mash"):
    if steps is None:
        steps = [PicoBrewProgramStep(name="Mash", temp=152, time=60, location=location, drain=5)]
    return PicoBrewRecipe(
        name=name,
        filename=filename,
        source_file=f"/library/{filename}",
        source_index=index,
        zymatic=PicoBrewZymaticProgram(steps=steps),
    )


def fields_of(record: str) -> tuple[str, str, list[list[str]]]:
    name, program_id, *steps = record.split("/")
    assert steps[-1] == "", "the firmware needs a trailing '/' after the last step"
    return name, program_id, [step.split(",") for step in steps[:-1]]


def test_plain_recipe_matches_recipe_serialization():
    recipe = make_recipe()
    [program] = machine_programs([recipe])
    assert program.id == recipe.id
    assert program.record == recipe.serialize()


def test_names_become_short_printable_ascii_without_delimiters():
    step = PicoBrewProgramStep(name="Maische – Rast #1, 50/50 | Weißbier", temp=152, time=60, location="Mash", drain=5)
    recipe = make_recipe(name="Märzen / Oktoberfest #2, extra lang", steps=[step])
    before = recipe.model_dump()

    [program] = machine_programs([recipe])

    name, _, [[step_name, *_]] = fields_of(program.record)
    assert name == "Maerzen Oktoberfest"
    assert step_name == "Maische - Rast 1 50"
    assert SAFE_FIELD.fullmatch(name) and SAFE_FIELD.fullmatch(step_name)
    assert recipe.model_dump() == before


def test_blank_names_get_fallbacks():
    assert wire_text("", 20, "Recipe") == "Recipe"
    assert wire_text("###", 20, "Step 1") == "Step 1"
    assert wire_text("日本", 20, "Step 1") == "Step 1"


def test_numbers_are_clamped_to_a_byte():
    steps = [PicoBrewProgramStep(name="Boil", temp=300, time=-5, location="Adjunct1", drain=256)]
    [program] = machine_programs([make_recipe(steps=steps)])
    assert fields_of(program.record)[2] == [["Boil", "255", "0", "2", "255"]]


def test_unsendable_recipes_are_skipped_without_hiding_the_rest():
    too_long = make_recipe(
        name="Long",
        filename="long.xml",
        steps=[PicoBrewProgramStep(name=f"S{i}", temp=150, time=1, location="Mash", drain=0) for i in range(26)],
    )
    bad_location = make_recipe(name="Bad", filename="bad.xml", location="Nowhere")
    missing_temp = make_recipe(
        name="Missing",
        filename="missing.xml",
        steps=[PicoBrewProgramStep(name="Mash", temp=None, time=60, location="Mash", drain=5)],
    )
    good = make_recipe(name="Good", filename="good.xml")
    assert [program.name for program in machine_programs([too_long, bad_location, missing_temp, good])] == ["Good"]


def test_long_programs_fit_the_ethernet_record_buffer():
    steps = [
        PicoBrewProgramStep(name=f"Very long step name {i}", temp=212, time=120, location="Adjunct4", drain=10)
        for i in range(25)
    ]
    [program] = machine_programs([make_recipe(name="Twenty five steps!!", steps=steps)])
    assert len(program.record) <= MAX_RECORD_LENGTH
    _, _, step_fields = fields_of(program.record)
    assert len(step_fields) == 25
    assert all(fields[1:] == ["212", "120", "5", "10"] for fields in step_fields)


def test_recipes_in_one_file_get_distinct_stable_ids():
    first = make_recipe(name="First", filename="pair.xml", index=0)
    second = make_recipe(name="Second", filename="pair.xml", index=1)
    elsewhere = make_recipe(name="Elsewhere", filename="pair.xml", index=0)
    elsewhere.source_file = "/library/sub/pair.xml"

    programs = machine_programs([first, second, elsewhere])

    ids = [program.id for program in programs]
    assert len(set(ids)) == 3
    assert ids[0] == get_hash("pair.xml")
    assert [program.id for program in machine_programs([first, second, elsewhere])] == ids


def test_list_is_framed_capped_at_ten_and_empty_is_hash_hash():
    assert encode_list([]) == "##"
    programs = machine_programs([make_recipe(name=f"R{i}", filename=f"r{i}.xml") for i in range(12)])
    response = encode_list(programs)
    assert response.startswith("#") and response.endswith("|#")
    records = response[1:-2].split("|")
    assert [fields_of(record)[0] for record in records] == [f"R{i}" for i in range(10)]


def test_non_finite_numbers_skip_only_that_recipe():
    steps = [PicoBrewProgramStep(name="Mash", temp=float("inf"), time=60, location="Mash", drain=5)]
    broken = make_recipe(name="Broken", filename="broken.xml", steps=steps)
    good = make_recipe(name="Good", filename="good.xml")
    assert [program.name for program in machine_programs([broken, good])] == ["Good"]


def test_ids_do_not_depend_on_whether_a_same_named_recipe_is_sendable():
    long_steps = [PicoBrewProgramStep(name=f"S{i}", temp=150, time=1, location="Mash", drain=0) for i in range(26)]
    broken = make_recipe(name="A", filename="beer.xml", steps=long_steps)
    broken.source_file = "/library/a/beer.xml"
    other = make_recipe(name="B", filename="beer.xml")
    other.source_file = "/library/b/beer.xml"
    fixed = broken.model_copy(update={"zymatic": other.zymatic})

    [before] = machine_programs([broken, other])
    after = machine_programs([fixed, other])
    assert [program.name for program in after] == ["A", "B"]
    assert after[1].id == before.id != after[0].id
    assert after[0].id == get_hash("beer.xml")
    # Input order does not matter either.
    assert {program.name: program.id for program in machine_programs([other, fixed])} == {
        program.name: program.id for program in after
    }


def test_find_machine_program_matches_the_list():
    recipes = [make_recipe(name=f"R{i}", filename=f"r{i}.xml") for i in range(3)]
    programs = machine_programs(recipes)
    assert find_machine_program(recipes, programs[2].id) == programs[2]
    assert find_machine_program(recipes, "unknown") is None
