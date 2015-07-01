import math


class Hop(object):
    def __init__(self):
        self.name = None
        self.alpha = None
        self.amount = None
        self.use = None
        self.form = None
        self.notes = None
        self.time = None

    def utilization_factor(self):
        # Account for better utilization from pellets vs. whole
        return 1.15 if self.form == "pellet" else 1.0

    def bitterness(self, ibu_method, early_og, batch_size):
        # Calculate bitterness based on chosen method

        if ibu_method == "tinseth":
            bitterness = 1.65 * math.pow(0.000125, early_og - 1.0) * ((1 - math.pow(math.e, -0.04 * self.time)) / 4.15) * ((self.alpha / 100.0 * self.amount * 1000000) / batch_size) * self.utilization_factor()

        elif ibu_method == "rager":
            utilization = 18.11 + 13.86 * math.tanh((self.time - 31.32) / 18.27)
            adjustment = max(0, (early_og - 1.050) / 0.2)
            bitterness = self.amount * 100 * utilization * self.utilization_factor() * self.alpha / (batch_size * (1 + adjustment))

        else:
            raise Exception("Unknown IBU method %s!" % ibu_method)

        return bitterness
