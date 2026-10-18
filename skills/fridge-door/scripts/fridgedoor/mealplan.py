"""The weekly meal plan, and the grocery list it keeps up to date.

- Each day has meals (breakfast, lunch, dinner, snack) holding a recipe, quick text ("eating out"), or leftovers
  of an earlier meal (a real slot: Today asks whether they're still good, rather than assuming).
- Nights you can cook: a long cook isn't planned on an evening the calendar already fills (calendar events win),
  unless the person says so (--anyway).
- "Make this week's grocery list" merges every planned recipe, skips what the pantry has, and lists unknown staples
  to check at home. After that, changing one meal changes only that meal's share of the list; crossed-off items
  are never touched.
"""

from __future__ import annotations

import datetime as _dt

from . import access, events, ingredients, recipes, shopping
from .seed_aisles import item_key
from .util import ToolError, clean_text, fold, match_one, now_stamp, plural, servings_arg

MEALS = ("breakfast", "lunch", "dinner", "snack")
LONG_COOK_MINUTES = 45
DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _week_start(hh) -> int:
    from .todos import week_start

    return week_start(hh)


def week_of(hh, day: _dt.date) -> _dt.date:
    return day - _dt.timedelta(days=(day.weekday() - _week_start(hh)) % 7)


def _date(hh, value) -> _dt.date:
    return hh.date(value) if value else hh.today()


def _meal(value) -> str:
    meal = fold(value or "dinner")
    if meal not in MEALS:
        raise ToolError(f"{value!r} isn't a meal.", hint="Use breakfast, lunch, dinner or snack.", code="bad_meal")
    return meal


def entries_between(plan: dict, first: _dt.date, last: _dt.date):
    """(date, meal, entry) for every planned entry in the range, in order."""
    day = first
    while day <= last:
        for meal in MEALS:
            for entry in plan.get(day.isoformat(), {}).get(meal, []):
                yield day, meal, entry
        day += _dt.timedelta(days=1)


def find_entry(plan: dict, entry_id: str):
    for day, meals in plan.items():
        for meal, entries in meals.items():
            for entry in entries:
                if entry["id"] == entry_id:
                    return day, meal, entry
    return None


def entry_label(hh, day: str, meal: str, entry: dict, recipes_by_id: dict) -> str:
    if entry.get("recipe"):
        recipe = recipes_by_id.get(entry["recipe"])
        name = recipe["title"] if recipe else "a deleted recipe"
    elif entry.get("leftovers_of"):
        found = find_entry(hh.data("mealplan")["plan"], entry["leftovers_of"])
        if found and found[2].get("recipe") and recipes_by_id.get(found[2]["recipe"]):
            src = recipes_by_id[found[2]["recipe"]]["title"]
        else:
            src = (found[2].get("text") if found else None) or "an earlier meal"
        src_day = _dt.date.fromisoformat(found[0]) if found else None
        name = f"Leftover {src}" + (f" from {DAY_NAMES[src_day.weekday()]}" if src_day else "")
    else:
        name = entry.get("text") or "?"
    return name


def entry_view(hh, day: str, meal: str, entry: dict, recipes_by_id: dict) -> dict:
    out = {"id": entry["id"], "date": day, "meal": meal, "label": entry_label(hh, day, meal, entry, recipes_by_id)}
    if entry.get("recipe"):
        recipe = recipes_by_id.get(entry["recipe"])
        out["recipe"] = entry["recipe"]
        out["servings"] = entry.get("servings") or (recipe or {}).get("servings")
        out["total_min"] = (recipe or {}).get("total_min")
    if entry.get("leftovers_of"):
        out["leftovers_of"] = entry["leftovers_of"]
        out["question"] = f"{out['label']}: still good? If not, plan something else."
    return out


def _require(ctx, need: str) -> None:
    ctx.viewer.require("meal_plan", need, "see the meal plan" if need == "view" else "change the meal plan")
    ctx.viewer.require_sees("meal_plan")


# --------------------------------------------------------------------------- the grocery list for a week


