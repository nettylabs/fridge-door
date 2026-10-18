"""Shopping and grocery lists: items sorted into each store's aisles, crossing off, re-adding, suggestions.

- A list is "grocery" (the grocery module) or "shopping" (the shopping-lists module), optionally tied to a store.
- Items file themselves: the household's own corrections first, then the bundled lookup, else "Other". Moving an
  item to another aisle teaches it for next time (moving it to "Other" is learned too).
- Crossing off keeps the item (it drops to a crossed-off section) and records the purchase, which powers
  "bought often" suggestions and one-step re-adding with the last quantity.
- Every change is saved at once under a lock, so two people shopping the same list stay in step.
"""

from __future__ import annotations

import datetime as _dt
import re

from . import access
from .seed_aisles import NAMES, SEED, item_key
from .util import ToolError, clean_text, fold, match_one, now_stamp, parse_stamp, plural

# The aisle vocabulary the bundled lookup maps into, in a typical store order.
CANONICAL_AISLES = (
    "Produce",
    "Bakery",
    "Deli",
    "Meat",
    "Seafood",
    "Dairy",
    "Frozen",
    "Pantry",
    "Canned",
    "Condiments",
    "Snacks",
    "Beverages",
    "Household",
    "Personal Care",
    "Baby",
    "Pet",
)
OTHER_AISLE = "Other"
KIND_ICONS = {"grocery": "🛒", "shopping": "🛍️"}
KINDS = ("grocery", "shopping")

RECENT_DAYS = 14  # bought within this many days: x1.5 in suggestions
RECENT_BOOST = 1.5
SUGGEST_LIMIT = 6

_QTY_RE = re.compile(r"^(.+?)\s+[x×]\s?(\d{1,3})$", re.IGNORECASE)
_UNITS = (r"g|gr|grams?|kg|kgs|kilos?|kilograms?|lbs?|pounds?|oz|ounces?|ml|millilit(?:re|er)s?|l|lit(?:re|er)s?|"
          r"pints?|quarts?|gallons?|packs?|packets?|pkts?|bags?|box(?:es)?|bottles?|cans?|tins?|jars?|loaf|loaves|"
          r"bunch(?:es)?|dozen|cartons?|tubs?|heads?|bars?|rolls?|cases?|blocks?|punnets?|trays?|sacks?|slices?")
_LEAD_QTY_RE = re.compile(
    rf"^((?:\d+(?:[.,]\d+)?(?:/\d+)?)|half an?|an?|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
    rf"\s*({_UNITS})?\.?\s+(?:of\s+)?(.+)$", re.IGNORECASE)


# --------------------------------------------------------------------------- pure helpers (ported rules)


def parse_quick(text) -> tuple:
    """ "milk x2" -> ("milk", "2"); "2 lb ground beef" -> ("ground beef", "2 lb"); "500g mince" -> ("mince", "500 g");
    "2 loaves of bread" -> ("bread", "2 loaves"); "12 eggs" -> ("eggs", "12"). A word number counts only with a
    unit ("a dozen eggs"); "an onion" is just an onion."""
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    match = _QTY_RE.match(cleaned)
    if match:
        return match.group(1).strip(), match.group(2)
    match = _LEAD_QTY_RE.match(cleaned)
    if match:
        number, unit, rest = match.group(1), match.group(2), match.group(3).strip()
        if unit:
            return rest, f"{number} {unit}".strip()
        if re.fullmatch(r"\d+(?:[.,]\d+)?(?:/\d+)?", number):
            return rest, number
        if fold(number) in ("a", "an"):
            return rest, None
    return cleaned, None


def categorize(name, overrides: dict, seed: dict = SEED) -> str | None:
    """The aisle name for an item: the household's correction wins, then the bundled lookup; unknown is None.
    A name that isn't known whole is filed by its end ("semi-skimmed milk" by "milk", "lean ground beef" by
    "ground beef"), then by any word in it ("yogurt tubes" by "yogurt")."""
    key = item_key(name)
    words = key.split()
    tails = [" ".join(words[i:]) for i in range(len(words))]
    singles = [item_key(word) for word in reversed(words[:-1])]
    for candidate in tails + singles:
        for table in (overrides, seed):
            if candidate in table:
                return table[candidate]
    return None


def known_item(name, data: dict) -> bool:
    """Something the household has bought before or the bundled lookup knows by name."""
    key = item_key(name)
    return key in data.get("history", {}) or key in data.get("overrides", {}) or key in SEED


def match_aisle(aisle_name: str | None, lst: dict) -> str | None:
    """Find that aisle in this list, ignoring case. No such aisle (or None) means the item goes to Other."""
    if aisle_name is None:
        return None
    wanted = fold(aisle_name)
    for aisle in lst.get("aisles", []):
        if fold(aisle["name"]) == wanted:
            return aisle["id"]
    return None


def suggest(prefix, history: dict, exclude=(), now: _dt.datetime | None = None, limit: int = SUGGEST_LIMIT,
            seed: dict = SEED) -> list:  # fmt: skip
    """Bought-often suggestions while typing (ported scoring).

    Prefix or contains matches over the household's purchase history, scored times bought x1.5 when bought in the
    last 14 days; a prefix beats a contains match on an equal score, then the name. Items already on the list are
    left out (crossed-off ones stay, because picking one re-adds it). Free slots fill from the bundled lookup,
    prefix matches first, alphabetically.
    """
    q = item_key(prefix)
    if not q:
        return []
    now = now or _dt.datetime.now(_dt.timezone.utc)
    excluded = {item_key(e) for e in exclude}
    scored = []
    for key, row in history.items():
        if key in excluded:
            continue
        is_prefix = key.startswith(q)
        if not is_prefix and q not in key:
            continue
        bought = parse_stamp(row.get("last_at"))
        recent = bought is not None and now - bought <= _dt.timedelta(days=RECENT_DAYS)
        score = int(row.get("times", 0)) * (RECENT_BOOST if recent else 1)
        scored.append((score, is_prefix, key, row))
    scored.sort(key=lambda s: (-s[0], not s[1], s[2]))
    results = [
        {"name": row.get("name") or key, "qty": row.get("last_qty"), "times": int(row.get("times", 0)),
         "from": "history"}  # fmt: skip
        for _, _, key, row in scored[:limit]
    ]
    if len(results) < limit:
        taken = {s[2] for s in scored} | excluded
        prefix_hits = sorted(k for k in seed if k not in taken and k.startswith(q))
        contains_hits = sorted(k for k in seed if k not in taken and not k.startswith(q) and q in k)
        for key in prefix_hits + contains_hits:
            if len(results) >= limit:
                break
            name = NAMES.get(key, key) if seed is SEED else key
            results.append({"name": name, "qty": None, "times": 0, "from": "common items"})
    return results


