"""Recipes, the pantry, cook mode, and sending ingredients to a grocery list.

- Add a recipe by hand, from a saved web page (importer.py), or from a photo the agent read (structured data plus
  anything unclear, which the person confirms).
- "Add to grocery list" is a review first (--dry-run): what's in the pantry is skipped, unknown staples and
  "to taste" items go to a check-at-home pile, and the rest merges into what's already on the list. Each list item
  remembers which recipe or meal asked for how much, so a meal can later be swapped without disturbing the rest
  (mealplan.py). Crossed-off items are never changed.
"""

from __future__ import annotations

import datetime as _dt
import re
from fractions import Fraction

from . import importer, ingredients, shopping, trash, units
from .seed_aisles import item_key
from .util import ToolError, clean_text, fold, load_spec, match_one, now_stamp, parse_stamp, plural, servings_arg

PANTRY_STATUSES = ("in", "low", "out")
STALE_DAYS = 30  # a staple's "in" status older than this is unknown again
QUICK_MINUTES = 30


# --------------------------------------------------------------------------- records


def _minutes(value, field: str):
    if value in (None, ""):
        return None
    text = str(value).strip().lower()
    match = re.fullmatch(r"(?:(\d+)\s*h(?:ours?|rs?)?)?\s*(?:(\d+)\s*m(?:in(?:ute)?s?)?)?", text)
    if text.isdigit():
        return int(text)
    if match and any(match.groups()):
        return int(match.group(1) or 0) * 60 + int(match.group(2) or 0)
    raise ToolError(f"{field} {value!r} isn't a number of minutes.", hint="e.g. 20, 1h30m or 45m.", code="bad_time")


def build_recipe(hh, spec: dict, created_by: str, source: str = "manual") -> dict:
    title = clean_text(spec.get("title"), "recipe title", max_len=120)
    servings = spec.get("servings")
    if servings not in (None, ""):
        try:
            servings = int(servings)
        except (TypeError, ValueError):
            raise ToolError(f"Servings {servings!r} isn't a whole number.", code="bad_servings") from None
        if not 1 <= servings <= 100:
            raise ToolError("Servings must be between 1 and 100.", code="bad_servings")
    lines = [str(line) for line in (spec.get("ingredients") or []) if str(line).strip()]
    steps = [clean_text(step, "step", max_len=2000) for step in (spec.get("steps") or []) if str(step).strip()]
    prep, cook = _minutes(spec.get("prep_min"), "Prep time"), _minutes(spec.get("cook_min"), "Cook time")
    total = _minutes(spec.get("total_min"), "Total time") or ((prep or 0) + (cook or 0) or None)
    tags = []
    for tag in spec.get("tags") or []:
        tag = fold(tag)
        if tag and tag not in tags:
            tags.append(tag)
    return {
        "id": hh.next_id("recipe"),
        "title": title,
        "servings": servings or None,
        "yield": spec.get("yield"),
        "prep_min": prep,
        "cook_min": cook,
        "total_min": total,
        "ingredients": [ingredients.to_record(ingredients.parse(line)) for line in lines],
        "steps": steps,
        "tags": tags,
        "photo": spec.get("photo"),
        "source_url": spec.get("source_url"),
        "source": source,
        "notes": clean_text(spec.get("notes"), "notes", max_len=2000, required=False),
        "unclear": [clean_text(u, "unclear item", max_len=300) for u in (spec.get("unclear") or [])],
        "created_by": created_by,
        "created_at": now_stamp(),
        "cooked": [],
    }


def scaled(recipe: dict, servings: int | None) -> tuple:
    """The recipe's ingredients for a number of servings, and the factor used."""
    factor = Fraction(1)
    if servings:
        if not recipe.get("servings"):
            raise ToolError(
                f"{recipe['title']} doesn't say how many it serves, so it can't be scaled.",
                hint=f'Set it first: fridge recipe edit "{recipe["title"]}" --servings 4',
                code="no_servings",
            )
        factor = Fraction(int(servings), int(recipe["servings"]))
    parts = [ingredients.scale(ingredients.from_record(rec), factor) for rec in recipe["ingredients"]]
    return parts, factor


def recipe_text(recipe: dict, servings: int | None = None) -> str:
    parts, _ = scaled(recipe, servings)
    serves = servings or recipe.get("servings")
    head = [recipe["title"]]
    facts = []
    if serves:
        facts.append(f"serves {serves}")
    if recipe.get("total_min"):
        facts.append(f"{recipe['total_min']} min")
    if facts:
        head[0] += f" ({', '.join(facts)})"
    lines = head + ["Ingredients:"] + [f"  • {ingredients.describe(p)}" for p in parts]
    if recipe.get("steps"):
        lines.append("Steps:")
        lines += [f"  {i}. {step}" for i, step in enumerate(recipe["steps"], 1)]
    if recipe.get("unclear"):
        lines.append("To check: " + "; ".join(recipe["unclear"]))
    return "\n".join(lines)


