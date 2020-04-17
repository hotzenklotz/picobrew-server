from xml.etree import ElementTree
from typing import Text, List
from pathlib import PosixPath

from pybeerxml import Parser
from beerxml.picobrew_recipe import PicoBrewRecipe
from beerxml.picobrew_program_step import PicoBrewProgramStep


class PicoBrewRecipeParser(Parser):
    def parse(self, xml_file: PosixPath) -> List[PicoBrewRecipe]:

        # Parse the BeerXML file
        recipes = super(PicoBrewRecipeParser, self).parse(xml_file)

        # include the recipe filename in the parsed recipes for id creation
        for recipe in recipes:
            recipe.filename = xml_file.name

        # Cast all recipes to PicoBrewRcipes
        recipes = [PicoBrewRecipe(recipe) for recipe in recipes]

        # Parse the PicoBrew Program Steps
        programs = self.parse_zymatic_heating_steps(xml_file)

        # merge the parsed recipes with the PicoBrew program steps
        for (recipe, steps) in zip(recipes, programs):
            recipe.steps = steps

        return recipes

    def parse_zymatic_heating_steps(self, xml_file: PosixPath) -> List[List[PicoBrewProgramStep]]:
        # Extract the PicoBrew Zymatic/Z(?) specific heating/timing instructions from a recipe
        programs = []

        with xml_file.open("r") as f:
            tree = ElementTree.parse(f)

        for programNode in tree.iterfind(".//ZYMATIC"):

            steps = []
            for stepNode in list(programNode):
                tag_name = self.to_lower(stepNode.tag)

                if tag_name == "step":
                    step = PicoBrewProgramStep()
                    self.nodes_to_object(stepNode, step)
                    steps.append(step)

            programs.append(steps)

        return programs
