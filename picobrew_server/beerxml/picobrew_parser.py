from pathlib import Path

from picobrew_server.beerxml.picobrew_recipe import PicoBrewRecipe, PicoBrewRecipes

__all__ = ["PicoBrewRecipe", "PicoBrewRecipeParser"]


class PicoBrewRecipeParser:
    def parse(self, xml_file: str | Path) -> list[PicoBrewRecipe]:
        path = Path(xml_file)

        # Read as bytes so that ElementTree honours the encoding declared in the
        # XML prolog (PicoBrew writes iso-8859-1, not utf-8).
        recipes = PicoBrewRecipes.from_xml(path.read_bytes()).recipes

        for recipe in recipes:
            recipe.filename = path.name

        return recipes