def display_name(name: str) -> str:
    return name[:1].upper() + name[1:] if name else name


def qty_label(qty) -> str:
    """ "x2" for a plain count, otherwise the quantity as typed ("2 lbs")."""
    if qty in (None, ""):
        return ""
    return f"x{qty}" if re.fullmatch(r"\d+", str(qty)) else str(qty)


# --------------------------------------------------------------------------- records


def new_list(hh, name: str, kind: str = "grocery", store=None, icon=None, color=None, default=None) -> dict:
    aisles = CANONICAL_AISLES  # a warehouse or hardware list can trim or add aisles to match its store
    record = {
        "id": hh.next_id("list"),
        "name": name,
        "kind": kind,
        "store": store,
        "icon": icon or KIND_ICONS[kind],
        "color": color,
        "aisles": [{"id": hh.next_id("aisle"), "name": aisle} for aisle in aisles],
        "created_at": now_stamp(),
    }
    if default:
        record["default"] = default
    return record


def ensure_default_lists(hh) -> list:
    data = hh.data("shopping")
    if any(lst.get("default") == "grocery" for lst in data["lists"]):
        return []
    lst = new_list(hh, "Groceries", "grocery", default="grocery")
    data["lists"].insert(0, lst)
    hh.touch("shopping")
    return [lst]


def forget_member(hh, member_id: str) -> list:
    data = hh.data("shopping")
    touched = False
    for item in data["items"]:
        for key in ("added_by", "crossed_by"):
            if item.get(key) == member_id:
                item[key] = None
                touched = True
    if touched:
        hh.touch("shopping")
    return []


def module_of(lst: dict) -> str:
    return access.LIST_KIND_MODULE[lst["kind"]]


def visible_lists(ctx, data: dict, include_deleted: bool = False) -> list:
    return [
        lst
        for lst in data["lists"]
        if (include_deleted or not lst.get("deleted_at")) and ctx.viewer.sees(module_of(lst))
        and ctx.viewer.can_act(module_of(lst), "view")
    ]


def find_list(ctx, data: dict, query, need: str = "view", include_deleted: bool = False) -> dict:
    """A list by name or id (default: the household's grocery list), checking the module for its kind."""
    pool = [
        lst
        for lst in data["lists"]
        if (include_deleted or not lst.get("deleted_at")) and ctx.viewer.can_act(module_of(lst), "view")
    ]  # lists of a kind the person can't see don't exist for them (not even their names)
    if not query:
        lst = next((x for x in pool if x.get("default") == "grocery"), None) or next(iter(pool), None)
        if lst is None:
            raise ToolError("There's no shopping list yet.", hint='Make one: fridge shop new --name "Groceries"',
                            code="not_found")  # fmt: skip
    else:
        lst = match_one(pool, query, "shopping list", hint="See the lists with: fridge shop lists")
    module = module_of(lst)
    verb = "change" if need == "edit" else "see"
    ctx.viewer.require(module, need, f"{verb} the {lst['kind']} list {lst['name']}")
    ctx.viewer.require_sees(module)
    return lst


def items_of(data: dict, list_id: str, crossed: bool | None = None) -> list:
    out = [i for i in data["items"] if i["list"] == list_id]
    if crossed is None:
        return out
    return [i for i in out if bool(i.get("crossed_at")) == crossed]


def item_view(item: dict, lst: dict, hh=None) -> dict:
    aisle_names = {a["id"]: a["name"] for a in lst.get("aisles", [])}
    out = {
        "id": item["id"],
        "name": item["name"],
        "qty": item.get("qty"),
        "note": item.get("note"),
        "aisle": aisle_names.get(item.get("aisle"), OTHER_AISLE),
    }
    if item.get("crossed_at"):
        out["crossed_at"] = item["crossed_at"]
        if hh is not None and item.get("crossed_by"):
            out["crossed_by"] = hh.member_name(item["crossed_by"])
    if item.get("sources"):
        out["from"] = [s.get("label") for s in item["sources"] if s.get("label")]
    return out


def group_by_aisle(lst: dict, items: list) -> list:
    """Open items in the store's aisle order; unknown or deleted aisles fall to Other, last; empty aisles hidden.
    A list with no aisles gets one untitled group."""
    order = [a["id"] for a in lst.get("aisles", [])]
    names = {a["id"]: a["name"] for a in lst.get("aisles", [])}
    buckets: dict = {}
    for item in items:
        key = item.get("aisle") if item.get("aisle") in names else None
        buckets.setdefault(key, []).append(item)
    groups = []
    for aisle_id in order:
        if buckets.get(aisle_id):
            groups.append({"aisle": names[aisle_id], "items": buckets[aisle_id]})
    if buckets.get(None):
        groups.append({"aisle": OTHER_AISLE if order else None, "items": buckets[None]})
    return groups


def _line(item: dict, lst: dict, checkbox: str = "") -> str:
    q = qty_label(item.get("qty"))
    note = f" ({item['note']})" if item.get("note") else ""
    return f"{checkbox}{display_name(item['name'])}{' ' + q if q else ''}{note}"


