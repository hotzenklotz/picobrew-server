class PicoBrewProgramStep(object):

    def __init__(self):
        self.name = None
        self.temp = None
        self.time = None
        self.location = None
        self.drain = None

    def serialize(self):

        # e.g. Heat to Temp,102,0,0,0
        return "{0},{1},{2},{3},{4}".format(
            self.name,
            int(self.temp),
            int(self.time),
            int(self.location),
            int(self.drain)
        )