def find_recipe(ctx, data: dict, query) -> dict:
    ctx.viewer.require("recipes", "view", "see recipes")
    ctx.viewer.require_sees("recipes")
    return match_one(data["recipes"], query, "recipe", key="title", hint="See them with: fridge recipe list")


def recipe_view(recipe: dict, brief: bool = False) -> dict:
    out = {"id": recipe["id"], "title": recipe["title"], "servings": recipe.get("servings"),
           "total_min": recipe.get("total_min"), "tags": recipe.get("tags", [])}  # fmt: skip
    if brief:
        return out
    out.update({
        "prep_min": recipe.get("prep_min"), "cook_min": recipe.get("cook_min"),
        "ingredients": [ingredients.describe(ingredients.from_record(r)) for r in recipe["ingredients"]],
        "steps": recipe.get("steps", []), "source": recipe.get("source"), "source_url": recipe.get("source_url"),
        "photo": recipe.get("photo"), "unclear": recipe.get("unclear", []), "notes": recipe.get("notes"),
        "last_cooked": (recipe.get("cooked") or [None])[-1],
    })  # fmt: skip
    return out


# --------------------------------------------------------------------------- pantry and the grocery review


def pantry_state(pantry: dict, key: str, today: _dt.date) -> str | None:
    """"in", "low", "out", "unknown" (a staple whose status is missing or old), or None (not tracked)."""
    entry = pantry.get(key)
    if not entry:
        return None
    status = entry.get("status")
    if status in ("low", "out"):
        return status
    if status == "in":
        stamp = parse_stamp(entry.get("updated_at"))
        if stamp and (today - stamp.date()).days > STALE_DAYS and entry.get("staple"):
            return "unknown"
        return "in"
    return "unknown" if entry.get("staple") else None


def pantry_for(ctx, shop: dict) -> dict:
    """The pantry, if the person and everyone in the chat may see the grocery module; else nothing is known."""
    if ctx.viewer.can_act("grocery", "view") and ctx.viewer.sees("grocery"):
        return shop["pantry"]
    return {}


def _skipped(key: str, skips: list) -> str | None:
    """The skip word that covers an item: the same item, or one ending with it or holding all its words ("rice"
    leaves out "long grain rice" and "cooked rice")."""
    words = key.split()
    for skip in skips:
        if key == skip or key.endswith(" " + skip) or all(word in words for word in skip.split()):
            return skip
    return None


def _by_hand(item: dict) -> bool:
    """Someone put it on the list themselves: no recipe or meal asked for it (or it was there before they did)."""
    return bool(item.get("manual")) or not item.get("sources")


def _spoonful(need: dict) -> bool:
    """Only a spoonful or a pinch is needed: nobody buys 2 tbsp of oil, so it's checked at home instead."""
    parts = need.get("parts") or []
    return bool(parts) and all(part.get("unit") in units.SPOONS for part in parts)


def review(hh, shop: dict, lst: dict, needs: list, skip=(), pantry: dict | None = None) -> dict:
    """Decide what to do with each needed item (from ingredients.merge with "sources"). Nothing is changed here.

    add: not on the list yet; merge: joins an open item a recipe or meal already put on the list; covered: on the
    list already because someone added it by hand (its amount is theirs and isn't changed); pantry: marked in, so
    skipped; check: a staple with an unknown status, a "to taste" item or a spoonful, for the person to check at
    home; skip: they said (and unmatched_skip: what they said to leave out that matched nothing).
    """
    today = hh.today()
    skips = [key for key in (item_key(s) for s in skip) if key]
    used = set()
    plan = {"add": [], "merge": [], "covered": [], "pantry": [], "check": [], "skip": []}
    open_items = shopping.items_of(shop, lst["id"], crossed=False)
    for need in needs:
        key = need["key"]
        hit = _skipped(key, skips)
        if hit:
            plan["skip"].append(need)
            used.add(hit)
            continue
        state = pantry_state(shop["pantry"] if pantry is None else pantry, key, today)
        if state == "in":
            plan["pantry"].append(need)
            continue
        existing = [i for i in open_items if item_key(i["name"]) == key]
        if existing and _by_hand(existing[0]):
            plan["covered"].append(dict(need, into=existing[0]["id"]))
            continue
        if state == "unknown" or (need["to_taste"] and state not in ("low", "out")):
            plan["check"].append(need)
            continue
        if not existing and _spoonful(need) and state not in ("low", "out"):
            plan["check"].append(need)
            continue
        if existing:
            plan["merge"].append(dict(need, into=existing[0]["id"]))
        else:
            plan["add"].append(need)
    plan["unmatched_skip"] = [s for s in skips if s not in used]
    return plan


