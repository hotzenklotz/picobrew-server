from pybeerxml.base import BeerXmlModel, LenientFloat
from pydantic_xml import element, wrapped


class PicoBrewKegSmartStep(BeerXmlModel, tag="STEP"):
    number: int | None = element(tag="NUMBER", default=None)
    name: str | None = element(tag="NAME", default=None)
    time: LenientFloat = element(tag="TIME", default=None)
    temp: LenientFloat = element(tag="TEMP", default=None)


class PicoBrewKegSmartProgram(BeerXmlModel, tag="KEGSMART"):
    # PicoBrew KegSmart fermentation instructions, not part of the BeerXML spec.
    # Nothing consumes these yet - they are modelled so the block survives a write-back,
    # since pybeerxml silently drops any tag that is not a declared field.
    steps: list[PicoBrewKegSmartStep] = wrapped("STEPS", element(tag="STEP"), default_factory=list)