def week_needs(hh, ctx, first: _dt.date) -> list:
    """Needs (with sources) for every planned recipe in the week starting at first."""
    plan = hh.data("mealplan")["plan"]
    by_id = {r["id"]: r for r in hh.data("recipes")["recipes"]}
    needs = []
    for day, meal, entry in entries_between(plan, first, first + _dt.timedelta(days=6)):
        recipe = by_id.get(entry.get("recipe"))
        if not recipe:
            continue
        servings = entry.get("servings") if recipe.get("servings") else None
        parts, _ = recipes.scaled(recipe, servings)
        label = f"{recipe['title']} ({DAY_NAMES[day.weekday()]} {meal})"
        needs += recipes.needs_from_parts(parts, "meal", entry["id"], label)
    return needs


def sync_week(hh, ctx, first: _dt.date, lst: dict, skip=()) -> dict:
    """Bring the week's share of the list up to date. Only that share changes: meals added, removed or swapped
    since last time add or take away exactly their amounts. Crossed-off items are never touched."""
    shop = hh.data("shopping")
    weeks = hh.data("mealplan").setdefault("weeks", {})
    record = weeks.get(first.isoformat(), {})
    old_refs = set(record.get("refs", []))
    removed = []
    for item in list(shopping.items_of(shop, lst["id"], crossed=False)):
        sources = item.get("sources") or []
        keep = [s for s in sources if not (s["kind"] == "meal" and s["ref"] in old_refs)]
        if len(keep) == len(sources):
            continue
        item["sources"] = keep
        if not keep and not item.get("manual") and not item.get("manual_qty"):
            shop["items"] = [i for i in shop["items"] if i["id"] != item["id"]]
            removed.append(item["name"])
        else:
            item["qty"] = recipes.item_quantity(item)
    # What's been bought for this week's meals (crossed off) counts against what the week still needs, item by
    # item, whichever meal it was bought for: swapping meals around after the shop doesn't put it all back.
    needs = week_needs(hh, ctx, first)
    week_refs = old_refs | {n["source_ref"] for n in needs}
    bought: dict = {}
    for item in shopping.items_of(shop, lst["id"], crossed=True):
        for source in item.get("sources") or []:
            if source["kind"] == "meal" and source["ref"] in week_refs:
                bought.setdefault(item_key(item["name"]), []).extend(
                    ingredients.from_record(part) for part in source.get("parts", []))  # fmt: skip
    still = []
    for need in needs:
        have = bought.get(need["key"])
        if have is None:
            still.append(need)
            continue
        wanted = [ingredients.from_record(part) for part in need.get("parts", [])]
        if not wanted:  # "to taste": bought already
            continue
        left = ingredients.subtract(wanted, have)
        bought[need["key"]] = ingredients.subtract(have, wanted)
        if left:
            parts = [ingredients.to_record(dict(part, item=need["item"])) for part in left]
            still.append(dict(need, parts=parts, quantity=ingredients.quantity_text(ingredients.merge_amounts(left))))
    plan = recipes.review(hh, shop, lst, still, skip=skip, pantry=recipes.pantry_for(ctx, shop))
    recipes.apply_review(hh, shop, lst, plan, ctx.member["id"])
    re_added = {n["item"] for n in plan["add"] + plan["merge"]}
    weeks[first.isoformat()] = {
        "list": lst["id"],
        "refs": sorted({n["source_ref"] for n in week_needs(hh, ctx, first)}),
        "skip": sorted(set(record.get("skip", [])) | {item_key(s) for s in skip}),
        "updated_at": now_stamp(),
    }
    hh.touch("shopping")
    hh.touch("mealplan")
    return {"plan": plan, "removed": [r for r in removed if r not in re_added]}


