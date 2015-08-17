from beerxml import recipe
import uuid

class PicoBrewRecipe(recipe.Recipe):

    def __init__(self, parent):
        self.__dict__ = parent.__dict__

        self.id = uuid.uuid4()
        self.steps = []

    def serialize(self):

        return "{0}/{1}/{2}/".format(
            self.name,
            self.id,
            self.get_recipe_steps(),
        )

    def get_recipe_steps(self):

        steps = map(lambda step: step.serialize(), self.steps)
        return "/".join(steps)

    def save(self):
        pass



