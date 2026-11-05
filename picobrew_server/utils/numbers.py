import math


def to_float(value: object) -> float | None:
    """Convert lenient BeerXML numeric fields, returning None for missing, invalid, or non-finite values."""
    if value is None:
        return None
    try:
        result = float(str(value))
    except ValueError:
        return None
    return result if math.isfinite(result) else None
