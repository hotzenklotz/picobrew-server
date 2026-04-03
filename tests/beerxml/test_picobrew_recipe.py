from pybeerxml.recipe import Recipe

from picobrew_server.beerxml.picobrew_program_step import PicoBrewProgramStep
from picobrew_server.beerxml.picobrew_recipe import PicoBrewRecipe, get_hash


def make_step(name: str, temp: float, time: float, location: str, drain: float) -> PicoBrewProgramStep:
    step = PicoBrewProgramStep()
    step.name = name
    step.temp = temp
    step.time = time
    step.location = location
    step.drain = drain
    return step


class TestGetHash:
    def test_returns_32_char_hex_string(self):
        result = get_hash("test.xml")
        assert len(result) == 32
        assert all(c in "0123456789abcdef" for c in result)

    def test_is_deterministic(self):
        assert get_hash("test.xml") == get_hash("test.xml")

    def test_different_inputs_give_different_hashes(self):
        assert get_hash("file_a.xml") != get_hash("file_b.xml")

    def test_empty_string_produces_valid_hash(self):
        result = get_hash("")
        assert len(result) == 32


class TestPicoBrewRecipeInit:
    def test_id_is_hash_of_filename(self):
        recipe = PicoBrewRecipe("my_recipe.xml")
        assert recipe.id == get_hash("my_recipe.xml")

    def test_different_filenames_produce_different_ids(self):
        assert PicoBrewRecipe("a.xml").id != PicoBrewRecipe("b.xml").id

    def test_steps_is_empty_list(self):
        recipe = PicoBrewRecipe("my_recipe.xml")
        assert recipe.steps == []


class TestFromBeerxmlRecipe:
    def test_copies_name(self):
        base = Recipe()
        base.name = "My IPA"
        result = PicoBrewRecipe.from_beerxml_recipe(base, "my_ipa.xml")
        assert result.name == "My IPA"

    def test_copies_og(self):
        base = Recipe()
        base.og = 1.065
        result = PicoBrewRecipe.from_beerxml_recipe(base, "recipe.xml")
        assert result.og == 1.065

    def test_copies_fg(self):
        base = Recipe()
        base.fg = 1.012
        result = PicoBrewRecipe.from_beerxml_recipe(base, "recipe.xml")
        assert result.fg == 1.012

    def test_id_is_hash_of_filename(self):
        # id is set by PicoBrewRecipe.__init__ and not overwritten by Recipe.__dict__
        # (pybeerxml's Recipe has no 'id' attribute)
        base = Recipe()
        base.name = "Test"
        result = PicoBrewRecipe.from_beerxml_recipe(base, "test_file.xml")
        assert result.id == get_hash("test_file.xml")

    def test_returns_picobrew_recipe_instance(self):
        result = PicoBrewRecipe.from_beerxml_recipe(Recipe(), "recipe.xml")
        assert isinstance(result, PicoBrewRecipe)

    def test_steps_is_empty_after_conversion(self):
        result = PicoBrewRecipe.from_beerxml_recipe(Recipe(), "recipe.xml")
        assert result.steps == []


class TestSerialize:
    def test_format_is_name_slash_id_slash_steps_slash(self):
        recipe = PicoBrewRecipe("test.xml")
        recipe.name = "My IPA"
        # empty steps → get_recipe_steps() returns "", so format yields "name/id//"
        assert recipe.serialize() == f"My IPA/{get_hash('test.xml')}//"

    def test_includes_serialized_steps(self):
        recipe = PicoBrewRecipe("test.xml")
        recipe.name = "Ale"
        recipe.steps = [make_step("Heat", 67.0, 0.0, "PassThrough", 0.0)]
        assert recipe.serialize() == f"Ale/{get_hash('test.xml')}/Heat,67,0,0,0/"

    def test_multiple_steps_joined_by_slash(self):
        recipe = PicoBrewRecipe("test.xml")
        recipe.name = "Ale"
        recipe.steps = [
            make_step("Heat", 67.0, 0.0, "PassThrough", 0.0),
            make_step("Mash", 67.0, 60.0, "Mash", 5.0),
        ]
        assert recipe.serialize() == f"Ale/{get_hash('test.xml')}/Heat,67,0,0,0/Mash,67,60,1,5/"


class TestGetRecipeSteps:
    def test_empty_steps_returns_empty_string(self):
        recipe = PicoBrewRecipe("test.xml")
        assert recipe.get_recipe_steps() == ""

    def test_single_step(self):
        recipe = PicoBrewRecipe("test.xml")
        recipe.steps = [make_step("Heat", 67.0, 0.0, "PassThrough", 0.0)]
        assert recipe.get_recipe_steps() == "Heat,67,0,0,0"

    def test_multiple_steps_joined_by_slash(self):
        recipe = PicoBrewRecipe("test.xml")
        recipe.steps = [
            make_step("Heat", 67.0, 0.0, "PassThrough", 0.0),
            make_step("Mash", 67.0, 90.0, "Mash", 8.0),
            make_step("Boil", 97.0, 60.0, "Adjunct1", 5.0),
        ]
        assert recipe.get_recipe_steps() == "Heat,67,0,0,0/Mash,67,90,1,8/Boil,97,60,2,5"
