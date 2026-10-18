"""Cooking units: what each one measures, how to add them up, and how to show amounts people can measure.

Amounts are exact Fractions, so 1/3 cup x 3 is exactly 1 cup. Conversions happen only inside one system and one
dimension: teaspoons, tablespoons and cups together; millilitres and litres together; grams and kilograms together;
ounces and pounds together. Never metric to US, and never weight to volume (a cup of flour has no fixed weight).
"""

from __future__ import annotations

from fractions import Fraction

# canonical unit -> (dimension, system, size in the base unit of that dimension and system)
MEASURED = {
    "tsp": ("volume", "us", Fraction(1)),
    "tbsp": ("volume", "us", Fraction(3)),
    "fl oz": ("volume", "us", Fraction(6)),
    "cup": ("volume", "us", Fraction(48)),
    "pint": ("volume", "us", Fraction(96)),
    "quart": ("volume", "us", Fraction(192)),
    "gallon": ("volume", "us", Fraction(768)),
    "ml": ("volume", "metric", Fraction(1)),
    "cl": ("volume", "metric", Fraction(10)),
    "dl": ("volume", "metric", Fraction(100)),
    "l": ("volume", "metric", Fraction(1000)),
    "mg": ("weight", "metric", Fraction(1, 1000)),
    "g": ("weight", "metric", Fraction(1)),
    "kg": ("weight", "metric", Fraction(1000)),
    "oz": ("weight", "us", Fraction(1)),
    "lb": ("weight", "us", Fraction(16)),
}

# Units that only add up with themselves: 2 cloves + 1 clove, but never cloves + cans.
COUNTED = {
    "clove": "cloves", "can": "cans", "tin": "tins", "jar": "jars", "pack": "packs", "packet": "packets",
    "bunch": "bunches", "sprig": "sprigs", "slice": "slices", "stick": "sticks", "head": "heads",
    "piece": "pieces", "pinch": "pinches", "dash": "dashes", "handful": "handfuls", "sheet": "sheets",
    "bag": "bags", "bottle": "bottles", "box": "boxes", "carton": "cartons", "container": "containers",
    "cube": "cubes", "drop": "drops", "leaf": "leaves", "stalk": "stalks", "rib": "ribs", "fillet": "fillets",
    "ear": "ears", "knob": "knobs", "sachet": "sachets", "loaf": "loaves", "rasher": "rashers",
}  # fmt: skip

_LABELS = {"cup": ("cup", "cups"), "pint": ("pint", "pints"), "quart": ("quart", "quarts"),
           "gallon": ("gallon", "gallons")}  # fmt: skip

# Words people write -> canonical unit. Matched longest first. "T" and "t" are matched case-sensitively.
ALIASES = {
    "teaspoon": "tsp", "teaspoons": "tsp", "tsp": "tsp", "tsps": "tsp", "tspn": "tsp",
    "tablespoon": "tbsp", "tablespoons": "tbsp", "tbsp": "tbsp", "tbsps": "tbsp", "tbs": "tbsp", "tbl": "tbsp",
    "tbls": "tbsp", "tblsp": "tbsp", "tbspn": "tbsp",
    "cup": "cup", "cups": "cup", "c": "cup",
    "fluid ounce": "fl oz", "fluid ounces": "fl oz", "fl oz": "fl oz", "fl. oz": "fl oz", "floz": "fl oz",
    "pint": "pint", "pints": "pint", "pt": "pint", "pts": "pint",
    "quart": "quart", "quarts": "quart", "qt": "quart", "qts": "quart",
    "gallon": "gallon", "gallons": "gallon", "gal": "gallon", "gals": "gallon",
    "ml": "ml", "millilitre": "ml", "millilitres": "ml", "milliliter": "ml", "milliliters": "ml", "cc": "ml",
    "cl": "cl", "centilitre": "cl", "centilitres": "cl", "centiliter": "cl", "centiliters": "cl",
    "dl": "dl", "decilitre": "dl", "decilitres": "dl", "deciliter": "dl", "deciliters": "dl",
    "l": "l", "litre": "l", "litres": "l", "liter": "l", "liters": "l", "ltr": "l", "ltrs": "l",
    "mg": "mg", "milligram": "mg", "milligrams": "mg",
    "g": "g", "gram": "g", "grams": "g", "gramme": "g", "grammes": "g", "gm": "g", "gms": "g",
    "kg": "kg", "kgs": "kg", "kilo": "kg", "kilos": "kg", "kilogram": "kg", "kilograms": "kg",
    "oz": "oz", "ounce": "oz", "ounces": "oz",
    "lb": "lb", "lbs": "lb", "pound": "lb", "pounds": "lb",
    "package": "pack", "packages": "pack", "pkg": "pack", "pkgs": "pack", "pack": "pack", "packs": "pack",
}  # fmt: skip
for _unit, _plural in COUNTED.items():
    ALIASES.setdefault(_unit, _unit)
    ALIASES.setdefault(_plural, _unit)
