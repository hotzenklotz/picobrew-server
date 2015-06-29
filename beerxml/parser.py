from xml.etree import ElementTree
from recipe import *
import sys


# Map all child nodes to one object's attributes
def nodes_to_object(node, object):
    for n in list(node):
        node_to_object(n, object)


# Map a single node to one object's attributes
def node_to_object(node, object):
    attribute = to_lower(node.tag)
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
def parseBeerXml(xml_file):
    recipes = []

    with open(xml_file, "rt") as f:
        tree = ElementTree.parse(f)

    for recipeNode in tree.iter():
        if to_lower(recipeNode.tag) != "recipe":
            continue

        recipe = Recipe()
        recipes.append(recipe)

        for recipeProperty in list(recipeNode):
            tag_name = to_lower(recipeProperty.tag)

            if tag_name == "fermentables":
                for fermentable_node in list(recipeProperty):
                    fermentable = Fermentable()
                    nodes_to_object(fermentable_node, fermentable)
                    recipe.fermentables.append(fermentable)

            elif tag_name == "yeasts":
                for yeast_node in list(recipeProperty):
                    yeast = Yeast()
                    nodes_to_object(yeast_node, yeast)
                    recipe.yeasts.append(yeast)

            elif tag_name == "hops" or tag_name == "miscs":
                for hop_node in list(recipeProperty):
                    hop = Hop()
                    nodes_to_object(hop_node, hop)
                    recipe.hops.append(hop)

            elif tag_name == "style":
                style = Style()
                recipe.style = style
                nodes_to_object(recipeProperty, style)

            elif tag_name == "mash":

                for mash_node in list(recipeProperty):
                    mash = Mash()
                    recipe.mash = mash

                    if to_lower(mash_node.tag) == "mash_steps":
                        for mash_step_node in list(mash_node):
                            mash_step = MashStep()
                            nodes_to_object(mash_step_node, mash_step)
                            mash.steps.append(mash_step)
                    else:
                        nodes_to_object(mash_node, mash)

            else:
                node_to_object(recipeProperty, recipe)

    return recipes

# Helper function to transform strings to lower case
def to_lower(string):
    value = None
    try:
        value = string.lower()
    except NoneType:
        value = ""
    finally:
        return value


