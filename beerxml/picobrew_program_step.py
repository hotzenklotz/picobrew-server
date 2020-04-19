from typing import Text


class PicoBrewProgramStep:
    def __init__(self):
        self.name = None
        self.temp = None
        self.time = None
        self.location = None
        self.drain = None

    def serialize(self) -> Text:
        # pylint: disable=fixme
        location_id_map = {
            "PassThrough": 0,
            "Mash": 1,
            "Adjunct1": 2,
            "Adjunct2": 3,
            "Adjunct3": 4,
            "Adjunct4": 5,
            "Pause": 6,  # TODO Verify this
        }

        # e.g. Heat to Temp,102,0,0,0
        return "{0},{1},{2},{3},{4}".format(
            self.name,
            int(self.temp),
            int(self.time),
            location_id_map[self.location],
            int(self.drain),
        )