def list_text(lst: dict, data: dict, checkbox: bool = False, crossed: bool = False) -> str:
    open_items = items_of(data, lst["id"], crossed=False)
    lines = [f"{lst.get('icon') or ''} {lst['name']}".strip() + (f" ({lst['store']})" if lst.get("store") else "")]
    if not open_items:
        lines.append("All done: nothing left on this list.")
    for group in group_by_aisle(lst, open_items):
        if group["aisle"]:
            lines.append(f"{group['aisle']}:")
        for item in group["items"]:
            lines.append("  " + _line(item, lst, "☐ " if checkbox else "• "))
    done = items_of(data, lst["id"], crossed=True)
    if done:
        if crossed:
            lines.append(f"Crossed off ({len(done)}):")
            for item in sorted(done, key=lambda i: (i["crossed_at"], i["id"]), reverse=True):
                lines.append("  " + _line(item, lst, "☑ " if checkbox else "✓ "))
        else:
            lines.append(f"Crossed off: {len(done)}")
    return "\n".join(lines)


def record_purchase(data: dict, item: dict, stamp: str) -> None:
    """Crossing off counts as buying it once (uncrossing never takes it back)."""
    key = item_key(item["name"])
    row = data["history"].setdefault(key, {"name": item["name"].lower(), "times": 0})
    row["times"] = int(row.get("times", 0)) + 1
    row["last_qty"] = item.get("qty")
    row["last_at"] = stamp
    row["name"] = item["name"].lower()
    if key in data.get("pantry", {}):  # bought it: the pantry has it now
        data["pantry"][key]["status"] = "in"
        data["pantry"][key]["updated_at"] = stamp


def find_items(data: dict, lst: dict, query, crossed: bool | None) -> list:
    """Items on this list by id or name (same key), preferring the state asked for; oldest first. A name that
    isn't on the list as such finds the one item whose name ends with it or holds all its words ("milk" finds
    "Semi-skimmed milk"); if several different items fit, it asks which."""
    q = str(query or "").strip()
    pool = items_of(data, lst["id"])
    by_id = [i for i in pool if fold(i["id"]) == fold(q)]
    if by_id:
        return by_id
    key = item_key(parse_quick(q)[0])
    same = [i for i in pool if item_key(i["name"]) == key]
    if not same and key:
        said = key.split()
        fits = [i for i in pool if item_key(i["name"]).endswith(" " + key)
                or all(word in item_key(i["name"]).split() for word in said)]  # fmt: skip
        if crossed is not None:
            fits = [i for i in fits if bool(i.get("crossed_at")) == crossed] or fits
        names = sorted({item_key(i["name"]) for i in fits})
        if len(names) > 1:
            raise ToolError(f"{q!r} could be more than one thing on {lst['name']}.",
                            hint="Use the full name: " + ", ".join(display_name(i["name"]) for i in fits[:6]) + ".",
                            code="ambiguous",
                            candidates=[{"id": i["id"], "name": i["name"]} for i in fits[:10]])  # fmt: skip
        same = fits
    if crossed is not None:
        preferred = [i for i in same if bool(i.get("crossed_at")) == crossed]
        same = preferred or same
    return sorted(same, key=lambda i: (i.get("created_at", ""), i["id"]))


def split_items(values, data: dict | None = None) -> list:
    """Items from what was typed: commas and new lines separate them, and "eggs and bread" is two items when both
    are known and the whole isn't (so "mac and cheese" stays one)."""
    out = []
    for value in values or []:
        for part in (p.strip() for p in re.split(r"[,;\n]", str(value)) if p.strip()):
            pieces = [x.strip() for x in re.split(r"\s+(?:and|&)\s+", part) if x.strip()]
            whole = parse_quick(part)[0]
            if (data is not None and len(pieces) > 1 and not known_item(whole, data)
                    and all(known_item(parse_quick(x)[0], data) for x in pieces)):  # fmt: skip
                out += pieces
            else:
                out.append(part)
    return out


# --------------------------------------------------------------------------- commands


def _counts(data: dict, lst: dict) -> dict:
    return {
        "open": len(items_of(data, lst["id"], crossed=False)),
        "crossed": len(items_of(data, lst["id"], crossed=True)),
    }


def _list_view(data: dict, lst: dict) -> dict:
    counts = _counts(data, lst)
    return {
        "id": lst["id"],
        "name": lst["name"],
        "kind": lst["kind"],
        "store": lst.get("store"),
        "icon": lst.get("icon"),
        "open": counts["open"],
        "crossed": counts["crossed"],
        "label": plural(counts["open"], "item"),
    }


def cmd_lists(ctx, args) -> dict:
    data = ctx.household.data("shopping")
    lists = visible_lists(ctx, data, include_deleted=args.deleted)
    if args.deleted:
        lists = [lst for lst in lists if lst.get("deleted_at")]
    views = [_list_view(data, lst) for lst in lists]
    text = "\n".join(f"{v['icon']} {v['name']}: {v['label']}" for v in views) or "No lists."
    return {"lists": views, "text": text, "summary": f"{plural(len(views), 'list')}."}


def _kind(value: str | None) -> str:
    kind = (value or "grocery").lower()
    if kind not in KINDS:
        raise ToolError(f"{value!r} isn't a list kind.", hint="Use grocery or shopping.", code="bad_kind")
    return kind


def cmd_new(ctx, args) -> dict:
    kind = _kind(args.kind)
    module = access.LIST_KIND_MODULE[kind]
    ctx.viewer.require(module, "edit", f"make {kind} lists")
    ctx.viewer.require_sees(module)
    hh = ctx.household
    name = clean_text(args.name, "list name", max_len=60)
    store = clean_text(args.store, "store", max_len=60, required=False)
    with hh.transaction(dry_run=args.dry_run):
        data = hh.data("shopping")
        if any(fold(lst["name"]) == fold(name) and not lst.get("deleted_at") for lst in data["lists"]):
            raise ToolError(f"There's already a list called {name}.", hint="Pick another name.", code="exists")
        color = None
        if args.color:
            from .members import color_hex

            color = color_hex(args.color)
        lst = new_list(hh, name, kind, store=store, icon=args.icon, color=color)
        data["lists"].append(lst)
        hh.touch("shopping")
        hh.log("shop.list_new", ctx.member["id"], list=lst["id"], kind=kind)
        view = _list_view(data, lst)
    verb = "Would make" if args.dry_run else "Made"
    where = f" for {store}" if store else ""
    return {"list": view, "dry_run": args.dry_run, "summary": f"{verb} the {kind} list {name}{where}."}