def _maybe_sync(hh, ctx, day: _dt.date) -> dict | None:
    """If this week's list was already made, keep it in step with the change just made, and say exactly which
    lines changed."""
    first = week_of(hh, day)
    record = hh.data("mealplan").get("weeks", {}).get(first.isoformat())
    if not record:
        return None
    shop = hh.data("shopping")
    lst = next((x for x in shop["lists"] if x["id"] == record["list"] and not x.get("deleted_at")), None)
    if lst is None or not ctx.viewer.can_act(shopping.module_of(lst), "edit"):
        return None

    def lines() -> dict:  # by item, so a line replaced by an equal one isn't "taken off and added"
        return {item_key(i["name"]): (i["name"], i.get("qty"))
                for i in shopping.items_of(shop, lst["id"], crossed=False)}  # fmt: skip

    before = lines()
    sync_week(hh, ctx, first, lst, skip=record.get("skip", []))
    after = lines()
    return {"list": lst["name"],
            "added": [after[k][0] for k in after if k not in before],
            "changed": [after[k][0] for k in after if k in before and after[k][1] != before[k][1]],
            "removed": [before[k][0] for k in before if k not in after]}  # fmt: skip


# --------------------------------------------------------------------------- commands


def _busy_check(ctx, day: _dt.date, recipe: dict | None, anyway: bool) -> list:
    """Refuse a long cook on a busy evening unless the person says so; returns the busy events for the reply."""
    if not recipe or not ctx.viewer.can_act("calendar", "view"):
        return []
    busy = events.busy_evenings(ctx, day, day).get(day.isoformat(), [])
    long_cook = (recipe.get("total_min") or 0) >= LONG_COOK_MINUTES
    if busy and long_cook and not anyway:
        quick = [r["title"] for r in ctx.household.data("recipes")["recipes"]
                 if r.get("total_min") and r["total_min"] <= recipes.QUICK_MINUTES][:5]  # fmt: skip
        raise ToolError(
            f"{DAY_NAMES[day.weekday()]} evening is busy ({', '.join(busy)}), and {recipe['title']} takes "
            f"{recipe['total_min']} minutes.",
            hint=("Quick ones: " + ", ".join(quick) + ". " if quick else "") + "Pick a quicker meal, another night, "
            "or add --anyway to plan it regardless.",
            code="busy_night",
            busy=busy,
            quick=quick,
        )
    return busy


def cmd_plan(ctx, args) -> dict:
    _require(ctx, "edit")
    hh = ctx.household
    day = _date(hh, args.date)
    meal = _meal(args.meal)
    if sum(bool(x) for x in (args.recipe, args.text, args.leftovers_of)) != 1:
        raise ToolError("Plan one thing: --recipe, --text or --leftovers-of.", code="usage")
    with hh.transaction(dry_run=args.dry_run):
        data = hh.data("mealplan")
        recipe = None
        entry = {"id": hh.next_id("meal"), "recipe": None, "text": None, "servings": args.servings,
                 "leftovers_of": None, "added_by": ctx.member["id"], "added_at": now_stamp()}  # fmt: skip
        if args.recipe:
            ctx.viewer.require("recipes", "view", "use recipes")
            recipe = match_one(hh.data("recipes")["recipes"], args.recipe, "recipe", key="title",
                               hint="See them with: fridge recipe list")  # fmt: skip
            entry["recipe"] = recipe["id"]
        elif args.text:
            entry["text"] = clean_text(args.text, "meal", max_len=120)
        else:
            src_day = _date(hh, args.leftovers_of)
            source = next((e for _, m, e in entries_between(data["plan"], src_day, src_day)
                           if m in (meal, "dinner", "lunch") and not e.get("leftovers_of")), None)  # fmt: skip
            if source is None:
                raise ToolError(f"Nothing is planned on {hh.day(src_day)} to have leftovers of.", code="not_found")
            entry["leftovers_of"] = source["id"]
        busy = _busy_check(ctx, day, recipe, args.anyway)
        slot = data["plan"].setdefault(day.isoformat(), {}).setdefault(meal, [])
        replaced = []
        if args.replace:
            replaced = [e["id"] for e in slot]
            slot.clear()
        slot.append(entry)
        moved_leftovers = []
        if replaced and not entry.get("leftovers_of"):  # leftovers of the old meal are now leftovers of the new one
            for when, _, other in entries_between(data["plan"], day, day + _dt.timedelta(days=14)):
                if other.get("leftovers_of") in replaced:
                    other["leftovers_of"] = entry["id"]
                    moved_leftovers.append(when)
        hh.touch("mealplan")
        synced = _maybe_sync(hh, ctx, day)
        hh.log("meal.plan", ctx.member["id"], date=day.isoformat(), meal=meal, entry=entry["id"])
        by_id = {r["id"]: r for r in hh.data("recipes")["recipes"]}
        view = entry_view(hh, day.isoformat(), meal, entry, by_id)
    soon = {0: " (today)", 1: " (tomorrow)"}.get((day - hh.today()).days, "")
    summary = f"{'Would plan' if args.dry_run else 'Planned'} {view['label']} for {meal} on {hh.day(day)}{soon}"
    if busy:
        summary += f" (busy evening: {', '.join(busy)})"
    summary += "."
    if moved_leftovers:
        serves = f" (serves {view['servings']})" if view.get("servings") else ""
        days = ", ".join(hh.day(d) for d in moved_leftovers)
        summary += f" The leftovers on {days} now come from {view['label']}{serves}: check there'll be enough."
    if _changed(synced):
        summary += f" Updated {synced['list']}: " + _delta_words(synced) + "."
    return {"entry": view, "replaced": replaced or None, "list_update": synced, "dry_run": args.dry_run,
            "summary": summary}  # fmt: skip


