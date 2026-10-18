"""Reading, scaling and merging ingredient lines.

parse() turns "1 1/2 cups flour, sifted" into {"amount": 3/2, "unit": "cup", "item": "flour", "note": "sifted"}.
It understands mixed numbers and unicode fractions (1½), ranges (2-3, 2 to 3), number words (a, one, half, a
dozen), package sizes ("1 (14 oz) can tomatoes"), "juice of 1 lemon", and "to taste" or "as needed".

merge() adds up the same item from several recipes or servings: amounts in the same system and dimension combine
(2 cups + 1 cup = 3 cups, 3 tsp = 1 tbsp), everything else stays side by side ("2 cups + 200 g"); ranges add up as
ranges; "to taste" items appear once.
"""

from __future__ import annotations

import re
from fractions import Fraction

from . import units
from .seed_aisles import item_key

_UNICODE_FRACTIONS = {
    "½": "1/2", "⅓": "1/3", "⅔": "2/3", "¼": "1/4", "¾": "3/4", "⅕": "1/5", "⅖": "2/5", "⅗": "3/5", "⅘": "4/5",
    "⅙": "1/6", "⅚": "5/6", "⅛": "1/8", "⅜": "3/8", "⅝": "5/8", "⅞": "7/8",
}  # fmt: skip
_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "half": Fraction(1, 2), "quarter": Fraction(1, 4),
    "dozen": 12, "a dozen": 12, "half a dozen": 6, "a half": Fraction(1, 2), "one half": Fraction(1, 2),
}  # fmt: skip
_NUMBER = r"(?:\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?|\.\d+)"
_WORD_NUMBER = r"(?:half a dozen|a dozen|a half|one half|" + "|".join(
    sorted((w for w in _WORDS if " " not in w), key=len, reverse=True)) + r")"  # fmt: skip
_AMOUNT = rf"(?:{_NUMBER}|{_WORD_NUMBER})"
# Digits may run straight into a unit ("200g"); words need a space after them, so "apple" isn't "a pple".
_RANGE_RE = re.compile(
    rf"^({_AMOUNT})(?:\s*(?:-|–|to|or)\s*({_AMOUNT}))?(?:(?<=\d)(?=[a-zA-Z(])|(?=\s|$))", re.IGNORECASE
)
_TIMES_SIZE_RE = re.compile(r"^[x×]\s*(\d+(?:\.\d+)?\s*[a-zA-Z]+)\s+")  # "2 x 400g tins"
_TASTE_RE = re.compile(r"\b(to taste|as needed|as required|for serving|for garnish|to serve|optional)\b", re.I)
_SIZES = ("extra-large", "extra large", "large", "medium", "small", "jumbo")
_PREP = ("chopped", "diced", "minced", "sliced", "grated", "shredded", "crushed", "finely", "roughly", "coarsely",
         "freshly", "packed", "heaping", "heaped", "level", "softened", "melted", "beaten", "sifted", "peeled",
         "cubed", "halved", "quartered", "toasted", "divided", "thinly", "lightly")  # fmt: skip
_OF_RE = re.compile(r"^(juice|zest|zest and juice|juice and zest|rind)\s+of\s+(.+)$", re.IGNORECASE)


def _number(text: str) -> Fraction:
    text = text.strip().lower()
    if text in _WORDS:
        return Fraction(_WORDS[text])
    if " " in text:  # 1 1/2
        whole, frac = text.split(None, 1)
        return Fraction(int(whole)) + Fraction(frac)
    return Fraction(text)


def _normalize(text: str) -> str:
    for char, frac in _UNICODE_FRACTIONS.items():
        text = re.sub(rf"(\d){char}", rf"\1 {frac}", text)  # 1½ -> 1 1/2
        text = text.replace(char, frac)
    text = text.replace("⁄", "/").replace("–", "-").replace("—", "-")
    text = re.sub(r"(\d)\s*/\s*(\d)", r"\1/\2", text)
    text = re.sub(r"^[\s\-•*·]+", "", text)  # bullets
    return re.sub(r"\s+", " ", text).strip()