def cmd_edit(ctx, args) -> dict:
    hh = ctx.household
    with hh.transaction(dry_run=args.dry_run):
        data = hh.data("shopping")
        lst = find_list(ctx, data, args.list, need="edit")
        changed = []
        if args.name:
            name = clean_text(args.name, "list name", max_len=60)
            if any(fold(x["name"]) == fold(name) and x["id"] != lst["id"] and not x.get("deleted_at")
                   for x in data["lists"]):  # fmt: skip
                raise ToolError(f"There's already a list called {name}.", code="exists")
            lst["name"] = name
            changed.append("name")
        if args.store is not None:
            lst["store"] = clean_text(args.store, "store", max_len=60, required=False)
            changed.append("store")
        if args.icon:
            lst["icon"] = clean_text(args.icon, "icon", max_len=8)
            changed.append("icon")
        if args.color:
            from .members import color_hex

            lst["color"] = color_hex(args.color)
            changed.append("colour")
        if not changed:
            raise ToolError("Nothing to change.", hint="Pass --name, --store, --icon or --color.", code="usage")
        hh.touch("shopping")
        hh.log("shop.list_edit", ctx.member["id"], list=lst["id"], fields=changed)
        view = _list_view(data, lst)
    return {"list": view, "dry_run": args.dry_run, "summary": f"Updated {view['name']}: {', '.join(changed)}."}


def _which_list(args) -> str:
    """shop delete and shop restore take the list's name as a word or with --list, whichever the agent uses."""
    name = getattr(args, "name", None) or getattr(args, "list", None)
    if not name:
        raise ToolError("Which list?", hint="e.g. fridge shop delete Hardware (or --list Hardware)", code="usage")
    return name


def cmd_delete(ctx, args) -> dict:
    hh = ctx.household
    with hh.transaction():
        data = hh.data("shopping")
        lst = find_list(ctx, data, _which_list(args), need="edit")
        if lst.get("default") == "grocery":
            raise ToolError(f"{lst['name']} is the household's main grocery list and can't be deleted.",
                            hint="Rename it, or clear it with: fridge shop clear", code="protected")  # fmt: skip
        lst["deleted_at"] = now_stamp()
        hh.touch("shopping")
        hh.log("shop.list_delete", ctx.member["id"], list=lst["id"])
    days = hh.settings.get("retention_days", 90)
    return {
        "summary": f"Deleted {lst['name']}. It can be restored for {days} days: fridge shop restore \"{lst['name']}\"",
    }


def cmd_restore(ctx, args) -> dict:
    hh = ctx.household
    with hh.transaction():
        data = hh.data("shopping")
        deleted = [lst for lst in data["lists"] if lst.get("deleted_at")]
        lst = match_one(deleted, _which_list(args), "deleted list", hint="See them with: fridge shop lists --deleted")
        ctx.viewer.require(module_of(lst), "edit", f"restore {lst['name']}")
        if any(fold(x["name"]) == fold(lst["name"]) and not x.get("deleted_at") for x in data["lists"]):
            raise ToolError(f"Another list is called {lst['name']} now.", hint="Rename that one first.", code="exists")
        lst.pop("deleted_at", None)
        hh.touch("shopping")
        hh.log("shop.list_restore", ctx.member["id"], list=lst["id"])
    return {"summary": f"Restored {lst['name']}."}


def add_one(hh, data: dict, lst: dict, raw: str, actor_id: str, qty=None, note=None, aisle=None,
            again: bool = False, stamp: str | None = None, sources=None) -> dict:  # fmt: skip
    """Add one item (shared with recipes and the meal plan). Returns {"status", "item", "input"}."""
    stamp = stamp or now_stamp()
    name, typed_qty = parse_quick(raw)
    name = clean_text(name, "item name", max_len=80)
    qty = clean_text(qty, "quantity", max_len=30, required=False) or typed_qty
    note = clean_text(note, "note", max_len=120, required=False)
    key = item_key(name)
    same = [i for i in items_of(data, lst["id"]) if item_key(i["name"]) == key]
    active = [i for i in same if not i.get("crossed_at")]
    crossed = sorted((i for i in same if i.get("crossed_at")), key=lambda i: i["crossed_at"], reverse=True)
    if active and not again:
        item = active[0]
        if qty and not item.get("qty"):  # "chickpeas x3" for chickpeas already there with no amount
            item["qty"] = qty
            return {"status": "quantity_set", "input": raw, "item": item}
        if qty and str(item.get("qty")) != str(qty):
            return {"status": "already_on_list", "input": raw, "item": item, "kept_qty": item["qty"], "asked": qty}
        return {"status": "already_on_list", "input": raw, "item": item}
    if crossed and not again:
        item = crossed[0]  # re-adding uncrosses the most recently crossed one, keeping its quantity
        item["crossed_at"] = None
        item["crossed_by"] = None
        if qty:
            item["qty"] = qty
        if note:
            item["note"] = note
        if sources:
            item.setdefault("sources", []).extend(sources)
        return {"status": "uncrossed", "input": raw, "item": item}
    if aisle is not None:
        aisle_id = _aisle_id(lst, aisle)
    else:
        aisle_id = match_aisle(categorize(name, data["overrides"]), lst)
    item = {
        "id": hh.next_id("item"),
        "list": lst["id"],
        "name": name,
        "qty": qty,
        "note": note,
        "aisle": aisle_id,
        "crossed_at": None,
        "added_by": actor_id,
        "created_at": stamp,
    }
    if sources:
        item["sources"] = list(sources)
    data["items"].append(item)
    return {"status": "added", "input": raw, "item": item}