def _delta_words(synced: dict) -> str:
    parts = []
    for key, words in (("added", "added"), ("changed", "changed the amount of"), ("removed", "took off")):
        names = list(dict.fromkeys(synced.get(key) or []))
        if names:
            parts.append(f"{words} " + ", ".join(names))
    return "; ".join(parts) or "no change"


def _changed(synced: dict | None) -> bool:
    return bool(synced and (synced["added"] or synced.get("changed") or synced["removed"]))


def cmd_remove(ctx, args) -> dict:
    _require(ctx, "edit")
    hh = ctx.household
    with hh.transaction():
        data = hh.data("mealplan")
        if args.entry:
            found = find_entry(data["plan"], args.entry)
            if not found:
                raise ToolError(f"No planned meal {args.entry}.", code="not_found")
            day, meal, _ = found
            ids = {args.entry}
        else:
            day = _date(hh, args.date).isoformat()
            meal = _meal(args.meal)
            ids = {e["id"] for e in data["plan"].get(day, {}).get(meal, [])}
            if not ids:
                raise ToolError(f"Nothing is planned for {day} {meal}.", code="not_found")
        slot = data["plan"].get(day, {}).get(meal, [])
        data["plan"][day][meal] = [e for e in slot if e["id"] not in ids]
        orphans = []  # leftovers of a meal that's no longer planned can't happen either
        for when, meals in data["plan"].items():
            for name, entries in meals.items():
                for other in list(entries):
                    if other.get("leftovers_of") in ids:
                        entries.remove(other)
                        orphans.append(f"{when} {name}")
        hh.touch("mealplan")
        synced = _maybe_sync(hh, ctx, _dt.date.fromisoformat(day))
        hh.log("meal.remove", ctx.member["id"], date=day, meal=meal)
    summary = f"Cleared {meal} on {hh.day(_dt.date.fromisoformat(day))}."
    if orphans:
        summary += f" Also cleared its leftovers ({', '.join(orphans)})."
    if _changed(synced):
        summary += f" Updated {synced['list']}: " + _delta_words(synced) + "."
    return {"list_update": synced, "summary": summary}


def cmd_swap(ctx, args) -> dict:
    args.replace = True
    args.leftovers_of = getattr(args, "leftovers_of", None)
    return cmd_plan(ctx, args)