_NOT_FOR_SHOPPING = set(ingredients._PREP) | {"drained", "rinsed", "trimmed", "deveined", "pitted", "seeded",
                                              "stemmed", "torn", "at", "room", "temperature", "for", "garnish",
                                              "serving", "to", "taste", "serve", "and", "or"}  # fmt: skip


def _shopping_note(notes: list) -> str | None:
    """A recipe note worth having in the shop ("400g", "large"), without the cooking words ("minced", "beaten")."""
    for note in notes or []:
        kept = [part.strip() for part in note.split(",")
                if part.strip() and not all(word in _NOT_FOR_SHOPPING for word in part.lower().split())]  # fmt: skip
        if kept:
            return ", ".join(kept)[:120]
    return None


def item_quantity(item: dict) -> str | None:
    """An item's quantity from what was typed plus what each recipe or meal asked for, rounded up to what you'd
    buy. A typed amount that reads as a quantity ("2", "2 lbs") adds up with the rest; anything else ("a big bag")
    is kept as it was typed. Needs an item added by hand already covered ("absorbed") don't change it."""
    parts, typed = [], item.get("manual_qty")
    if typed:
        reading = ingredients.parse(f"{typed} x")
        if reading["amount"] is not None and reading["item"] == "x":
            parts.append(reading)
            typed = None
    for source in item.get("sources", []):
        if not source.get("absorbed"):
            parts += [ingredients.from_record(rec) for rec in source.get("parts", [])]
    merged = ingredients.quantity_text(ingredients.merge_amounts(parts), to_buy=True) if parts else ""
    pieces = [p for p in (typed, merged) if p]
    return " + ".join(pieces) or None


def apply_review(hh, shop: dict, lst: dict, plan: dict, actor_id: str) -> list:
    """Add and merge the planned items. Returns the items touched."""
    touched = []
    stamp = now_stamp()
    for need in plan.get("covered", []):  # on the list by hand: noted against it, its amount left alone
        item = next((i for i in shop["items"] if i["id"] == need["into"]), None)
        if item is None:
            continue
        if not item.get("sources") and "manual_qty" not in item:
            item["manual"] = True
            item["manual_qty"] = item.get("qty")
        source = {"kind": need["source_kind"], "ref": need["source_ref"], "label": need["source_label"],
                  "parts": need["parts"], "absorbed": True}  # fmt: skip
        same = (source["kind"], source["ref"])
        item["sources"] = [s for s in item.get("sources", []) if (s["kind"], s["ref"]) != same]
        item["sources"].append(source)
        touched.append(item)
    for need in plan["add"] + plan["merge"]:
        source = {"kind": need["source_kind"], "ref": need["source_ref"], "label": need["source_label"],
                  "parts": need["parts"]}  # fmt: skip
        item = None
        if need.get("into"):
            item = next((i for i in shop["items"] if i["id"] == need["into"] and not i.get("crossed_at")), None)
        if item is None:  # another need in this same batch may have just put it on the list
            open_items = shopping.items_of(shop, lst["id"], crossed=False)
            item = next((i for i in open_items if item_key(i["name"]) == need["key"]), None)
        if item is None:
            result = shopping.add_one(hh, shop, lst, need["item"], actor_id, again=True, stamp=stamp)
            item = result["item"]
            item["manual_qty"] = None
            if any(part.get("unit") == "can" for part in need.get("parts", [])):
                item["aisle"] = shopping.match_aisle("Canned", lst) or item["aisle"]  # tinned tomatoes, not fresh
        else:
            if not item.get("sources") and "manual_qty" not in item:
                item["manual"] = True  # someone put it on the list by hand: meal changes never remove it
                item["manual_qty"] = item.get("qty")
        item.setdefault("sources", [])
        same = (source["kind"], source["ref"])
        item["sources"] = [s for s in item["sources"] if (s["kind"], s["ref"]) != same]
        item["sources"].append(source)
        item["qty"] = item_quantity(item)
        if not item.get("note"):
            item["note"] = _shopping_note(need.get("notes"))
        touched.append(item)
    return touched


def needs_from_parts(parts: list, kind: str, ref: str, label: str) -> list:
    """Merged needs with where they came from (so the list can later be changed by source)."""
    out = []
    for group in ingredients.merge(parts):
        mine = [p for p in parts if p.get("item") and item_key(p["item"]) == group["key"]]
        out.append(dict(group, source_kind=kind, source_ref=ref, source_label=label,
                        parts=[ingredients.to_record(p) for p in mine if p.get("amount") is not None]))  # fmt: skip
    return out


