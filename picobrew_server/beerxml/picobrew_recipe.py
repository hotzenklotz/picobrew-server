import hashlib

from typing import Text, List
from pybeerxml import Recipe
from picobrew_server.beerxml.picobrew_program_step import PicoBrewProgramStep


def get_hash(text: Text) -> Text:
    hasher = hashlib.md5()
    hasher.update(text.encode("utf-8"))
    return hasher.hexdigest()[:32]


class PicoBrewRecipe(Recipe):
    def __init__(self, filename: Text):
        super().__init__()

        # create a unique id for every recipe based on the filename
        # pylint: disable=invalid-name
        self.id = get_hash(filename)
        self.steps: List[PicoBrewProgramStep] = []

    @classmethod
    def from_beerxml_recipe(cls, recipe: Recipe, filename: Text) -> "PicoBrewRecipe":

        picobrew_recipe = PicoBrewRecipe(filename)

        # Copy all properties of the BeerXML object
        for key, value in recipe.__dict__.items():
            picobrew_recipe.__dict__[key] = value

        return picobrew_recipe

    def serialize(self) -> Text:
        return "{0}/{1}/{2}/".format(self.name, self.id, self.get_recipe_steps(),)

    def get_recipe_steps(self) -> Text:
        steps = [step.serialize() for step in self.steps]
        return "/".join(steps)

    def save(self):
        pass