def cmd_week(ctx, args) -> dict:
    _require(ctx, "view")
    hh = ctx.household
    first = week_of(hh, _date(hh, args.date))
    plan = hh.data("mealplan")["plan"]
    by_id = {r["id"]: r for r in hh.data("recipes")["recipes"]}
    busy = events.busy_evenings(ctx, first, first + _dt.timedelta(days=6)) if ctx.viewer.sees("calendar") else {}
    days, lines = [], [f"Meals for the week of {hh.day(first)}"]
    for offset in range(7):
        day = first + _dt.timedelta(days=offset)
        meals = []
        for meal in MEALS:
            for entry in plan.get(day.isoformat(), {}).get(meal, []):
                meals.append(entry_view(hh, day.isoformat(), meal, entry, by_id))
        flag = " (busy evening)" if day.isoformat() in busy else ""
        days.append({"date": day.isoformat(), "meals": meals, "busy": busy.get(day.isoformat(), [])})
        text = "; ".join(f"{m['meal'].capitalize()}: {m['label']}" for m in meals) or "nothing planned"
        lines.append(f"{hh.day(day)}{flag}: {text}")
    record = hh.data("mealplan").get("weeks", {}).get(first.isoformat())
    return {"week": first.isoformat(), "days": days, "list_made": bool(record), "text": "\n".join(lines),
            "summary": f"Meal plan for the week of {hh.day(first)}."}  # fmt: skip


def cmd_to_list(ctx, args) -> dict:
    _require(ctx, "view")
    ctx.viewer.require("recipes", "view", "use the recipes in the plan")
    ctx.viewer.require_sees("recipes")
    hh = ctx.household
    first = week_of(hh, _date(hh, args.week))
    with hh.transaction(dry_run=args.dry_run):
        shop = hh.data("shopping")
        lst = shopping.find_list(ctx, shop, args.list, need="edit")
        result = sync_week(hh, ctx, first, lst, skip=shopping.split_items(args.skip))
        hh.log("meal.to_list", ctx.member["id"], week=first.isoformat(), list=lst["id"])
    plan = result["plan"]
    verb = "Would add" if args.dry_run else "Added"
    summary = f"{verb} {plural(recipes.plan_count(plan), 'item')} for the week of {hh.day(first)} to {lst['name']}."
    if plan["pantry"]:
        summary += f" Skipped {plural(len(recipes.combined(plan['pantry'])), 'pantry item')}."
    if plan["check"]:
        summary += " Check at home: " + ", ".join(n["item"] for n in recipes.combined(plan["check"])) + "."
    if plan.get("unmatched_skip"):
        unmatched = ", ".join(repr(s) for s in plan["unmatched_skip"])
        summary += f" Nothing on the plan matched {unmatched}, so nothing was left out for it."
    return {"week": first.isoformat(), "list": lst["name"], "plan": recipes.plan_summary(plan),
            "removed": result["removed"], "text": recipes.plan_text(plan, lst), "dry_run": args.dry_run,
            "summary": summary}  # fmt: skip


def cmd_nights(ctx, args) -> dict:
    _require(ctx, "view")
    ctx.viewer.require_sees("calendar")
    hh = ctx.household
    first = week_of(hh, _date(hh, args.week))
    last = first + _dt.timedelta(days=6)
    busy = events.busy_evenings(ctx, first, last)
    plan = hh.data("mealplan")["plan"]
    by_id = {r["id"]: r for r in hh.data("recipes")["recipes"]}
    nights, lines = [], []
    for offset in range(7):
        day = first + _dt.timedelta(days=offset)
        dinners = [e for e in plan.get(day.isoformat(), {}).get("dinner", [])]
        long_ones = [by_id[e["recipe"]]["title"] for e in dinners if e.get("recipe") in by_id
                     and (by_id[e["recipe"]].get("total_min") or 0) >= LONG_COOK_MINUTES]  # fmt: skip
        state = "busy" if day.isoformat() in busy else "free"
        conflict = state == "busy" and bool(long_ones)
        nights.append({"date": day.isoformat(), "evening": state, "busy_with": busy.get(day.isoformat(), []),
                       "long_cooks": long_ones, "conflict": conflict})  # fmt: skip
        note = f" — busy: {', '.join(busy[day.isoformat()])}" if state == "busy" else " — free to cook"
        if conflict:
            note += f" ⚠️ {', '.join(long_ones)} is a long cook"
        lines.append(f"{hh.day(day)}{note}")
    return {"nights": nights, "text": "\n".join(lines),
            "summary": f"{plural(len(busy), 'busy evening')} this week; "
                       f"{plural(sum(n['conflict'] for n in nights), 'long cook')} on a busy night."}  # fmt: skip


