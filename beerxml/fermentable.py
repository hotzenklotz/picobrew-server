import re


class Fermentable(object):
    # Regular expressions to match for boiling sugars (DME, LME, etc).
    STEEP = re.compile("/biscuit|black|cara|chocolate|crystal|munich|roast|special|toast|victory|vienna/i")
    BOIL = re.compile("/candi|candy|dme|dry|extract|honey|lme|liquid|sugar|syrup|turbinado/i")

    def __init__(self):
        self.name = None
        self.amount = None
        self._yield = None
        self.color = None
        self._add_after_boil = None  # Should be Bool

    @property
    def add_after_boil(self):
        return bool(self._add_after_boil)

    @add_after_boil.setter
    def add_after_boil(self, value):
        self._add_after_boil = value

    @property
    def ppg(self):
        return 0.46214 * self._yield

    # When is this item added in the brewing process? Boil, steep, or mash?
    @property
    def addition(self):
        regexes = [
            # Forced values take precedence, then search known names and
            # default to mashing
            [re.compile("mash/i"), "mash"],
            [re.compile("steep/i"), "steep"],
            [re.compile("boil/i"), "boil"],
            [Fermentable.BOIL, "boil"],
            [Fermentable.STEEP, "steep"],
            [re.compile(".*"), "mash"]
        ]

        for regex, substitue in regexes:
            addition = re.sub(regex, substitue, self.name)

        return addition

    # Get the gravity units for a specific liquid volume with 100% efficiency
    def gu(self, liters=1.0):
        # gu = parts per gallon * weight in pounds / gallons
        weight_lb = self.amount * 2.20462
        volume_gallons = liters * 0.264172
        return self.ppg * weight_lb / volume_gallons
