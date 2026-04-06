from pathlib import Path

import pytest

from picobrew_server.beerxml.picobrew_parser import PicoBrewRecipeParser
from picobrew_server.beerxml.picobrew_recipe import PicoBrewRecipe, get_hash

RECIPES_DIR = Path(__file__).parent.parent.parent / "picobrew_server" / "recipes"
PARTY_PORTER_XML = RECIPES_DIR / "Party_Porter.xml"
ALWAYS_ALE_XML = RECIPES_DIR / "Always_Ale.xml"


def _make_xml(tmp_path: Path, name: str, zymatic_steps: str) -> Path:
    """Write a minimal valid BeerXML file with the given ZYMATIC block."""
    xml = f"""<?xml version="1.0" encoding="iso-8859-1"?>
<RECIPES>
  <RECIPE>
    <NAME>{name}</NAME>
    <VERSION>1</VERSION>
    <TYPE>All Grain</TYPE>
    <BREWER>Test</BREWER>
    <BATCH_SIZE>9.46</BATCH_SIZE>
    <BOIL_SIZE>13.74</BOIL_SIZE>
    <BOIL_TIME>60</BOIL_TIME>
    <EFFICIENCY>75</EFFICIENCY>
    <OG>1.050</OG>
    <FG>1.010</FG>
    {zymatic_steps}
  </RECIPE>
</RECIPES>"""
    path = tmp_path / f"{name.lower().replace(' ', '_')}.xml"
    path.write_text(xml)
    
    return path


SINGLE_STEP_ZYMATIC = """
<ZYMATIC>
  <STEP>
    <NAME>Heat to Mash</NAME>
    <TEMP>67</TEMP>
    <TIME>0</TIME>
    <LOCATION>PassThrough</LOCATION>
    <DRAIN>0</DRAIN>
  </STEP>
  <STEP>
    <NAME>Mash</NAME>
    <TEMP>67</TEMP>
    <TIME>60</TIME>
    <LOCATION>Mash</LOCATION>
    <DRAIN>5</DRAIN>
  </STEP>
</ZYMATIC>
"""


@pytest.fixture
def parser() -> PicoBrewRecipeParser:
    return PicoBrewRecipeParser()


@pytest.fixture
def simple_xml(tmp_path: Path) -> Path:
    return _make_xml(tmp_path, "Test Recipe", SINGLE_STEP_ZYMATIC)


@pytest.fixture
def no_zymatic_xml(tmp_path: Path) -> Path:
    return _make_xml(tmp_path, "Simple Recipe", "")


class TestParseBasics:
    def test_returns_list(self, parser, simple_xml):
        assert isinstance(parser.parse(simple_xml), list)

    def test_returns_one_recipe_per_recipe_element(self, parser, simple_xml):
        assert len(parser.parse(simple_xml)) == 1

    def test_returns_picobrew_recipe_instances(self, parser, simple_xml):
        recipes = parser.parse(simple_xml)
        assert all(isinstance(r, PicoBrewRecipe) for r in recipes)

    def test_accepts_path_input(self, parser, simple_xml):
        recipes = parser.parse(simple_xml)  # Path
        assert len(recipes) == 1

    def test_accepts_str_input(self, parser, simple_xml):
        recipes = parser.parse(str(simple_xml))  # str
        assert len(recipes) == 1

    def test_recipe_name_parsed(self, parser, simple_xml):
        assert parser.parse(simple_xml)[0].name == "Test Recipe"

    def test_recipe_id_is_hash_of_filename(self, parser, simple_xml):
        recipe = parser.parse(simple_xml)[0]
        assert recipe.id == get_hash(simple_xml.name)