def _aisle_id(lst: dict, name: str) -> str | None:
    if fold(name) == fold(OTHER_AISLE):
        return None
    aisle_id = match_aisle(name, lst)
    if aisle_id is None:
        known = ", ".join(a["name"] for a in lst.get("aisles", [])) or "none yet"
        raise ToolError(
            f"{lst['name']} has no aisle called {name!r}.",
            hint=f"Aisles: {known}. Add one with: fridge shop aisles --list \"{lst['name']}\" --add \"{name}\"",
            code="no_such_aisle",
        )
    return aisle_id


_STATUS_WORDS = {
    "added": "added",
    "quantity_set": "amount added",
    "uncrossed": "back on the list",
    "already_on_list": "already on the list",
    "crossed": "crossed off",
    "already_crossed": "already crossed off",
    "not_found": "not on the list",
    "removed": "removed",
}


def _summarize(results: list, lst: dict) -> str:
    groups: dict = {}
    for r in results:
        label = display_name(r["item"]["name"]) if r.get("item") else r["input"]
        q = qty_label(r["item"].get("qty")) if r.get("item") else ""
        groups.setdefault(r["status"], []).append(label + (f" {q}" if q else ""))
    parts = [f"{_STATUS_WORDS[status]}: {', '.join(names)}" for status, names in groups.items()]
    return f"{lst['name']}: " + "; ".join(parts) + "."


def cmd_add(ctx, args) -> dict:
    hh = ctx.household
    with hh.transaction(dry_run=args.dry_run):
        data = hh.data("shopping")
        raws = split_items(args.items, data)
        if not raws:
            raise ToolError("What should I add?", hint='e.g. fridge shop add "milk x2" eggs bread', code="missing")
        if len(raws) > 1 and (args.qty or args.note):
            raise ToolError("--qty and --note work with one item at a time.",
                            hint='Use "milk x2" in the item instead.', code="usage")  # fmt: skip
        lst = find_list(ctx, data, args.list, need="edit")
        stamp = now_stamp()
        results = [
            add_one(hh, data, lst, raw, ctx.member["id"], qty=args.qty, note=args.note, aisle=args.aisle,
                    again=args.again, stamp=stamp)  # fmt: skip
            for raw in raws
        ]
        hh.touch("shopping")
        hh.log("shop.add", ctx.member["id"], list=lst["id"], items=[r["item"]["id"] for r in results])
        views = [dict(r, item=item_view(r["item"], lst)) for r in results]
        counts = _counts(data, lst)
    out = {
        "list": {"id": lst["id"], "name": lst["name"]},
        "results": views,
        "open": counts["open"],
        "dry_run": args.dry_run,
        "summary": ("Would update " if args.dry_run else "") + _summarize(views, lst),
    }
    if any(r["status"] == "already_on_list" for r in views):
        out["hint"] = "Already-there items weren't added twice; add --again to add another line anyway."
        differ = [r for r in views if r.get("asked")]
        if differ:
            r = differ[0]
            out["hint"] += (f" {display_name(r['item']['name'])} is there as {qty_label(r['kept_qty'])}; to make it "
                            f"{qty_label(r['asked'])}: fridge shop item \"{r['item']['name']}\" --qty \"{r['asked']}\"")
    return out


def cmd_show(ctx, args) -> dict:
    data = ctx.household.data("shopping")
    lst = find_list(ctx, data, args.list)
    open_items = items_of(data, lst["id"], crossed=False)
    groups = [
        {"aisle": g["aisle"], "items": [item_view(i, lst) for i in g["items"]]} for g in group_by_aisle(lst, open_items)
    ]
    done = sorted(items_of(data, lst["id"], crossed=True), key=lambda i: (i["crossed_at"], i["id"]), reverse=True)
    out = {
        "list": _list_view(data, lst),
        "groups": groups,
        "crossed_count": len(done),
        "text": list_text(lst, data, crossed=args.crossed),
        "summary": f"{lst['name']}: {plural(len(open_items), 'item')} to get"
        + (f", {len(done)} crossed off." if done else "."),
    }
    if args.crossed:
        out["crossed"] = [item_view(i, lst, ctx.household) for i in done]
    return out


def _cross(ctx, args, crossing: bool) -> dict:
    hh = ctx.household
    with hh.transaction():
        data = hh.data("shopping")
        lst = find_list(ctx, data, args.list, need="edit")
        stamp = now_stamp()
        results = []
        if not crossing and args.all:
            targets = items_of(data, lst["id"], crossed=True)
            for item in targets:
                item["crossed_at"] = None
                item["crossed_by"] = None
            hh.touch("shopping")
            hh.log("shop.uncross_all", ctx.member["id"], list=lst["id"], count=len(targets))
            summary = f"Put {plural(len(targets), 'item')} back on {lst['name']}, ready to reuse."
            return {"list": {"id": lst["id"], "name": lst["name"]}, "uncrossed": len(targets), "summary": summary}
        for raw in split_items(args.items, data):
            found = find_items(data, lst, raw, crossed=not crossing)
            if not found:
                results.append({"status": "not_found", "input": raw})
                continue
            item = found[0]
            if crossing:
                if item.get("crossed_at"):
                    results.append({"status": "already_crossed", "input": raw, "item": item})
                    continue
                item["crossed_at"] = stamp
                item["crossed_by"] = ctx.member["id"]
                record_purchase(data, item, stamp)
                results.append({"status": "crossed", "input": raw, "item": item})
            else:
                if not item.get("crossed_at"):
                    results.append({"status": "already_on_list", "input": raw, "item": item})
                    continue
                item["crossed_at"] = None
                item["crossed_by"] = None
                results.append({"status": "uncrossed", "input": raw, "item": item})
        if not results:
            raise ToolError("Which items?", hint='e.g. fridge shop cross milk eggs', code="missing")
        hh.touch("shopping")
        hh.log("shop.cross" if crossing else "shop.uncross", ctx.member["id"], list=lst["id"],
               items=[r["item"]["id"] for r in results if r.get("item")])  # fmt: skip
        views = [dict(r, item=item_view(r["item"], lst)) if r.get("item") else r for r in results]
        left = len(items_of(data, lst["id"], crossed=False))
    summary = _summarize(views, lst) + f" {plural(left, 'item')} left."
    return {"list": {"id": lst["id"], "name": lst["name"]}, "results": views, "open": left, "summary": summary}