ALIASES["tin"] = ALIASES["tins"] = "can"  # a tin and a can are the same thing on a shopping list
SPOONS = {"tsp", "tbsp", "pinch", "dash", "drop"}  # amounts too small to buy: they're checked at home
CASE_SENSITIVE = {"T": "tbsp", "Tb": "tbsp", "TB": "tbsp", "t": "tsp"}


def kind(unit: str | None) -> tuple:
    """How a unit adds up: ("volume", "us"), ("weight", "metric"), ("count", "clove"), or ("count", None)."""
    if unit in MEASURED:
        dimension, system, _ = MEASURED[unit]
        return (dimension, system)
    return ("count", unit)


def to_base(amount: Fraction, unit: str | None) -> Fraction:
    return amount * MEASURED[unit][2] if unit in MEASURED else amount


def label(unit: str | None, amount: Fraction | None) -> str:
    if unit is None:
        return ""
    plural = amount is not None and amount > 1
    if unit in _LABELS:
        return _LABELS[unit][1 if plural else 0]
    if unit in COUNTED:
        return COUNTED[unit] if plural else unit
    return unit


def nice_fraction(value: Fraction, denominators=(1, 2, 3, 4, 8)) -> Fraction:
    """The closest fraction a cook can measure (halves, thirds, quarters, eighths)."""
    best = None
    for den in denominators:
        candidate = Fraction(round(value * den), den)
        if best is None or abs(candidate - value) < abs(best - value):
            best = candidate
    return best


def is_nice(value: Fraction, denominators=(1, 2, 3, 4, 8)) -> bool:
    return value.denominator in denominators


def fraction_text(value: Fraction) -> str:
    """1 1/2, 3/4, 2. Exact when measurable, else rounded to eighths or thirds."""
    if not is_nice(value):
        value = nice_fraction(value)
    whole, rest = divmod(value.numerator, value.denominator)
    if rest == 0:
        return str(whole)
    frac = f"{rest}/{value.denominator}"
    return f"{whole} {frac}" if whole else frac


def decimal_text(value: Fraction, places: int = 2) -> str:
    """Metric amounts in decimals: 1.5, 250, 0.75."""
    rounded = round(float(value), places)
    text = f"{rounded:.{places}f}".rstrip("0").rstrip(".")
    return text or "0"


def best_unit(base: Fraction, dimension: str, system: str) -> tuple:
    """Pick the unit to show a total in: 3 tsp -> 1 tbsp, 12 tbsp -> 3/4 cup, 1500 g -> 1.5 kg, 24 oz -> 1 1/2 lb."""
    if system == "us" and dimension == "volume":
        cups = base / 48
        if base >= 12 and is_nice(cups):
            return cups, "cup"
        tbsp = base / 3
        if base >= 3 and is_nice(tbsp, (1, 2, 4)):  # 6 3/4 tsp reads better as 2 1/4 tbsp
            return tbsp, "tbsp"
        if base >= 12:
            return cups, "cup"
        return base, "tsp"
    if system == "us" and dimension == "weight":
        pounds = base / 16
        if base >= 16 and is_nice(pounds, (1, 2, 4)):
            return pounds, "lb"
        return base, "oz"
    if dimension == "volume":  # metric
        return (base / 1000, "l") if base >= 1000 else (base, "ml")
    return (base / 1000, "kg") if base >= 1000 else (base, "g")


def to_buy(amount: Fraction, unit: str | None) -> tuple:
    """An amount rounded up to something you can buy: whole onions, eggs and cans, metric amounts to the next 5 g
    or ml (187.5 ml -> 190 ml), ounces to the next whole one, cups to the next quarter."""
    if unit in MEASURED:
        dimension, system, _ = MEASURED[unit]
        base = to_base(amount, unit)
        if system == "metric":
            step = Fraction(5) if base >= 20 else Fraction(1)
            base = -(-base // step) * step
        elif dimension == "weight":
            base = Fraction(-(-base // 1))
        elif base >= 12:  # a cup or more: to the next quarter cup
            base = Fraction(-(-base // 12) * 12)
        return best_unit(base, dimension, system)
    return Fraction(-(-amount // 1)), unit


def amount_text(amount: Fraction | None, unit: str | None, amount_max: Fraction | None = None) -> str:
    """ "1 1/2 cups", "2-3 cloves", "250 g", "1.5 kg", "3"."""
    if amount is None:
        return ""
    metric = unit in MEASURED and MEASURED[unit][1] == "metric"
    show = decimal_text if metric else fraction_text
    text = show(amount)
    if amount_max is not None and amount_max != amount:
        text += f"-{show(amount_max)}"
    unit_label = label(unit, amount_max or amount)
    return f"{text} {unit_label}".strip()