def combined(needs: list) -> list:
    """Needs for the same item from several meals as one line, the way the list will show it."""
    groups, order = {}, []
    for need in needs:
        key = need["key"]
        if key not in groups:
            groups[key] = dict(need, parts=list(need.get("parts") or []), labels=[need.get("source_label")])
            order.append(key)
        else:
            group = groups[key]
            group["parts"] = group["parts"] + list(need.get("parts") or [])
            group["labels"].append(need.get("source_label"))
            group["to_taste"] = group["to_taste"] and need["to_taste"]
    out = []
    for key in order:
        group = groups[key]
        parts = [ingredients.from_record(p) for p in group["parts"]]
        group["quantity"] = ingredients.quantity_text(ingredients.merge_amounts(parts), to_buy=True) if parts else ""
        out.append(group)
    return out


def plan_count(plan: dict) -> int:
    """How many lines the list gains or changes."""
    return len(combined(plan["add"])) + len(combined(plan["merge"]))


def plan_text(plan: dict, lst: dict) -> str:
    lines = []
    if plan["add"] or plan["merge"]:
        lines.append(f"Adding to {lst['name']}:")
        lines += [f"  + {n['item']} {n['quantity']}".rstrip() for n in combined(plan["add"])]
        lines += [f"  + {n['item']} {n['quantity']} (joins what's already on the list)".rstrip()
                  for n in combined(plan["merge"])]  # fmt: skip
    for key, words in (("covered", "Already on the list (added by hand, so its amount is left as it is)"),
                       ("pantry", "Skipping, already in the pantry"), ("check", "Check at home"),
                       ("skip", "Leaving out")):  # fmt: skip
        if plan.get(key):
            lines.append(f"{words}: " + ", ".join(n["item"] for n in combined(plan[key])))
    if plan.get("unmatched_skip"):
        lines.append("Nothing matched (not left out): " + ", ".join(plan["unmatched_skip"]))
    return "\n".join(lines) or "Nothing to add."


def plan_summary(plan: dict) -> dict:
    out = {key: [{"item": n["item"], "quantity": n["quantity"]} for n in combined(value)]
           for key, value in plan.items() if key != "unmatched_skip"}  # fmt: skip
    out["unmatched_skip"] = plan.get("unmatched_skip", [])
    return out


# --------------------------------------------------------------------------- commands


def cmd_add(ctx, args) -> dict:
    ctx.viewer.require("recipes", "edit", "add recipes")
    ctx.viewer.require_sees("recipes")
    spec = load_spec(args.spec) if args.spec else {}
    if not isinstance(spec, dict):
        raise ToolError("The spec must be a JSON object.", code="bad_spec")
    for key, value in (("title", args.title), ("servings", args.servings), ("prep_min", args.prep),
                       ("cook_min", args.cook), ("notes", args.notes), ("photo", args.photo)):  # fmt: skip
        if value is not None:
            spec[key] = value
    spec["ingredients"] = list(spec.get("ingredients") or []) + list(args.ingredient or [])
    spec["steps"] = list(spec.get("steps") or []) + list(args.step or [])
    spec["tags"] = list(spec.get("tags") or []) + list(args.tag or [])
    spec["unclear"] = list(spec.get("unclear") or []) + list(args.unclear or [])
    hh = ctx.household
    with hh.transaction(dry_run=args.dry_run):
        data = hh.data("recipes")
        recipe = build_recipe(hh, spec, ctx.member["id"], source=args.source)
        if not recipe["ingredients"]:
            raise ToolError("A recipe needs at least one ingredient.", hint='Add --ingredient "2 cups flour"',
                            code="missing")  # fmt: skip
        data["recipes"].append(recipe)
        hh.touch("recipes")
        hh.log("recipe.add", ctx.member["id"], recipe=recipe["id"], source=args.source)
    counts = f"{plural(len(recipe['ingredients']), 'ingredient')}, {plural(len(recipe['steps']), 'step')}"
    summary = f"{'Would save' if args.dry_run else 'Saved'} {recipe['title']} ({counts})."
    out = {"recipe": recipe_view(recipe), "text": recipe_text(recipe), "dry_run": args.dry_run, "summary": summary}
    if recipe["unclear"]:
        out["ask"] = "Please check: " + "; ".join(recipe["unclear"])
        out["summary"] += " A few things need checking."
    return out