def cmd_cross(ctx, args) -> dict:
    return _cross(ctx, args, crossing=True)


def cmd_uncross(ctx, args) -> dict:
    if not args.all and not args.items:
        raise ToolError("Which items?", hint="Name them, or use --all to reuse the whole list.", code="missing")
    return _cross(ctx, args, crossing=False)


def cmd_readd(ctx, args) -> dict:
    """Put things back on the list in one step, each with the quantity it had last time."""
    hh = ctx.household
    with hh.transaction():
        data = hh.data("shopping")
        lst = find_list(ctx, data, args.list, need="edit")
        results = []
        for raw in split_items(args.items, data):
            name, typed = parse_quick(raw)
            found = find_items(data, lst, name, crossed=True)
            if found and found[0].get("crossed_at"):
                item = found[0]
                item["crossed_at"] = None
                item["crossed_by"] = None
                if typed:
                    item["qty"] = typed
                status = "uncrossed"
            elif found:
                item, status = found[0], "already_on_list"
            else:
                row = data["history"].get(item_key(name))
                result = add_one(hh, data, lst, name, ctx.member["id"], qty=typed or (row or {}).get("last_qty"))
                item, status = result["item"], result["status"]
            results.append({"status": status, "input": raw, "item": item})
        hh.touch("shopping")
        hh.log("shop.readd", ctx.member["id"], list=lst["id"], items=[r["item"]["id"] for r in results])
        views = [dict(r, item=item_view(r["item"], lst)) for r in results]
    out = {"results": views, "summary": _summarize(views, lst)}
    if len(views) == 1:
        out.update(status=views[0]["status"], item=views[0]["item"])
    return out


def cmd_remove(ctx, args) -> dict:
    hh = ctx.household
    with hh.transaction():
        data = hh.data("shopping")
        lst = find_list(ctx, data, args.list, need="edit")
        results = []
        for raw in split_items(args.items, data):
            found = find_items(data, lst, raw, crossed=False)
            if not found:
                results.append({"status": "not_found", "input": raw})
                continue
            data["items"] = [i for i in data["items"] if i["id"] != found[0]["id"]]
            results.append({"status": "removed", "input": raw, "item": found[0]})
        hh.touch("shopping")
        hh.log("shop.remove", ctx.member["id"], list=lst["id"],
               items=[r["item"]["id"] for r in results if r.get("item")])  # fmt: skip
        views = [dict(r, item=item_view(r["item"], lst)) if r.get("item") else r for r in results]
    return {"results": views, "summary": _summarize(views, lst)}


def cmd_clear(ctx, args) -> dict:
    hh = ctx.household
    with hh.transaction():
        data = hh.data("shopping")
        lst = find_list(ctx, data, args.list, need="edit")
        gone = items_of(data, lst["id"], crossed=True) if not args.everything else items_of(data, lst["id"])
        ids = {i["id"] for i in gone}
        data["items"] = [i for i in data["items"] if i["id"] not in ids]
        hh.touch("shopping")
        hh.log("shop.clear", ctx.member["id"], list=lst["id"], count=len(gone))
    what = "every item" if args.everything else "the crossed-off items"
    return {"removed": len(gone), "summary": f"Cleared {what} from {lst['name']} ({len(gone)})."}


def cmd_item(ctx, args) -> dict:
    hh = ctx.household
    with hh.transaction(dry_run=args.dry_run):
        data = hh.data("shopping")
        lst = find_list(ctx, data, args.list, need="edit")
        found = find_items(data, lst, args.item, crossed=False)
        if not found:
            raise ToolError(f"{args.item!r} isn't on {lst['name']}.", hint="See it with: fridge shop show",
                            code="not_found")  # fmt: skip
        item = found[0]
        changed = []
        if args.name:
            item["name"] = clean_text(args.name, "item name", max_len=80)
            changed.append("name")
            if not args.aisle:  # filed again under its new name ("2 loaves of bread" renamed "bread")
                refiled = match_aisle(categorize(item["name"], data["overrides"]), lst)
                if refiled:
                    item["aisle"] = refiled
        if args.qty is not None:
            item["qty"] = clean_text(args.qty, "quantity", max_len=30, required=False)
            changed.append("quantity")
        if args.note is not None:
            item["note"] = clean_text(args.note, "note", max_len=120, required=False)
            changed.append("note")
        learned = None
        if args.aisle:
            item["aisle"] = _aisle_id(lst, args.aisle)
            learned = next((a["name"] for a in lst["aisles"] if a["id"] == item["aisle"]), OTHER_AISLE)
            data["overrides"][item_key(item["name"])] = learned  # "Other" is learned too: it beats a wrong guess
            changed.append("aisle")
        if not changed:
            raise ToolError("Nothing to change.", hint="Pass --name, --qty, --note or --aisle.", code="usage")
        hh.touch("shopping")
        hh.log("shop.item_edit", ctx.member["id"], list=lst["id"], item=item["id"], fields=changed)
        view = item_view(item, lst)
    summary = f"Updated {display_name(view['name'])}: {', '.join(changed)}."
    if learned:
        summary += f" Next time it goes to {learned} by itself."
    return {"item": view, "learned_aisle": learned, "dry_run": args.dry_run, "summary": summary}


def cmd_suggest(ctx, args) -> dict:
    hh = ctx.household
    data = hh.data("shopping")
    lst = find_list(ctx, data, args.list)
    active = [i["name"] for i in items_of(data, lst["id"], crossed=False)]
    found = suggest(args.text, data["history"], exclude=active, now=hh.now())
    for s in found:
        s["name"] = display_name(s["name"])
    text = ", ".join(s["name"] + (f" {qty_label(s['qty'])}" if s.get("qty") else "") for s in found)
    return {"suggestions": found, "text": text, "summary": text or "No suggestions."}


