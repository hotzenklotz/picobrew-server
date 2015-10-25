from pybeerxml import Parser
from picobrew_recipe import PicoBrewRecipe
from picobrew_program_step import PicoBrewProgramStep
from xml.etree import ElementTree


class PicoBrewParser(Parser):
    def parse(self, xml_file):

        # Parse the BeerXML file
        recipes = super(PicoBrewParser, self).parse(xml_file)

        # include the recipe filename in the parsed recipes for id creation
        for recipe in recipes:
            recipe.filename = xml_file

        # Cast all recipes to PicoBrewRcipes
        recipes = [PicoBrewRecipe(recipe) for recipe in recipes]

        # Parse the PicoBrew Program Steps
        programs = self.parse_program_steps(xml_file)

        # merge the parsed recipes with the PicoBrew program steps
        for (recipe, steps) in zip(recipes, programs):
            recipe.steps = steps

        return recipes

    def parse_program_steps(self, xml_file):

        programs = []

        with open(xml_file, "rt") as f:
            tree = ElementTree.parse(f)

            for programNode in tree.iterfind(".//PROGRAM"):

                steps = []
                for stepNode in list(programNode):
                    tag_name = self.to_lower(stepNode.tag)

                    if tag_name == "step":
                        step = PicoBrewProgramStep()
                        self.nodes_to_object(stepNode, step)
                        steps.append(step)

                programs.append(steps)

        return programs