def cmd_import(ctx, args) -> dict:
    ctx.viewer.require("recipes", "edit", "add recipes")
    ctx.viewer.require_sees("recipes")
    found = importer.from_file(args.page, args.url)
    hh = ctx.household
    with hh.transaction(dry_run=args.dry_run):
        data = hh.data("recipes")
        same = [r for r in data["recipes"] if (found.get("source_url") and r.get("source_url") == found["source_url"])
                or fold(r["title"]) == fold(found["title"])]  # fmt: skip
        if same and not args.again:
            raise ToolError(f"{same[0]['title']} is already saved ({same[0]['id']}).",
                            hint="Use it as it is, or add --again to save a second copy.", code="exists")  # fmt: skip
        recipe = build_recipe(hh, found, ctx.member["id"], source="link")
        data["recipes"].append(recipe)
        hh.touch("recipes")
        hh.log("recipe.import", ctx.member["id"], recipe=recipe["id"])
    unread = [i["text"] for i in recipe["ingredients"] if not i.get("item")]
    counts = f"{plural(len(recipe['ingredients']), 'ingredient')}, {plural(len(recipe['steps']), 'step')}"
    summary = f"{'Would save' if args.dry_run else 'Saved'} {recipe['title']} from the page ({counts})."
    out = {"recipe": recipe_view(recipe), "text": recipe_text(recipe), "dry_run": args.dry_run, "summary": summary}
    if not recipe.get("servings"):
        out["ask"] = "The page doesn't say how many it serves. How many does it make?"
    if unread:
        out["unread"] = unread
    return out


def cmd_list(ctx, args) -> dict:
    data = ctx.household.data("recipes")
    ctx.viewer.require("recipes", "view", "see recipes")
    ctx.viewer.require_sees("recipes")
    recipes = data["recipes"]
    if args.tag:
        recipes = [r for r in recipes if fold(args.tag) in r.get("tags", [])]
    if args.search:
        q = fold(args.search)
        recipes = [
            r for r in recipes if q in fold(r["title"]) or any(q in fold(i.get("item")) for i in r["ingredients"])
        ]
    if args.quick:
        recipes = [r for r in recipes if r.get("total_min") and r["total_min"] <= QUICK_MINUTES]
    views = [recipe_view(r, brief=True) for r in sorted(recipes, key=lambda r: fold(r["title"]))]
    text = "\n".join(f"{v['title']}" + (f" ({v['total_min']} min)" if v["total_min"] else "") for v in views)
    return {"recipes": views, "text": text or "No recipes yet.", "summary": f"{plural(len(views), 'recipe')}."}


def cmd_show(ctx, args) -> dict:
    data = ctx.household.data("recipes")
    recipe = find_recipe(ctx, data, args.recipe)
    parts, factor = scaled(recipe, args.servings)
    view = recipe_view(recipe)
    view["ingredients"] = [ingredients.describe(p) for p in parts]
    if args.servings:
        view["scaled_to"] = args.servings
    return {"recipe": view, "text": recipe_text(recipe, args.servings), "summary": recipe["title"]}


def cmd_edit(ctx, args) -> dict:
    ctx.viewer.require("recipes", "edit", "change recipes")
    hh = ctx.household
    with hh.transaction(dry_run=args.dry_run):
        data = hh.data("recipes")
        recipe = find_recipe(ctx, data, args.recipe)
        changed = []
        if args.title:
            recipe["title"] = clean_text(args.title, "recipe title", max_len=120)
            changed.append("title")
        if args.servings is not None:
            if not 1 <= args.servings <= 100:
                raise ToolError("Servings must be between 1 and 100.", code="bad_servings")
            recipe["servings"] = args.servings
            changed.append("servings")
        for key, value, label in (("prep_min", args.prep, "prep time"), ("cook_min", args.cook, "cook time")):
            if value is not None:
                recipe[key] = _minutes(value, label)
                recipe["total_min"] = (recipe.get("prep_min") or 0) + (recipe.get("cook_min") or 0) or None
                changed.append(label)
        for line in args.add_ingredient or []:
            recipe["ingredients"].append(ingredients.to_record(ingredients.parse(line)))
            changed.append("ingredients")
        for spec in args.set_ingredient or []:
            number, _, line = spec.partition("=")
            index = int(number) - 1 if number.strip().isdigit() else -1
            if not 0 <= index < len(recipe["ingredients"]) or not line.strip():
                raise ToolError(f"{spec!r} should look like N=new line (N from 1 to {len(recipe['ingredients'])}).",
                                code="usage")  # fmt: skip
            recipe["ingredients"][index] = ingredients.to_record(ingredients.parse(line))
            changed.append("ingredients")
        for number in sorted(args.remove_ingredient or [], reverse=True):
            if not 1 <= number <= len(recipe["ingredients"]):
                raise ToolError(f"There's no ingredient {number}.", code="usage")
            recipe["ingredients"].pop(number - 1)
            changed.append("ingredients")
        for step in args.add_step or []:
            recipe["steps"].append(clean_text(step, "step", max_len=2000))
            changed.append("steps")
        for tag in args.tag or []:
            if fold(tag) not in recipe["tags"]:
                recipe["tags"].append(fold(tag))
                changed.append("tags")
        for tag in args.untag or []:
            recipe["tags"] = [t for t in recipe["tags"] if t != fold(tag)]
            changed.append("tags")
        if args.notes is not None:
            recipe["notes"] = clean_text(args.notes, "notes", max_len=2000, required=False)
            changed.append("notes")
        if args.photo:
            recipe["photo"] = args.photo
            changed.append("photo")
        if args.checked:
            recipe["unclear"] = []
            changed.append("checked")
        if not changed:
            raise ToolError("Nothing to change.", hint="See: fridge recipe edit --help", code="usage")
        hh.touch("recipes")
        hh.log("recipe.edit", ctx.member["id"], recipe=recipe["id"], fields=sorted(set(changed)))
    return {"recipe": recipe_view(recipe), "dry_run": args.dry_run,
            "summary": f"Updated {recipe['title']}: {', '.join(sorted(set(changed)))}."}  # fmt: skip