def _aisle_index(lst: dict, name: str) -> int:
    wanted = fold(name)
    for index, aisle in enumerate(lst["aisles"]):
        if fold(aisle["name"]) == wanted:
            return index
    raise ToolError(f"{lst['name']} has no aisle called {name!r}.",
                    hint="Aisles: " + (", ".join(a["name"] for a in lst["aisles"]) or "none yet"),
                    code="no_such_aisle")  # fmt: skip


def cmd_aisles(ctx, args) -> dict:
    hh = ctx.household
    editing = any((args.add, args.rename, args.move, args.delete, args.order))
    with hh.transaction(dry_run=args.dry_run or not editing):
        data = hh.data("shopping")
        lst = find_list(ctx, data, args.list, need="edit" if editing else "view")
        aisles = lst["aisles"]
        changes = []
        if args.order:
            wanted = [part.strip() for part in args.order.split(",") if part.strip()]
            for name in wanted:  # a store's own aisles ("Bulk", "Seasonal") are added as they're named
                if match_aisle(name, lst) is None and fold(name) != fold(OTHER_AISLE):
                    aisles.append({"id": hh.next_id("aisle"), "name": clean_text(name, "aisle name", max_len=40)})
                    changes.append(f"added {name}")
            picked = [aisles[_aisle_index(lst, name)] for name in wanted if fold(name) != fold(OTHER_AISLE)]
            rest = [a for a in aisles if a not in picked]
            lst["aisles"] = picked + rest
            aisles = lst["aisles"]
            changes.append("reordered")
        if args.add:
            name = clean_text(args.add, "aisle name", max_len=40)
            if any(fold(a["name"]) == fold(name) for a in aisles) or fold(name) == fold(OTHER_AISLE):
                raise ToolError(f"{lst['name']} already has {name}.", code="exists")
            record = {"id": hh.next_id("aisle"), "name": name}
            position = _aisle_index(lst, args.before) if args.before else len(aisles)
            aisles.insert(position, record)
            changes.append(f"added {name}")
        if args.rename:
            index = _aisle_index(lst, args.rename)
            new_name = clean_text(args.to, "new aisle name", max_len=40)
            old = aisles[index]["name"]
            aisles[index]["name"] = new_name
            for key, value in data["overrides"].items():
                if fold(value) == fold(old):
                    data["overrides"][key] = new_name
            changes.append(f"renamed {old} to {new_name}")
        if args.move:
            index = _aisle_index(lst, args.move)
            record = aisles.pop(index)
            if args.first:
                aisles.insert(0, record)
            elif args.before:
                aisles.insert(_aisle_index(lst, args.before), record)
            elif args.after:
                aisles.insert(_aisle_index(lst, args.after) + 1, record)
            else:
                aisles.append(record)
            changes.append(f"moved {record['name']}")
        if args.delete:
            index = _aisle_index(lst, args.delete)
            record = aisles.pop(index)
            for item in items_of(data, lst["id"]):
                if item.get("aisle") == record["id"]:
                    item["aisle"] = None
            changes.append(f"deleted {record['name']} (its items moved to Other)")
        if editing:
            filed = 0
            for item in items_of(data, lst["id"]):  # items waiting in Other go to an aisle that now fits them
                if not item.get("aisle"):
                    aisle_id = match_aisle(categorize(item["name"], data["overrides"]), lst)
                    if aisle_id:
                        item["aisle"] = aisle_id
                        filed += 1
            if filed:
                changes.append(f"filed {plural(filed, 'item')} from Other")
            hh.touch("shopping")
            hh.log("shop.aisles", ctx.member["id"], list=lst["id"], changes=changes)
        names = [a["name"] for a in lst["aisles"]]
    if not editing:
        everything = names + [OTHER_AISLE]
        return {"aisles": everything, "summary": f"{lst['name']} aisles: " + ", ".join(everything)}
    verb = "Would update" if args.dry_run else "Updated"
    return {"aisles": names + [OTHER_AISLE], "dry_run": args.dry_run,
            "summary": f"{verb} {lst['name']}: {'; '.join(changes)}."}  # fmt: skip


def cmd_share(ctx, args) -> dict:
    hh = ctx.household
    data = hh.data("shopping")
    lst = find_list(ctx, data, args.list)
    text = list_text(lst, data, checkbox=True)
    out = {"text": text, "summary": f"{lst['name']} is ready to share as a message."}
    if args.file:
        safe = re.sub(r"[^A-Za-z0-9_-]+", "-", lst["name"]).strip("-").lower() or "list"
        path = hh.output_dir() / f"{safe}.txt"
        path.write_text(text + "\n", encoding="utf-8")
        out["file"] = str(path)
        out["summary"] = f"Saved {lst['name']} to {path.name}, ready to send as a file."
    return out


