class Recipe(object):
    def __init__(self):
        self.name = None
        self.brewer = None
        self.batch_size = None
        self.boil_size = None
        self.efficiency = None
        self.primary_age = None
        self.primary_temp = None
        self.secondary_age = None
        self.secondary_temp = None
        self.tertiary_age = None
        self.tertiary_temp = None
        self.carbonation = None
        self.carbonation_temp = None
        self.age = None
        self.age_temp = None

        self.style = None
        self.hops = []
        self.yeasts = []
        self.fermentables = []
        self.mash = None


class Fermentable(object):

    def __init__(self):
        self.name = None
        self.weight = None
        #self.yield = None
        self.color = None
        self.add_after_boil = None  # Should be Bool

        @property
        def add_after_boil(self):
            return bool(self.add_after_boil)


class Yeast(object):
    def __init__(self):
        self.name = None
        self.type = None
        self.form = None
        self.attenuation = None
        self.notes = None


class Hop(object):
    def __init__(self):
        self.name = None
        self.aa = None
        self.use = None
        self.form = None
        self.notes = None


class Style(object):
    def __init__(self):
        self.name = None
        self.category = None
        self.og_min = None
        self.og_max = None
        self.fg_min = None
        self.fg_max = None
        self.ibu_min = None
        self.ibu_max = None
        self.color_min = None
        self.color_max = None
        self.abv_min = None
        self.abv_max = None
        self.carb_min = None
        self.carb_max = None
        self.notes = None

class Mash(object):
    def __init__(self):
        self.grain_temp = None
        self.sparge_temp = None
        self.ph = None
        self.notes = None

        self.steps = []

class MashStep(object):
    def __init__(self):
        self.type = None
        self.infuse_amount = None
        self.step_temp = None
        self.end_temp = None
        self.step_time = None
        self.decoction_amt = None

        @property
        def waterRatio(self):
            raise NotImplementedError("waterRation")
            # water_amout = self.infuse_amount or self.decoction_amt
            # return water_amount / recipe.grainWeight()
