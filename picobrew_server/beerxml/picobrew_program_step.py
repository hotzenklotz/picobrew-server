class PicoBrewProgramStep:
    def __init__(self):
        self.name: str | None = None
        self.temp: float | None = None
        self.time: float | None = None
        self.location: str | None = None
        self.drain: float | None = None

    def serialize(self) -> str:
        assert self.name is not None
        assert self.temp is not None
        assert self.time is not None
        assert self.location is not None
        assert self.drain is not None

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
        return f"{self.name},{int(self.temp)},{int(self.time)},{location_id_map[self.location]},{int(self.drain)}"