def ideas(ctx, args) -> dict:
    """Meal ideas from the household's own recipes: what the pantry already covers, what hasn't been cooked lately,
    and quick ones for busy nights. Suggestions only; the person decides."""
    ctx.viewer.require("recipes", "view", "see recipes")
    ctx.viewer.require_sees("recipes")
    hh = ctx.household
    day = _date(hh, getattr(args, "date", None))
    shop = hh.data("shopping")
    pantry = recipes.pantry_for(ctx, shop)
    knows_pantry = bool(pantry) or (ctx.viewer.can_act("grocery", "view") and ctx.viewer.sees("grocery"))
    today = hh.today()
    busy = bool(events.busy_evenings(ctx, day, day)) if ctx.viewer.sees("calendar") else False
    recent = set()
    plan = hh.data("mealplan")["plan"]
    for _, _, entry in entries_between(plan, day - _dt.timedelta(days=14), day + _dt.timedelta(days=6)):
        if entry.get("recipe"):
            recent.add(entry["recipe"])
    scored = []
    for recipe in hh.data("recipes")["recipes"]:
        measurable = [i for i in recipe["ingredients"] if i.get("item") and i.get("amount")]
        have = [i for i in measurable if recipes.pantry_state(pantry, item_key(i["item"]), today) == "in"]
        coverage = len(have) / len(measurable) if measurable else 0
        cooked = recipe.get("cooked") or []
        last = _dt.date.fromisoformat(cooked[-1]) if cooked else None
        days_since = (today - last).days if last else 999
        quick = bool(recipe.get("total_min") and recipe["total_min"] <= recipes.QUICK_MINUTES)
        score = coverage * 3 + min(days_since, 60) / 30
        score += (2 if busy and quick else 0) - (3 if recipe["id"] in recent else 0)
        reasons = []
        if measurable and knows_pantry:
            reasons.append(f"you have {len(have)} of {len(measurable)} ingredients")
        if quick:
            reasons.append(f"quick ({recipe['total_min']} min)")
        if last:
            reasons.append(f"last cooked {days_since} days ago")
        elif not cooked:
            reasons.append("not cooked yet")
        if recipe["id"] in recent:
            reasons.append("already planned or cooked recently")
        scored.append((score, recipe, reasons))
    scored.sort(key=lambda s: (-s[0], fold(s[1]["title"])))
    top = [{"recipe": r["id"], "title": r["title"], "why": ", ".join(why)} for _, r, why in scored[:5]]
    text = "\n".join(f"• {t['title']} — {t['why']}" for t in top) or "No recipes saved yet."
    head = f"Ideas for {DAY_NAMES[day.weekday()]}" + (" (a busy evening: quick ones first)" if busy else "")
    summary = head + ". These are suggestions; plan one with: fridge meal plan <date> --recipe <name>"
    return {"ideas": top, "busy": busy, "text": f"{head}\n{text}", "summary": summary}


def cmd_ideas(ctx, args) -> dict:
    return ideas(ctx, args)


def _meals_layer(ctx, first: _dt.date, last: _dt.date) -> list:
    if not ctx.viewer.sees("meal_plan"):
        return []
    hh = ctx.household
    plan = hh.data("mealplan")["plan"]
    by_id = {r["id"]: r for r in hh.data("recipes")["recipes"]}
    out = []
    for day, meal, entry in entries_between(plan, first, last):
        label = entry_label(hh, day.isoformat(), meal, entry, by_id)
        out.append({"event": entry["id"], "date": day.isoformat(), "end_date": None, "time": None, "end_time": None,
                    "all_day": True, "title": f"{meal.capitalize()}: {label}", "type": "meal", "icon": "🍽️",
                    "location": None, "members": [], "color": None, "repeats": False, "layer": "meals"})  # fmt: skip
    return out


