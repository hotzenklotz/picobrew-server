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

        # self.og = None
        # self.fg = None
        # self.ibu = None

        self.style = None
        self.hops = []
        self.yeasts = []
        self.fermentables = []
        self.mash = None

    @property
    def abv(self):
        return ((1.05 * (self.og - self.fg)) / self.fg) / 0.79 * 100.0

    # Gravity degrees plato approximations
    @property
    def og_plato(self):
        og = self.og or self.calc_og()
        return (-463.37) + (668.72 * og) - (205.35 * (og * og))

    @property
    def fg_plato(self):
        fg = self.fg or self.calc_fg()
        return (-463.37) + (668.72 * fg) - (205.35 * (fg * fg))

    @property
    def ibu(self):

        ibu_method = "tinseth"
        _ibu = 0.0

        for hop in self.hops:
            if hop.alpha and hop.use.lower() == "boil":
                _ibu += hop.bitterness(ibu_method, self.og, self.batch_size)

        return _ibu

    @property
    def og(self):

        _og = 1.0
        steep_efficiency = 50
        mash_efficiency = 75

        # Calculate gravities and color from fermentables
        for fermentable in self.fermentables:
            addition = fermentable.addition
            if addition == "steep":
                efficiency = steep_efficiency / 100.0
            elif addition == "mash":
                efficiency = mash_efficiency / 100.0
            else:
                efficiency = 1.0

            # Update gravities
            gu = fermentable.gu(self.batch_size) * efficiency
            gravity = gu / 1000.0
            _og += gravity

        return _og

    @property
    def fg(self):

        _fg = 0
        attenuation = 0

        # Get attenuation for final gravity
        for yeast in self.yeasts:
            if yeast.attenuation > attenuation:
                attenuation = yeast.attenuation

        if attenuation == 0:
            attenuation = 75.0

        _fg = self.og - ((self.og - 1.0) * attenuation / 100.0)

        return _fg

    @ibu.setter
    def ibu(self, value):
        pass

    @fg.setter
    def fg(self, value):
        pass

    @og.setter
    def og(self, value):
        pass

    @abv.setter
    def abv(self, value):
        pass