class TestZymaticStepParsing:
    def test_step_count(self, parser, simple_xml):
        assert len(parser.parse(simple_xml)[0].steps) == 2

    def test_step_name(self, parser, simple_xml):
        assert parser.parse(simple_xml)[0].steps[0].name == "Heat to Mash"

    def test_step_temp(self, parser, simple_xml):
        assert parser.parse(simple_xml)[0].steps[0].temp == 67.0

    def test_step_time(self, parser, simple_xml):
        assert parser.parse(simple_xml)[0].steps[0].time == 0.0

    def test_step_location(self, parser, simple_xml):
        assert parser.parse(simple_xml)[0].steps[0].location == "PassThrough"

    def test_step_drain(self, parser, simple_xml):
        assert parser.parse(simple_xml)[0].steps[0].drain == 0.0

    def test_second_step_values(self, parser, simple_xml):
        step = parser.parse(simple_xml)[0].steps[1]
        assert step.name == "Mash"
        assert step.temp == 67.0
        assert step.time == 60.0
        assert step.location == "Mash"
        assert step.drain == 5.0

    def test_steps_serialize_correctly(self, parser, simple_xml):
        steps = parser.parse(simple_xml)[0].steps
        assert steps[0].serialize() == "Heat to Mash,67,0,0,0"
        assert steps[1].serialize() == "Mash,67,60,1,5"

    def test_no_zymatic_section_yields_empty_steps(self, parser, no_zymatic_xml):
        recipe = parser.parse(no_zymatic_xml)[0]
        assert recipe.steps == []

    def test_non_step_zymatic_children_ignored(self, parser, tmp_path):
        # MASH_TEMP / MASH_TIME / BOIL_TEMP are siblings of STEP but not STEPs
        xml_path = _make_xml(tmp_path, "Filtered", """
<ZYMATIC>
  <MASH_TEMP>67</MASH_TEMP>
  <MASH_TIME>90</MASH_TIME>
  <BOIL_TEMP>97</BOIL_TEMP>
  <STEP>
    <NAME>Only Step</NAME>
    <TEMP>67</TEMP>
    <TIME>0</TIME>
    <LOCATION>PassThrough</LOCATION>
    <DRAIN>0</DRAIN>
  </STEP>
</ZYMATIC>
""")
        steps = parser.parse(xml_path)[0].steps
        assert len(steps) == 1
        assert steps[0].name == "Only Step"


class TestPartyPorterIntegration:
    def test_recipe_name(self, parser):
        assert parser.parse(PARTY_PORTER_XML)[0].name == "Party Porter"

    def test_step_count(self, parser):
        assert len(parser.parse(PARTY_PORTER_XML)[0].steps) == 6

    def test_first_step(self, parser):
        step = parser.parse(PARTY_PORTER_XML)[0].steps[0]
        assert step.serialize() == "Heat to Single S...,67,0,0,0"

    def test_mash_step(self, parser):
        step = parser.parse(PARTY_PORTER_XML)[0].steps[1]
        assert step.name == "Single Step Infu..."
        assert step.temp == 67.0
        assert step.time == 90.0
        assert step.location == "Mash"
        assert step.drain == 8.0

    def test_boil_step(self, parser):
        step = parser.parse(PARTY_PORTER_XML)[0].steps[3]
        assert step.serialize() == "Boil Adjunct 1,97,60,2,5"

    def test_pause_step(self, parser):
        step = parser.parse(PARTY_PORTER_XML)[0].steps[4]
        assert step.serialize() == "Connect Chiller,18,0,6,0"

    def test_chill_step(self, parser):
        step = parser.parse(PARTY_PORTER_XML)[0].steps[5]
        assert step.serialize() == "Chill,18,10,0,10"

    def test_full_serialization_format(self, parser):
        recipe = parser.parse(PARTY_PORTER_XML)[0]
        serialized = recipe.serialize()
        assert serialized.startswith("Party Porter/")
        assert serialized.endswith("/")
        # id segment is a 32-char hex string
        parts = serialized.split("/")
        assert len(parts[1]) == 32
        assert all(c in "0123456789abcdef" for c in parts[1])

    def test_full_serialization_contains_all_steps(self, parser):
        serialized = parser.parse(PARTY_PORTER_XML)[0].serialize()
        assert "Heat to Single S...,67,0,0,0" in serialized
        assert "Single Step Infu...,67,90,1,8" in serialized
        assert "Boil Adjunct 1,97,60,2,5" in serialized
        assert "Connect Chiller,18,0,6,0" in serialized
        assert "Chill,18,10,0,10" in serialized


class TestAlwaysAle6010_2Integration:
    def test_recipe_name(self, parser):
        assert parser.parse(ALWAYS_ALE_XML)[0].name == "Always Ale"

    def test_step_count(self, parser):
        assert len(parser.parse(ALWAYS_ALE_XML)[0].steps) == 14

    def test_adjunct1_step(self, parser):
        step = parser.parse(ALWAYS_ALE_XML)[0].steps[3]
        assert step.serialize() == "Mash 1,67,30,1,8"

    def test_adjunct2_step(self, parser):
        step = parser.parse(ALWAYS_ALE_XML)[0].steps[4]
        assert step.serialize() == "Heat to Mash 2,68,0,0,0"

    def test_adjunct3_step(self, parser):
        step = parser.parse(ALWAYS_ALE_XML)[0].steps[5]
        assert step.serialize() == "Mash 2,68,60,1,8"

    def test_chill_step(self, parser):
        step = parser.parse(ALWAYS_ALE_XML)[0].steps[7]
        assert step.serialize() == "Mash Out,79,10,1,8"