def cmd_delete(ctx, args) -> dict:
    ctx.viewer.require("recipes", "edit", "delete recipes")
    hh = ctx.household
    with hh.transaction():
        data = hh.data("recipes")
        recipe = find_recipe(ctx, data, args.recipe)
        data["recipes"] = [r for r in data["recipes"] if r["id"] != recipe["id"]]
        data.setdefault("cooking", {})
        data["cooking"] = {m: c for m, c in data["cooking"].items() if c.get("recipe") != recipe["id"]}
        undo = trash.put(hh, "recipe", [recipe], ctx.member["id"])
        hh.touch("recipes")
        hh.log("recipe.delete", ctx.member["id"], recipe=recipe["id"])
    return {"summary": f"Deleted {recipe['title']}. {trash.kept_for(hh)}", "undo": undo}


def _grocery_list(ctx, shop: dict, query) -> dict:
    return shopping.find_list(ctx, shop, query, need="edit")


def cmd_to_list(ctx, args) -> dict:
    hh = ctx.household
    with hh.transaction(dry_run=args.dry_run):
        recipes = hh.data("recipes")
        recipe = find_recipe(ctx, recipes, args.recipe)
        shop = hh.data("shopping")
        lst = _grocery_list(ctx, shop, args.list)
        parts, _ = scaled(recipe, args.servings)
        label = recipe["title"] + (f" (for {args.servings})" if args.servings else "")
        needs = needs_from_parts(parts, "recipe", recipe["id"], label)
        plan = review(hh, shop, lst, needs, skip=shopping.split_items(args.skip), pantry=pantry_for(ctx, shop))
        touched = apply_review(hh, shop, lst, plan, ctx.member["id"])
        hh.touch("shopping")
        hh.log("recipe.to_list", ctx.member["id"], recipe=recipe["id"], list=lst["id"], items=len(touched))
    verb = "Would add" if args.dry_run else "Added"
    summary = f"{verb} {plural(plan_count(plan), 'item')} from {recipe['title']} to {lst['name']}."
    if plan["check"]:
        summary += " Check at home: " + ", ".join(n["item"] for n in combined(plan["check"])) + "."
    if plan.get("unmatched_skip"):
        unmatched = ", ".join(repr(s) for s in plan["unmatched_skip"])
        summary += f" Nothing matched {unmatched}, so nothing was left out for it."
    return {"recipe": recipe["id"], "list": lst["name"], "plan": plan_summary(plan), "text": plan_text(plan, lst),
            "dry_run": args.dry_run, "summary": summary}  # fmt: skip


def cmd_cook(ctx, args) -> dict:
    """Step-by-step cook mode for the person talking: start, next, back, a step number, or stop."""
    hh = ctx.household
    ctx.viewer.require("recipes", "view", "see recipes")  # checked on every step, not just the first
    ctx.viewer.require_sees("recipes")
    if args.done:
        ctx.viewer.require("recipes", "edit", "note that a recipe was cooked")
    with hh.transaction():
        data = hh.data("recipes")
        cooking = data.setdefault("cooking", {})
        state = cooking.get(ctx.member["id"])
        if args.recipe:
            recipe = find_recipe(ctx, data, args.recipe)
            moving = args.next or args.back or args.step is not None or args.stop
            if not (state and state.get("recipe") == recipe["id"] and moving):  # naming it again just carries on
                state = {"recipe": recipe["id"], "step": 0, "servings": args.servings, "started_at": now_stamp()}
        elif not state:
            raise ToolError("You're not cooking anything right now.", hint='Start with: fridge recipe cook "Chili"',
                            code="not_cooking")  # fmt: skip
        recipe = next((r for r in data["recipes"] if r["id"] == state["recipe"]), None)
        if recipe is None:
            cooking.pop(ctx.member["id"], None)
            hh.touch("recipes")
            raise ToolError("That recipe was deleted.", code="not_found")
        steps = recipe.get("steps") or []
        if args.stop:
            cooking.pop(ctx.member["id"], None)
            if args.done:
                recipe.setdefault("cooked", []).append(hh.today().isoformat())
            hh.touch("recipes")
            return {"summary": f"Finished cooking {recipe['title']}." if args.done else "Cook mode closed."}
        if args.next:
            state["step"] = min(state["step"] + 1, len(steps))
        elif args.back:
            state["step"] = max(state["step"] - 1, 0)
        elif args.step is not None:
            state["step"] = max(0, min(args.step, len(steps)))
        cooking[ctx.member["id"]] = state
        hh.touch("recipes")
    number = state["step"]
    out = {"recipe": recipe["title"], "step": number, "of": len(steps)}
    if number == 0:
        parts, _ = scaled(recipe, state.get("servings"))
        out["ingredients"] = [ingredients.describe(p) for p in parts]
        ready = "\n".join(f"  • {i}" for i in out["ingredients"])
        then = 'Say "next" for step 1.' if steps else "No steps are saved for this one. Say \"done\" when it's ready."
        out["text"] = f"Get these ready:\n{ready}\n{then}"
    elif number <= len(steps):
        out["text"] = f"Step {number} of {len(steps)}: {steps[number - 1]}"
        if number == len(steps):
            out["text"] += "\nThat's the last step. Say \"done\" when it's ready."
    out["summary"] = out["text"].splitlines()[0]
    return out


