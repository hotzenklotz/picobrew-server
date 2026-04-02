from pathlib import Path
from xml.etree import ElementTree

from pybeerxml import Parser

from picobrew_server.beerxml.picobrew_program_step import PicoBrewProgramStep
from picobrew_server.beerxml.picobrew_recipe import PicoBrewRecipe


class PicoBrewRecipeParser(Parser):
    def parse(self, xml_file: Path) -> list[PicoBrewRecipe]:

        # Parse the BeerXML file
        recipes: list[PicoBrewRecipe] = super().parse(xml_file)

        # Cast all recipes to PicoBrewRcipes
        recipes = [PicoBrewRecipe.from_beerxml_recipe(recipe, xml_file.name) for recipe in recipes]

        # Parse the PicoBrew Program Steps
        programs = self.parse_zymatic_heating_steps(xml_file)

        # merge the parsed recipes with the PicoBrew program steps
        for recipe, steps in zip(recipes, programs):
            recipe.steps = steps

        return recipes

    # pylint: disable=bad-continuation
    def parse_zymatic_heating_steps(self, xml_file: Path) -> list[list[PicoBrewProgramStep]]:
        # Extract the PicoBrew Zymatic/Z(?) specific heating/timing instructions from a recipe
        programs = []

        with xml_file.open("r") as recipe_file:
            tree = ElementTree.parse(recipe_file)

        for program_node in tree.iterfind(".//ZYMATIC"):
            steps = []
            for step_node in list(program_node):
                tag_name = self.to_lower(step_node.tag)

                if tag_name == "step":
                    step = PicoBrewProgramStep()
                    self.nodes_to_object(step_node, step)
                    steps.append(step)

            programs.append(steps)

        return programs
