from pybeerxml.base import BeerXmlModel, LenientFloat
from pydantic_xml import element

# PicoBrew encodes the brewing location of a step as a numeric id on the wire
LOCATION_IDS = {
    "PassThrough": 0,
    "Mash": 1,
    "Adjunct1": 2,
    "Adjunct2": 3,
    "Adjunct3": 4,
    "Adjunct4": 5,
    "Pause": 6,  # TODO Verify this
}


class PicoBrewProgramStep(BeerXmlModel, tag="STEP"):
    name: str | None = element(tag="NAME", default=None)
    temp: float | None = element(tag="TEMP", default=None)
    time: float | None = element(tag="TIME", default=None)
    location: str | None = element(tag="LOCATION", default=None)
    drain: float | None = element(tag="DRAIN", default=None)

    def serialize(self) -> str:
        assert self.name is not None
        assert self.temp is not None
        assert self.time is not None
        assert self.location is not None
        assert self.drain is not None

        # e.g. Heat to Temp,102,0,0,0
        return f"{self.name},{int(self.temp)},{int(self.time)},{LOCATION_IDS[self.location]},{int(self.drain)}"


class PicoBrewZymaticProgram(BeerXmlModel, tag="ZYMATIC"):
    # PicoBrew Zymatic/Z specific heating/timing instructions, not part of the BeerXML spec
    mash_temp: LenientFloat = element(tag="MASH_TEMP", default=None)
    mash_time: LenientFloat = element(tag="MASH_TIME", default=None)
    boil_temp: LenientFloat = element(tag="BOIL_TEMP", default=None)
    steps: list[PicoBrewProgramStep] = element(tag="STEP", default_factory=list)
