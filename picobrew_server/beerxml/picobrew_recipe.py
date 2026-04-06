import hashlib

from pybeerxml.recipe import Recipe

from picobrew_server.beerxml.picobrew_program_step import PicoBrewProgramStep


def get_hash(text: str) -> str:
    hasher = hashlib.md5()
    hasher.update(text.encode("utf-8"))
    return hasher.hexdigest()[:32]


class PicoBrewRecipe(Recipe):
    def __init__(self, filename: str):
        super().__init__()

        # create a unique id for every recipe based on the filename
        self.id = get_hash(filename)
        self.steps: list[PicoBrewProgramStep] = []

    @classmethod
    def from_beerxml_recipe(cls, recipe: Recipe, filename: str) -> "PicoBrewRecipe":
        picobrew_recipe = PicoBrewRecipe(filename)

        # Copy all properties of the BeerXML object
        for key, value in recipe.__dict__.items():
            picobrew_recipe.__dict__[key] = value

        return picobrew_recipe

    def serialize(self) -> str:
        return f"{self.name}/{self.id}/{self.get_recipe_steps()}/"

    def get_recipe_steps(self) -> str:
        steps = [step.serialize() for step in self.steps]
        return "/".join(steps)

    def save(self) -> None:
        pass