def _match_unit(rest: str):
    """Find a unit at the start of rest: returns (canonical unit, remaining text) or (None, rest)."""
    for alias, unit in units.CASE_SENSITIVE.items():
        match = re.match(rf"{re.escape(alias)}\.?(?=\s|$)", rest)
        if match:
            return unit, rest[match.end():].strip()
    lowered = rest.lower()
    for alias in sorted(units.ALIASES, key=len, reverse=True):
        if lowered.startswith(alias):
            end = len(alias)
            tail = rest[end:]
            if tail.startswith("."):
                end += 1
                tail = rest[end:]
            if tail == "" or tail[0] in " ,)(":
                return units.ALIASES[alias], rest[end:].strip()
    return None, rest


def parse(line: str) -> dict:
    """One ingredient line -> {text, amount, max, unit, item, note, optional, to_taste} (amounts as Fractions)."""
    original = str(line or "").strip()
    text = _normalize(original)
    result = {"text": original, "amount": None, "max": None, "unit": None, "item": "", "note": None,
              "optional": False, "to_taste": False}  # fmt: skip
    notes = []
    if re.match(r"^optional\s*:\s*", text, re.I):
        result["optional"] = True
        text = re.sub(r"^optional\s*:\s*", "", text, flags=re.I)
    if re.search(r"\(\s*optional\s*\)|,\s*optional\b", text, re.I):
        result["optional"] = True
        text = re.sub(r"\(\s*optional\s*\)|,\s*optional\b", "", text, flags=re.I).strip()
    match = _RANGE_RE.match(text)
    if match:
        result["amount"] = _number(match.group(1))
        if match.group(2):
            result["max"] = _number(match.group(2))
        text = text[match.end():].strip()
        # "1 (14 oz) can tomatoes" and "2 x 400g tins tomatoes": the package size is a note
        size = re.match(r"^\(([^)]*)\)\s*", text) or _TIMES_SIZE_RE.match(text)
        if size:
            notes.append(size.group(1).strip())
            text = text[size.end():]
        unit, text = _match_unit(text)
        result["unit"] = unit
        text = re.sub(r"^of\s+", "", text, flags=re.I)
    else:
        of = _OF_RE.match(text)
        if of:
            inner = parse(of.group(2))
            inner["text"] = original
            inner["note"] = ", ".join(n for n in (of.group(1).lower(), inner["note"]) if n)
            return inner
    # Notes: anything in brackets, and anything after the first comma.
    for bracket in re.findall(r"\(([^)]*)\)", text):
        if bracket.strip():
            notes.append(bracket.strip())
    text = re.sub(r"\([^)]*\)", "", text)
    if "," in text:
        text, after = text.split(",", 1)
        if after.strip():
            notes.append(after.strip())
    taste = _TASTE_RE.search(text)
    if taste:
        notes.append(taste.group(1).lower())
        text = _TASTE_RE.sub("", text)
    if result["amount"] is None and _TASTE_RE.search(" ".join([text] + notes)):
        result["to_taste"] = True  # "salt to taste", "Black pepper, as needed"
    words = text.split()
    while words and words[0].lower().rstrip(",") in _PREP:
        notes.append(words.pop(0).lower())
    lowered = " ".join(words).lower()
    for size in _SIZES:
        if lowered.startswith(size + " "):
            notes.insert(0, size)
            words = words[len(size.split()):]
            break
    item = re.sub(r"\s+", " ", " ".join(words)).strip(" .,-")
    trailing = item.rsplit(" ", 1)
    if (result["amount"] is not None and result["unit"] is None and len(trailing) == 2
            and units.ALIASES.get(trailing[1].lower()) in units.COUNTED.keys() | {"can"}):  # fmt: skip
        item, result["unit"] = trailing[0], units.ALIASES[trailing[1].lower()]  # "2 garlic cloves" -> 2 clove garlic
    if result["amount"] is None and result["unit"] is None and not item:
        item = original
    result["item"] = item
    if any(n for n in notes):
        result["note"] = ", ".join(n for n in notes if n)
    return result


