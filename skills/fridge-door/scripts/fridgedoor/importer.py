"""Read a recipe from a saved web page: the schema.org Recipe data (JSON-LD) most recipe sites include.

The agent fetches the page with its own web tools and saves it; this module only reads the file. No network.
Handles @graph containers, lists of types, HowToStep and HowToSection instructions, and ISO 8601 times (PT1H30M).
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

from .util import ToolError

MAX_BYTES = 10 * 1024 * 1024
_SCRIPT_RE = re.compile(
    r"<script[^>]*type\s*=\s*[\"']?application/ld\+json[^>]*>(.*?)</script>", re.IGNORECASE | re.DOTALL
)
_TAG_RE = re.compile(r"<[^>]+>")


def clean(text) -> str:
    """Strip tags and entities and collapse spaces."""
    if text is None:
        return ""
    if isinstance(text, (int, float)):
        return str(text)
    out = html.unescape(_TAG_RE.sub(" ", str(text)))
    return re.sub(r"\s+", " ", out).strip()


def minutes(value) -> int | None:
    """ISO 8601 durations (PT1H30M, P0DT45M, PT90M) to whole minutes; None if absent or unreadable."""
    if not value or not isinstance(value, str):
        return None
    match = re.fullmatch(
        r"P(?:(\d+)D)?(?:T(?:(\d+(?:\.\d+)?)H)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?)?", value.strip().upper()
    )
    if not match or not any(match.groups()):
        return None
    days, hours, mins, secs = (float(g) if g else 0 for g in match.groups())
    total = days * 1440 + hours * 60 + mins + secs / 60
    return int(round(total)) if total > 0 else None


def servings(value) -> tuple:
    """recipeYield -> (servings as an int or None, the yield as text)."""
    if isinstance(value, list):
        texts = [clean(v) for v in value if clean(v)]
        for text in texts:
            number = re.search(r"\d+", text)
            if number:
                return int(number.group()), max(texts, key=len)
        return None, (texts[0] if texts else "")
    text = clean(value)
    number = re.search(r"\d+", text)
    return (int(number.group()) if number else None), text


def _types(node) -> set:
    kind = node.get("@type")
    if isinstance(kind, list):
        return {str(k) for k in kind}
    return {str(kind)} if kind else set()


def _find_recipes(node, found: list) -> None:
    if isinstance(node, list):
        for item in node:
            _find_recipes(item, found)
    elif isinstance(node, dict):
        if "Recipe" in _types(node) or any(t.endswith("/Recipe") for t in _types(node)):
            found.append(node)
        for key in ("@graph", "mainEntity", "mainEntityOfPage", "itemListElement", "hasPart"):
            if key in node and isinstance(node[key], (list, dict)):
                _find_recipes(node[key], found)


def _steps(value) -> list:
    """Instructions in any of the shapes sites use, as a flat list of steps."""
    out = []
    if isinstance(value, str):
        parts = [p for p in re.split(r"\n+|(?<=\.)\s{2,}", html.unescape(value)) if clean(p)]
        return [clean(p) for p in parts]
    if isinstance(value, dict):
        value = [value]
    for item in value or []:
        if isinstance(item, str):
            if clean(item):
                out.append(clean(item))
        elif isinstance(item, dict):
            kinds = _types(item)
            if "HowToSection" in kinds or ("itemListElement" in item and "text" not in item):
                inner = _steps(item.get("itemListElement") or [])
                name = clean(item.get("name"))
                if inner and name:
                    inner[0] = f"{name}: {inner[0]}"
                out += inner
            else:
                text = clean(item.get("text") or item.get("name") or item.get("description"))
                if text:
                    out.append(text)
    return out


def _tags(node) -> list:
    tags = []
    for key in ("keywords", "recipeCategory", "recipeCuisine"):
        value = node.get(key)
        parts = value if isinstance(value, list) else re.split(r",", str(value)) if value else []
        for part in parts:
            tag = clean(part).lower()
            if tag and tag not in tags and len(tag) <= 40:
                tags.append(tag)
    return tags[:12]


def _image(value):
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, dict):
        value = value.get("url") or value.get("contentUrl")
    return clean(value) or None


def from_html(text: str, url: str | None = None) -> dict:
    """The first schema.org Recipe in a page, as plain fields. Raises no_recipe_data when there isn't one."""
    found: list = []
    for block in _SCRIPT_RE.findall(text):
        raw = block.strip()
        raw = re.sub(r"^\s*<!--|-->\s*$", "", raw)
        raw = re.sub(r"^\s*//\s*<!\[CDATA\[|//\s*\]\]>\s*$", "", raw)
        raw = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", raw)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        _find_recipes(data, found)
    if not found:
        raise ToolError(
            "That page has no recipe data I can read.",
            hint="Read the page yourself and add the recipe with: fridge recipe add --spec '{...}' "
            "(title, servings, ingredients, steps), then ask the person to check it.",
            code="no_recipe_data",
        )
    node = max(found, key=lambda n: len(n.get("recipeIngredient") or n.get("ingredients") or []))
    count, yield_text = servings(node.get("recipeYield") or node.get("yield"))
    ingredients = node.get("recipeIngredient") or node.get("ingredients") or []
    if isinstance(ingredients, str):
        ingredients = [ingredients]
    lines = [clean(i) for i in ingredients if clean(i)]
    prep, cook, total = (minutes(node.get(k)) for k in ("prepTime", "cookTime", "totalTime"))
    return {
        "title": clean(node.get("name")) or "Untitled recipe",
        "servings": count,
        "yield": yield_text or None,
        "prep_min": prep,
        "cook_min": cook,
        "total_min": total or ((prep or 0) + (cook or 0) or None),
        "ingredients": lines,
        "steps": _steps(node.get("recipeInstructions")),
        "tags": _tags(node),
        "image_url": _image(node.get("image")),
        "source_url": clean(node.get("url")) or url,
        "description": clean(node.get("description"))[:500] or None,
    }


def from_file(path: str, url: str | None = None) -> dict:
    file = Path(path).expanduser()
    if not file.is_file():
        raise ToolError(f"There's no saved page at {path}.", hint="Save the page first, then pass its path.",
                        code="no_file")  # fmt: skip
    if file.stat().st_size > MAX_BYTES:
        raise ToolError("That page is too big to read (over 10 MB).", code="too_big")
    return from_html(file.read_text(encoding="utf-8", errors="replace"), url)