def tonight(ctx, member, day: _dt.date) -> dict | None:
    """Today's section: tonight's dinner (and a leftovers question)."""
    if not ctx.viewer.sees("meal_plan") or not access.in_their_day(member, "meal_plan"):
        return None
    hh = ctx.household
    plan = hh.data("mealplan")["plan"]
    by_id = {r["id"]: r for r in hh.data("recipes")["recipes"]}
    dinners = [entry_view(hh, day.isoformat(), "dinner", e, by_id)
               for e in plan.get(day.isoformat(), {}).get("dinner", [])]  # fmt: skip
    if not dinners:
        return {"title": "🍽️ Dinner", "items": [], "lines": ["Nothing planned for dinner."]}
    lines = [d["label"] + (f" (serves {d['servings']})" if d.get("servings") else "")
             + (" — still good? If not, plan something else." if d.get("question") else "") for d in dinners]  # fmt: skip
    return {"title": "🍽️ Dinner", "items": dinners, "lines": lines}


def register(cli) -> None:
    events.LAYERS["meals"] = _meals_layer
    grp = cli.group("meal", "The meal plan: plan the week, keep the grocery list in step, busy nights, ideas.")
    p = grp.add(
        "plan",
        "Plan a meal: a recipe, quick text, or leftovers of an earlier meal. A long cook on a busy evening is "
        "refused unless --anyway. If the week's list was made, it's updated by this meal's share only.",
        ['fridge meal plan monday --recipe Chili --servings 6', 'fridge meal plan friday --text "Eating out"',
         "fridge meal plan tuesday --leftovers-of monday", "fridge meal plan saturday --meal lunch --recipe Pancakes"],
        cmd_plan,
    )  # fmt: skip
    p.add_argument("date")
    p.add_argument("--meal", default="dinner", help="breakfast, lunch, dinner (default) or snack")
    p.add_argument("--recipe")
    p.add_argument("--text")
    p.add_argument("--leftovers-of", help="The day whose meal this is leftovers of")
    p.add_argument("--servings", type=servings_arg)
    p.add_argument("--replace", action="store_true", help="Replace what's planned for that meal")
    p.add_argument("--anyway", action="store_true", help="Plan a long cook on a busy evening anyway")
    p.add_argument("--dry-run", action="store_true")
    p = grp.add("swap", "Replace a planned meal (the grocery list changes by the difference only).",
                ['fridge meal swap wednesday --recipe "Fish tacos"'], cmd_swap)  # fmt: skip
    p.add_argument("date")
    p.add_argument("--meal", default="dinner")
    p.add_argument("--recipe")
    p.add_argument("--text")
    p.add_argument("--servings", type=servings_arg)
    p.add_argument("--anyway", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p = grp.add("remove", "Clear a planned meal (its share comes off the week's list, crossed-off items stay).",
                ["fridge meal remove wednesday", "fridge meal remove --entry P4"], cmd_remove)  # fmt: skip
    p.add_argument("date", nargs="?")
    p.add_argument("--meal", default="dinner")
    p.add_argument("--entry", help="A planned meal's id")
    p = grp.add("week", "The week's meals (busy evenings marked).",
                ["fridge meal week", "fridge meal week \"next week\""], cmd_week)  # fmt: skip
    p.add_argument("date", nargs="?")
    p = grp.add(
        "to-list",
        "Make (or refresh) the week's grocery list from the plan: merged amounts, pantry items skipped, unknown "
        "staples to check at home. Use --dry-run to review first.",
        ["fridge meal to-list --dry-run", 'fridge meal to-list --week "next week" --skip "rice, salt"'],
        cmd_to_list,
    )
    p.add_argument("--week", help="Any day in the week (default this week)")
    p.add_argument("--list", help="Which list (default: the household's grocery list)")
    p.add_argument("--skip", action="append", help="Items to leave out (comma list)")
    p.add_argument("--dry-run", action="store_true")
    p = grp.add("nights", "Which evenings are busy this week, and any long cook planned on one.",
                ["fridge meal nights"], cmd_nights)  # fmt: skip
    p.add_argument("--week")
    p = grp.add("ideas", "Meal ideas from your own recipes and pantry (suggestions to confirm).",
                ["fridge meal ideas", "fridge meal ideas --date thursday"], cmd_ideas)  # fmt: skip
    p.add_argument("--date")