def to_record(parsed: dict) -> dict:
    """JSON-safe copy: Fractions as "3/2" strings."""
    out = dict(parsed)
    for key in ("amount", "max"):
        if out.get(key) is not None:
            out[key] = str(out[key])
    return out


def from_record(record: dict) -> dict:
    out = dict(record)
    for key in ("amount", "max"):
        if out.get(key) not in (None, ""):
            out[key] = Fraction(out[key])
        else:
            out[key] = None
    return out


def scale(parsed: dict, factor: Fraction) -> dict:
    """Amounts times factor, shown in the handiest unit (6 3/4 tsp becomes 2 1/4 tbsp, 15/16 cup 15 tbsp)."""
    out = dict(parsed)
    for key in ("amount", "max"):
        if out.get(key) is not None:
            out[key] = out[key] * factor
    unit = out.get("unit")
    if factor != 1 and unit in units.MEASURED and out.get("amount") is not None:
        dimension, system, _ = units.MEASURED[unit]
        new_amount, new_unit = units.best_unit(units.to_base(out["amount"], unit), dimension, system)
        if out.get("max") is not None:
            out["max"] = units.to_base(out["max"], unit) / units.MEASURED[new_unit][2]
        out["amount"], out["unit"] = new_amount, new_unit
    return out


def _plural(item: str) -> str:
    word = item.rsplit(" ", 1)[-1]
    if not word or word[-1:] == "s" or not word.isalpha():
        return item
    if word.endswith(("x", "ch", "sh")) or word in ("tomato", "potato"):
        return item + "es"
    if word.endswith("y") and word[-2:-1] not in "aeiou":
        return item[:-1] + "ies"
    return item + "s"


def describe(parsed: dict) -> str:
    """One ingredient as a line to read: "1 1/2 cups flour (sifted)". Whole things (eggs, cloves, cans) show to
    the nearest half after scaling ("6 1/2 cloves garlic", not "6 3/8")."""
    amount, top, unit = parsed.get("amount"), parsed.get("max"), parsed.get("unit")
    if amount is not None and unit not in units.MEASURED and not units.is_nice(amount, (1, 2, 3, 4)):
        amount = max(Fraction(1, 2), units.nice_fraction(amount, (1, 2)))
        top = units.nice_fraction(top, (1, 2)) if top is not None else None
    qty = units.amount_text(amount, unit, top)
    item = parsed["item"]
    if unit is None and amount is not None and (top or amount) > 1:
        item = _plural(item)  # 3 eggs, not 3 egg
    note = f" ({parsed['note']})" if parsed.get("note") else ""
    return f"{qty} {item}".strip() + note


# --------------------------------------------------------------------------- merging


def _bucket_key(parsed: dict):
    if parsed.get("amount") is None:
        return ("none",)
    dimension, system = units.kind(parsed.get("unit"))
    return (dimension, system)


