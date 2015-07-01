from types import NoneType
from xml.etree import ElementTree
from recipe import *
from hop import Hop
from mash import Mash
from mash_step import MashStep
from yeast import Yeast
from style import Style
from fermentable import Fermentable
import sys

class BeerXMLParser(object):

    # Map all child nodes to one object's attributes
    def nodes_to_object(self, node, object):
        for n in list(node):
            self.node_to_object(n, object)

    # Map a single node to one object's attributes
    def node_to_object(self, node, object):
        attribute = self.to_lower(node.tag)

        # Yield is a protected keyword in Python, so let's rename it
        attribute = "_yield" if attribute == "yield" else attribute

        try:
            valueString = node.text or ""
            value = float(valueString)
        except ValueError:
            value = node.text

        try:
            setattr(object, attribute, value)
        except AttributeError():
            sys.stderr.write("Attribute <%s> not supported." % attribute)

    # Get a list of parsed recipes from BeerXML input
    def parse(self, xml_file):
        recipes = []

        with open(xml_file, "rt") as f:
            tree = ElementTree.parse(f)

        for recipeNode in tree.iter():
            if self.to_lower(recipeNode.tag) != "recipe":
                continue

            recipe = Recipe()
            recipes.append(recipe)

            for recipeProperty in list(recipeNode):
                tag_name = self.to_lower(recipeProperty.tag)

                if tag_name == "fermentables":
                    for fermentable_node in list(recipeProperty):
                        fermentable = Fermentable()
                        self.nodes_to_object(fermentable_node, fermentable)
                        recipe.fermentables.append(fermentable)

                elif tag_name == "yeasts":
                    for yeast_node in list(recipeProperty):
                        yeast = Yeast()
                        self.nodes_to_object(yeast_node, yeast)
                        recipe.yeasts.append(yeast)

                elif tag_name == "hops" or tag_name == "miscs":
                    for hop_node in list(recipeProperty):
                        hop = Hop()
                        self.nodes_to_object(hop_node, hop)
                        recipe.hops.append(hop)

                elif tag_name == "style":
                    style = Style()
                    recipe.style = style
                    self.nodes_to_object(recipeProperty, style)

                elif tag_name == "mash":

                    for mash_node in list(recipeProperty):
                        mash = Mash()
                        recipe.mash = mash

                        if self.to_lower(mash_node.tag) == "mash_steps":
                            for mash_step_node in list(mash_node):
                                mash_step = MashStep()
                                self.nodes_to_object(mash_step_node, mash_step)
                                mash.steps.append(mash_step)
                        else:
                            self.nodes_to_object(mash_node, mash)

                else:
                    self.node_to_object(recipeProperty, recipe)

        return recipes

    # Helper function to transform strings to lower case
    def to_lower(self, string):
        value = None
        try:
            value = string.lower()
        except NoneType:
            value = ""
        finally:
            return value