def register(cli) -> None:
    grp = cli.group("shop", "Shopping and grocery lists: items by aisle, cross off, re-add, suggestions, share.")
    list_help = "Which list (name or id; default: the household's grocery list)"
    p = grp.add("lists", "Show the shopping and grocery lists with how many items are left.",
                ["fridge shop lists", "fridge shop lists --deleted"], cmd_lists)  # fmt: skip
    p.add_argument("--deleted", action="store_true", help="Show deleted lists that can still be restored")
    p = grp.add(
        "new",
        "Make a list (grocery or shopping), optionally for a store.",
        [
            'fridge shop new --name "Warehouse run" --kind shopping --store "Northside Warehouse Club"',
            'fridge shop new --name "Hardware" --kind shopping --icon 🔨',
        ],
        cmd_new,
    )
    p.add_argument("--name", required=True)
    p.add_argument("--kind", default="grocery", help="grocery (default) or shopping")
    p.add_argument("--store")
    p.add_argument("--icon", help="An emoji")
    p.add_argument("--color", help="A palette colour name or #RRGGBB")
    p.add_argument("--dry-run", action="store_true")
    p = grp.add("edit", "Rename a list or change its store, icon or colour.",
                ['fridge shop edit --list Hardware --store "Hammer & Nail"'], cmd_edit)  # fmt: skip
    p.add_argument("--list", help=list_help)
    p.add_argument("--name")
    p.add_argument("--store", help='The store ("" to clear it)')
    p.add_argument("--icon")
    p.add_argument("--color")
    p.add_argument("--dry-run", action="store_true")
    p = grp.add("delete", "Delete a list (restorable for the retention period).",
                ["fridge shop delete Hardware", "fridge shop delete --list Hardware"],
                cmd_delete)  # fmt: skip
    p.add_argument("name", nargs="?", help="The list")
    p.add_argument("--list", help="The list (the same as giving its name)")
    p = grp.add("restore", "Bring back a deleted list.", ["fridge shop restore Hardware",
                "fridge shop restore --list Hardware"], cmd_restore)  # fmt: skip
    p.add_argument("name", nargs="?", help="The deleted list")
    p.add_argument("--list", help="The deleted list (the same as giving its name)")
    p = grp.add(
        "add",
        'Add items ("milk x2" sets a quantity). Items file themselves into aisles; items already there aren\'t added '
        "twice, and crossed-off ones come back with their quantity.",
        ['fridge shop add "milk x2" eggs bread', 'fridge shop add "nails" --list Hardware --note "2 inch"',
         'fridge shop add "oat milk" --aisle Dairy'],
        cmd_add,
    )  # fmt: skip
    p.add_argument("items", nargs="+", help='Items; "x2" at the end sets the quantity; commas separate items')
    p.add_argument("--list", help=list_help)
    p.add_argument("--qty", help='Quantity for a single item, e.g. "2 lbs"')
    p.add_argument("--note", help="A note for a single item")
    p.add_argument("--aisle", help="Put it in this aisle instead of the automatic one")
    p.add_argument("--again", action="store_true", help="Add another line even if it's already on the list")
    p.add_argument("--dry-run", action="store_true")
    p = grp.add("show", "Show a list grouped by aisle, in the store's order.",
                ["fridge shop show", "fridge shop show --list Hardware --crossed"], cmd_show)  # fmt: skip
    p.add_argument("--list", help=list_help)
    p.add_argument("--crossed", action="store_true", help="List the crossed-off items too")
    commands = (
        ("cross", cmd_cross, "Cross items off (they drop to the crossed-off section)."),
        ("uncross", cmd_uncross, "Put crossed-off items back on the list (--all to reuse it)."),
    )
    for name, func, text in commands:
        p = grp.add(name, text, [f"fridge shop {name} milk eggs", "fridge shop uncross --all"] if name == "uncross"
                    else ["fridge shop cross milk eggs", "fridge shop cross I12 --list Hardware"], func)  # fmt: skip
        p.add_argument("items", nargs="*")
        p.add_argument("--list", help=list_help)
        if name == "uncross":
            p.add_argument("--all", action="store_true", help="Uncross everything (reuse the list)")
        else:
            p.set_defaults(all=False)
    p = grp.add("readd", "Re-add items in one step, each with the quantity it had last time.",
                ["fridge shop readd milk", "fridge shop readd milk bananas"], cmd_readd)  # fmt: skip
    p.add_argument("items", nargs="+")
    p.add_argument("--list", help=list_help)
    p = grp.add("remove", "Take items off the list (not the same as crossing off).", ["fridge shop remove kale"],
                cmd_remove)  # fmt: skip
    p.add_argument("items", nargs="+")
    p.add_argument("--list", help=list_help)
    p = grp.add("clear", "Clear the crossed-off items (or --everything).", ["fridge shop clear"], cmd_clear)
    p.add_argument("--list", help=list_help)
    p.add_argument("--everything", action="store_true", help="Remove every item, crossed off or not")
    p = grp.add(
        "item",
        "Change an item's name, quantity, note or aisle. A new aisle is remembered for next time.",
        ['fridge shop item milk --qty "2 litres"', 'fridge shop item "oat milk" --aisle Dairy'],
        cmd_item,
    )
    p.add_argument("item")
    p.add_argument("--list", help=list_help)
    p.add_argument("--name")
    p.add_argument("--qty", help='"" clears it')
    p.add_argument("--note", help='"" clears it')
    p.add_argument("--aisle", help="An aisle on this list, or Other")
    p.add_argument("--dry-run", action="store_true")
    p = grp.add("suggest", "Suggestions while typing: what the household buys often, then common items.",
                ["fridge shop suggest mi"], cmd_suggest)  # fmt: skip
    p.add_argument("text")
    p.add_argument("--list", help=list_help)
    p = grp.add(
        "aisles",
        "Show or change a list's aisle order: add, rename, move, delete, or set the whole order.",
        [
            "fridge shop aisles",
            'fridge shop aisles --add "Bulk" --before Pantry',
            "fridge shop aisles --move Frozen --after Beverages",
            'fridge shop aisles --order "Bakery,Produce,Dairy"',
            'fridge shop aisles --rename Deli --to "Deli & Cheese"',
        ],
        cmd_aisles,
    )
    p.add_argument("--list", help=list_help)
    p.add_argument("--add", help="A new aisle name")
    p.add_argument("--rename", help="The aisle to rename (with --to)")
    p.add_argument("--to", help="The new name")
    p.add_argument("--move", help="The aisle to move (with --first, --before, --after; default: last)")
    p.add_argument("--first", action="store_true")
    p.add_argument("--before")
    p.add_argument("--after")
    p.add_argument("--delete", help="The aisle to delete (its items move to Other)")
    p.add_argument("--order", help="Comma list: these aisles first, in this order")
    p.add_argument("--dry-run", action="store_true")
    p = grp.add("share", "The list as a tidy message with tick boxes, or a .txt file with --file.",
                ["fridge shop share", "fridge shop share --list Hardware --file"], cmd_share)  # fmt: skip
    p.add_argument("--list", help=list_help)
    p.add_argument("--file", action="store_true", help="Also save it as a text file to send")