def merge_amounts(parts: list) -> list:
    """Add up quantities of one item. Returns buckets: [{"kind", "amount", "max", "unit"}] in first-seen order."""
    buckets: dict = {}
    order = []
    for parsed in parts:
        key = _bucket_key(parsed)
        if key not in buckets:
            buckets[key] = {"min": Fraction(0), "max": Fraction(0), "ranged": False, "any": False}
            order.append(key)
        bucket = buckets[key]
        if parsed.get("amount") is None:
            bucket["any"] = True
            continue
        base = units.to_base(parsed["amount"], parsed.get("unit"))
        top = units.to_base(parsed["max"], parsed.get("unit")) if parsed.get("max") is not None else base
        bucket["min"] += base
        bucket["max"] += top
        bucket["ranged"] = bucket["ranged"] or parsed.get("max") is not None
        bucket["any"] = True
    out = []
    for key in order:
        bucket = buckets[key]
        if key == ("none",):
            out.append({"kind": "none", "amount": None, "max": None, "unit": None})
            continue
        dimension, what = key
        if dimension in ("volume", "weight"):
            low, unit = units.best_unit(bucket["min"], dimension, what)
            high = None
            if bucket["ranged"] and bucket["max"] != bucket["min"]:
                factor = units.MEASURED[unit][2]
                high = bucket["max"] / factor
            out.append({"kind": dimension, "amount": low, "max": high, "unit": unit})
        else:
            high = bucket["max"] if bucket["ranged"] and bucket["max"] != bucket["min"] else None
            out.append({"kind": "count", "amount": bucket["min"], "max": high, "unit": what})
    return out


def quantity_text(buckets: list, to_buy: bool = False) -> str:
    """ "2 cups + 200 g". With to_buy, each amount is rounded up to what you'd buy (units.to_buy)."""
    texts = []
    for bucket in buckets:
        if bucket["kind"] == "none":
            continue
        amount, unit, top = bucket["amount"], bucket["unit"], bucket["max"]
        if to_buy:
            amount, unit = units.to_buy(top if top is not None else amount, unit)
            top = None
        texts.append(units.amount_text(amount, unit, top))
    return " + ".join(t for t in texts if t)


def subtract(needed: list, have: list) -> list:
    """What's still needed after what's already bought: per bucket (same system and dimension), the needed amount
    minus the bought one. A bucket without amounts counts as covered once anything was bought. Returns parts."""
    have_buckets = {}
    for bucket in merge_amounts(have):
        kind = bucket["unit"] if bucket["kind"] == "count" else units.kind(bucket["unit"])[1]
        have_buckets[(bucket["kind"], kind)] = bucket
    left = []
    for bucket in merge_amounts(needed):
        if bucket["kind"] == "none":
            if not have:
                left.append({"amount": None, "max": None, "unit": None})
            continue
        key = (bucket["kind"], bucket["unit"] if bucket["kind"] == "count" else units.kind(bucket["unit"])[1])
        got = have_buckets.get(key)
        need_base = units.to_base(bucket["max"] if bucket["max"] is not None else bucket["amount"], bucket["unit"])
        got_base = units.to_base(got["max"] if got["max"] is not None else got["amount"], got["unit"]) if got else 0
        if need_base > got_base:
            rest = need_base - got_base
            unit = bucket["unit"]
            left.append({"amount": rest / units.MEASURED[unit][2] if unit in units.MEASURED else rest, "max": None,
                         "unit": unit})  # fmt: skip
    return left


def merge(parsed_list: list) -> list:
    """Combine ingredient lines by item. Returns [{"key", "item", "quantity", "buckets", "notes", "to_taste"}]."""
    groups: dict = {}
    order = []
    for parsed in parsed_list:
        if not parsed.get("item"):
            continue
        key = item_key(parsed["item"])
        if key not in groups:
            groups[key] = {"key": key, "item": parsed["item"], "parts": [], "notes": [], "to_taste": True}
            order.append(key)
        group = groups[key]
        group["parts"].append(parsed)
        if parsed.get("amount") is not None:
            group["to_taste"] = False
        if parsed.get("note") and parsed["note"] not in group["notes"]:
            group["notes"].append(parsed["note"])
    out = []
    for key in order:
        group = groups[key]
        buckets = merge_amounts(group["parts"])
        out.append({
            "key": key,
            "item": group["item"],
            "quantity": quantity_text(buckets),
            "buckets": [{**b, "amount": str(b["amount"]) if b["amount"] is not None else None,
                         "max": str(b["max"]) if b["max"] is not None else None} for b in buckets],
            "notes": group["notes"],
            "to_taste": group["to_taste"],
        })  # fmt: skip
    return out