def cmd_cooked(ctx, args) -> dict:
    ctx.viewer.require("recipes", "edit", "change recipes")
    hh = ctx.household
    with hh.transaction():
        data = hh.data("recipes")
        recipe = find_recipe(ctx, data, args.recipe)
        recipe.setdefault("cooked", []).append(hh.today().isoformat())
        hh.touch("recipes")
    return {"summary": f"Noted: {recipe['title']} cooked today."}


# --------------------------------------------------------------------------- pantry commands


def _pantry_access(ctx, need: str) -> None:
    ctx.viewer.require("grocery", need, "see the pantry" if need == "view" else "change the pantry")
    ctx.viewer.require_sees("grocery")


def cmd_pantry_show(ctx, args) -> dict:
    _pantry_access(ctx, "view")
    hh = ctx.household
    pantry = hh.data("shopping")["pantry"]
    today = hh.today()
    rows = []
    for key, entry in sorted(pantry.items()):
        rows.append({"item": entry.get("name") or key, "status": pantry_state(pantry, key, today) or "untracked",
                     "staple": bool(entry.get("staple"))})  # fmt: skip
    text = "\n".join(f"{r['item']}: {r['status']}" + (" (staple)" if r["staple"] else "") for r in rows)
    return {"pantry": rows, "text": text or "The pantry is empty.", "summary": f"{plural(len(rows), 'pantry item')}."}


def cmd_pantry_set(ctx, args) -> dict:
    _pantry_access(ctx, "edit")
    hh = ctx.household
    names = shopping.split_items(args.items)
    if not names:
        raise ToolError("Which items?", code="missing")
    with hh.transaction():
        pantry = hh.data("shopping")["pantry"]
        for name in names:
            key = item_key(name)
            entry = pantry.setdefault(key, {"name": name.lower()})
            if args.forget:
                pantry.pop(key, None)
                continue
            if args.status:
                entry["status"] = args.status
                entry["updated_at"] = now_stamp()
            if args.staple:
                entry["staple"] = True
            if args.not_staple:
                entry["staple"] = False
        hh.touch("shopping")
        hh.log("pantry.set", ctx.member["id"], count=len(names))
    what = "forgot" if args.forget else (f"marked {args.status}" if args.status else "updated")
    return {"summary": f"Pantry: {what} {', '.join(names)}."}


