from typing import Literal

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

TemperatureUnit = Literal["C", "F"]


def convert_temperature(temp: float, source: TemperatureUnit, target: TemperatureUnit) -> float:
    # Zero is the machine's no-heating sentinel, including rinse and pause steps.
    if temp == 0 or source == target:
        return temp
    return temp * 9 / 5 + 32 if target == "F" else (temp - 32) * 5 / 9


class PicoBrewProgramStep(BeerXmlModel, tag="STEP"):
    name: str | None = element(tag="NAME", default=None)
    temp: float | None = element(tag="TEMP", default=None)
    time: float | None = element(tag="TIME", default=None)
    location: str | None = element(tag="LOCATION", default=None)
    drain: float | None = element(tag="DRAIN", default=None)

    def serialize(self, temperature_unit: TemperatureUnit = "F") -> str:
        assert self.name is not None
        assert self.temp is not None
        assert self.time is not None
        assert self.location is not None
        assert self.drain is not None

        temp = convert_temperature(self.temp, temperature_unit, "F")
        wire_temp = round(temp) if temperature_unit == "C" else int(temp)
        return f"{self.name},{wire_temp},{int(self.time)},{LOCATION_IDS[self.location]},{int(self.drain)}"


class PicoBrewZymaticProgram(BeerXmlModel, tag="ZYMATIC"):
    # PicoBrew Zymatic/Z specific heating/timing instructions, not part of the BeerXML spec
    # Parse steps first: unordered searches for metadata swap XML siblings,
    # which would otherwise change the brewing sequence.
    steps: list[PicoBrewProgramStep] = element(tag="STEP", default_factory=list)
    mash_temp: LenientFloat = element(tag="MASH_TEMP", default=None)
    mash_time: LenientFloat = element(tag="MASH_TIME", default=None)
    boil_temp: LenientFloat = element(tag="BOIL_TEMP", default=None)
    temperature_unit: TemperatureUnit | None = element(tag="TEMPERATURE_UNIT", default=None)

    @property
    def resolved_temperature_unit(self) -> TemperatureUnit:
        if self.temperature_unit is not None:
            return self.temperature_unit
        # Legacy exports lack a unit marker. Detect once for the whole program:
        # Fahrenheit programs can also contain low chilling or heating targets.
        temperatures = [step.temp for step in self.steps] + [self.mash_temp, self.boil_temp]
        return "F" if any(isinstance(temp, (int, float)) and temp > 110 for temp in temperatures) else "C"
