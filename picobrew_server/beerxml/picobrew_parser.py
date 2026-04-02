from pathlib import Path
from typing import cast
from xml.etree import ElementTree

from pybeerxml import Parser
from pybeerxml.recipe import Recipe

from picobrew_server.beerxml.picobrew_program_step import PicoBrewProgramStep
from picobrew_server.beerxml.picobrew_recipe import PicoBrewRecipe


class PicoBrewRecipeParser:
    def __init__(self):
        self._parser = Parser()

    def parse(self, xml_file: str | Path) -> list[PicoBrewRecipe]:
        path = Path(xml_file)

        # Parse the BeerXML file
        raw_recipes = self._parser.parse(str(path))

        # Cast all recipes to PicoBrewRecipes
        recipes = [PicoBrewRecipe.from_beerxml_recipe(recipe, path.name) for recipe in raw_recipes]

        # Parse the PicoBrew Program Steps
        programs = self._parse_zymatic_heating_steps(path)

        # merge the parsed recipes with the PicoBrew program steps
        for recipe, steps in zip(recipes, programs):
            recipe.steps = steps

        return recipes

    def _parse_zymatic_heating_steps(self, xml_file: Path) -> list[list[PicoBrewProgramStep]]:
        # Extract the PicoBrew Zymatic/Z(?) specific heating/timing instructions from a recipe
        programs = []

        with xml_file.open("r") as recipe_file:
            tree = ElementTree.parse(recipe_file)

        for program_node in tree.iterfind(".//ZYMATIC"):
            steps = []
            for step_node in list(program_node):
                if step_node.tag.lower() == "step":
                    step = PicoBrewProgramStep()
                    self._parser.nodes_to_object(step_node, cast(Recipe, step))
                    steps.append(step)

            programs.append(steps)

        return programs
