import hashlib
from typing import Annotated

from pybeerxml.base import BeerXmlModel
from pybeerxml.recipe import Recipe
from pydantic_xml import NoXml, element

from picobrew_server.beerxml.picobrew_kegsmart import PicoBrewKegSmartProgram
from picobrew_server.beerxml.picobrew_program_step import PicoBrewProgramStep, PicoBrewZymaticProgram


def get_hash(text: str) -> str:
    hasher = hashlib.md5()
    hasher.update(text.encode("utf-8"))
    return hasher.hexdigest()[:32]


class PicoBrewRecipe(Recipe, tag="RECIPE"):
    # Not part of the XML document. NoXml keeps pydantic-xml from binding it to the element text.
    filename: Annotated[str, NoXml] = ""

    zymatic: PicoBrewZymaticProgram | None = element(tag="ZYMATIC", default=None)
    kegsmart: PicoBrewKegSmartProgram | None = element(tag="KEGSMART", default=None)

    @property
    def id(self) -> str:
        # a unique id for every recipe, derived from the filename
        return get_hash(self.filename)

    @property
    def steps(self) -> list[PicoBrewProgramStep]:
        return self.zymatic.steps if self.zymatic else []

    def serialize(self) -> str:
        return f"{self.name}/{self.id}/{self.get_recipe_steps()}/"

    def get_recipe_steps(self) -> str:
        steps = [step.serialize() for step in self.steps]
        return "/".join(steps)


class PicoBrewRecipes(BeerXmlModel, tag="RECIPES"):
    # Overrides pybeerxml's own container so that parsing yields PicoBrewRecipes
    recipes: list[PicoBrewRecipe] = element(tag="RECIPE", default_factory=list)