def register(cli) -> None:
    grp = cli.group("recipe", "Recipes: add (by hand, from a saved page or a photo), show, scale, cook, to a list.")
    p = grp.add(
        "add",
        "Save a recipe by hand, or from structured data (--spec) the agent read from a photo of a recipe card.",
        [
            'fridge recipe add --title "Pancakes" --servings 4 --ingredient "1 1/2 cups flour" '
            '--ingredient "2 eggs" --step "Whisk everything" --tag breakfast',
            "fridge recipe add --spec card.json --source photo --photo /workspace/photos/card.jpg",
        ],
        cmd_add,
    )
    p.add_argument("--title")
    p.add_argument("--servings", type=servings_arg)
    p.add_argument("--prep", help="Prep time, e.g. 15 or 1h15m")
    p.add_argument("--cook", help="Cook time")
    p.add_argument("--ingredient", action="append", help="One ingredient line; repeat")
    p.add_argument("--step", action="append", help="One step; repeat")
    p.add_argument("--tag", action="append")
    p.add_argument("--notes")
    p.add_argument("--photo", help="Path of a saved photo")
    p.add_argument("--unclear", action="append", help="Something the person must confirm (photo imports)")
    p.add_argument("--spec", help="JSON: title, servings, ingredients, steps, tags, prep_min, cook_min, unclear")
    p.add_argument("--source", choices=("manual", "photo"), default="manual")
    p.add_argument("--dry-run", action="store_true")
    p = grp.add(
        "import",
        "Read a recipe from a web page the agent saved (schema.org Recipe data). No network.",
        ["fridge recipe import /workspace/pages/chili.html --url https://example.com/chili"],
        cmd_import,
    )
    p.add_argument("page", help="Path of the saved page")
    p.add_argument("--url", help="Where the page came from")
    p.add_argument("--again", action="store_true", help="Save it even if it looks like one already saved")
    p.add_argument("--dry-run", action="store_true")
    p = grp.add(
        "list",
        "List recipes, by tag, search words or quick ones.",
        ["fridge recipe list", "fridge recipe list --tag dinner --quick", "fridge recipe list --search chicken"],
        cmd_list,
    )
    p.add_argument("--tag")
    p.add_argument("--search")
    p.add_argument("--quick", action="store_true", help=f"{QUICK_MINUTES} minutes or less")
    p = grp.add("show", "Show a recipe, scaled with --servings.", ['fridge recipe show Chili --servings 6'], cmd_show)
    p.add_argument("recipe")
    p.add_argument("--servings", type=servings_arg)
    p = grp.add(
        "edit",
        "Change a recipe: title, servings, times, ingredients (add, set N=..., remove N), steps, tags, notes.",
        ['fridge recipe edit Chili --servings 6', 'fridge recipe edit Chili --set-ingredient "3=2 tsp cumin"',
         "fridge recipe edit Pancakes --checked"],
        cmd_edit,
    )  # fmt: skip
    p.add_argument("recipe")
    p.add_argument("--title")
    p.add_argument("--servings", type=servings_arg)
    p.add_argument("--prep")
    p.add_argument("--cook")
    p.add_argument("--add-ingredient", action="append")
    p.add_argument("--set-ingredient", action="append", help="N=new line")
    p.add_argument("--remove-ingredient", action="append", type=int, help="Ingredient number")
    p.add_argument("--add-step", action="append")
    p.add_argument("--tag", action="append")
    p.add_argument("--untag", action="append")
    p.add_argument("--notes")
    p.add_argument("--photo")
    p.add_argument("--checked", action="store_true", help="The person has checked the unclear bits")
    p.add_argument("--dry-run", action="store_true")
    p = grp.add("delete", "Delete a recipe.", ["fridge recipe delete Chili"], cmd_delete)
    p.add_argument("recipe")
    p = grp.add(
        "to-list",
        "Send a recipe's ingredients to a grocery list. Run with --dry-run first to review: pantry items are "
        "skipped, unknown staples and \"to taste\" items go to a check-at-home pile, duplicates merge.",
        ['fridge recipe to-list Chili --dry-run', 'fridge recipe to-list Chili --servings 6 --skip "salt, cumin"'],
        cmd_to_list,
    )
    p.add_argument("recipe")
    p.add_argument("--list", help="Which list (default: the household's grocery list)")
    p.add_argument("--servings", type=servings_arg)
    p.add_argument("--skip", action="append", help="Items to leave out (comma list)")
    p.add_argument("--dry-run", action="store_true")
    p = grp.add(
        "cook",
        "Cook mode, one step at a time: start with a recipe, then --next, --back, --step N, or --stop (--done).",
        ['fridge recipe cook Chili', "fridge recipe cook --next", "fridge recipe cook --stop --done"],
        cmd_cook,
    )
    p.add_argument("recipe", nargs="?")
    p.add_argument("--servings", type=servings_arg)
    p.add_argument("--next", action="store_true")
    p.add_argument("--back", action="store_true")
    p.add_argument("--step", type=int)
    p.add_argument("--stop", action="store_true")
    p.add_argument("--done", action="store_true", help="With --stop: note that it was cooked today")
    p = grp.add("cooked", "Note that a recipe was cooked today (helps meal ideas).", ["fridge recipe cooked Chili"],
                cmd_cooked)  # fmt: skip
    p.add_argument("recipe")

    pan = cli.group("pantry", "The pantry: what's in, low or out, and staples to check before shopping.")
    pan.add("show", "Show what the pantry knows.", ["fridge pantry show"], cmd_pantry_show)
    p = pan.add(
        "set",
        "Mark items in, low or out, mark staples (things usually kept), or forget items.",
        ['fridge pantry set "rice, flour, olive oil" --status in --staple', "fridge pantry set milk --status out",
         "fridge pantry set kale --forget"],
        cmd_pantry_set,
    )  # fmt: skip
    p.add_argument("items", nargs="+")
    p.add_argument("--status", choices=PANTRY_STATUSES)
    p.add_argument("--staple", action="store_true")
    p.add_argument("--not-staple", action="store_true")
    p.add_argument("--forget", action="store_true")
