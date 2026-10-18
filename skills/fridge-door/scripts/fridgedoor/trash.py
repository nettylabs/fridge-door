"""The bin (`fridge bin`): a deleted task, event, note, recipe, expense, bill, savings goal or budget category
waits here for the household's retention period (90 days unless the owner changes it), so a delete can be undone
with `fridge bin restore`. Deleted lists have their own restore (shop restore, todo list-restore).

Each module keeps its own bin in its own file ("bin": [...]), so the bin follows the same rules as the records did:
a private event or note in the bin is still only its owner's, only what the person may see is shown or restored,
and nothing from the bin shows in a group chat with kids in it. Entries older than the retention period are dropped
whenever their file is saved (store.Household.transaction), and removing a member clears theirs (forget).
"""

from __future__ import annotations

import datetime as _dt
from decimal import Decimal

from .util import ToolError, fold, get_tz, match_one, now_stamp, parse_stamp, plural

KINDS = {
    "task": ("todos", "tasks"),
    "event": ("calendar", "events"),
    "note": ("notes", "notes"),
    "recipe": ("recipes", "recipes"),
    "expense": ("budget", "expenses"),
    "bill": ("budget", "bills"),
    "goal": ("budget", "goals"),
    "category": ("budget", "categories"),
}
LABELS = {"task": "task", "event": "event", "note": "note", "recipe": "recipe", "expense": "expense", "bill": "bill",
          "goal": "savings goal", "category": "budget category"}  # fmt: skip
MODULES = ("todos", "calendar", "notes", "recipes", "budget")  # module files with a bin, and their access modules


def days(hh) -> int:
    from .store import DEFAULT_RETENTION_DAYS

    return int(hh.settings.get("retention_days") or DEFAULT_RETENTION_DAYS)


def put(hh, kind: str, records: list, by: str, **extra) -> str:
    """Move records into their module's bin (the caller takes them out of the module). Returns how to undo it."""
    module, _ = KINDS[kind]
    entry = {"kind": kind, "records": records, "deleted_at": now_stamp(), "by": by}
    if extra:
        entry["extra"] = extra
    hh.data(module).setdefault("bin", []).append(entry)
    hh.touch(module)
    return f'fridge bin restore "{_name(hh, entry)}"'


def kept_for(hh) -> str:
    return f"It's in the bin for {plural(days(hh), 'day')}."


def forget(hh, module: str, member_id: str, drop, scrub) -> None:
    """Removing a member: their own private things leave the bin (drop), and they're taken off the rest (scrub)."""
    data = hh.data(module)
    if not data.get("bin"):
        return
    kept = []
    for entry in data["bin"]:
        if any(drop(record) for record in entry["records"]):
            continue
        for record in entry["records"]:
            scrub(record)
        if entry.get("by") == member_id:
            entry["by"] = None
        kept.append(entry)
    data["bin"] = kept
    hh.touch(module)


# --------------------------------------------------------------------------- reading the bin


def _name(hh, entry: dict) -> str:
    record, kind = entry["records"][0], entry["kind"]
    if kind in ("task", "event", "note", "recipe"):
        return record["title"]
    if kind == "expense":
        from .budget import disp
        from .money import fmt

        note = f" {record['note']}" if record.get("note") else ""
        return f"{fmt(Decimal(record['amount']), disp(hh))} on {record['date']}{note}"
    return record["name"]


def _visible(ctx, entry: dict) -> bool:
    kind, record, viewer = entry["kind"], entry["records"][0], ctx.viewer
    if kind == "task":
        lists = ctx.household.data("todos")["lists"]
        owner = next((lst.get("owner") for lst in lists if lst["id"] == record.get("list")), None)
        return viewer.sees_private_of(owner) if owner else True
    if kind == "event":
        from . import events

        return events.visible(viewer, record)
    if kind == "note":
        from . import notes

        return notes.visible(ctx, record)
    return True  # recipes and the budget: the module check in _entries is the whole rule


def _entries(ctx, kind: str | None = None) -> list:
    """(module, entry) for everything in the bin this person may see, newest first."""
    hh = ctx.household
    if ctx.viewer.minors_present:
        raise ToolError("The bin isn't shown in a group chat with kids in it.", hint="Ask in a direct chat.",
                        code="hidden_in_group")  # fmt: skip
    cutoff = hh.now() - _dt.timedelta(days=days(hh))
    found = []
    for module in MODULES:
        if not ctx.viewer.sees(module):
            continue
        for entry in hh.data(module).get("bin", []):
            stamp = parse_stamp(entry.get("deleted_at"))
            if (kind and entry["kind"] != kind) or (stamp and stamp < cutoff) or not _visible(ctx, entry):
                continue
            found.append((module, entry))
    return sorted(found, key=lambda pair: pair[1].get("deleted_at") or "", reverse=True)


def _when(hh, entry: dict) -> tuple:
    stamp = parse_stamp(entry.get("deleted_at")) or hh.now()
    day = stamp.astimezone(get_tz(hh.tz())).date()
    return day, day + _dt.timedelta(days=days(hh))


def cmd_show(ctx, args) -> dict:
    hh = ctx.household
    items, lines = [], []
    for _, entry in _entries(ctx, args.kind):
        day, until = _when(hh, entry)
        name = _name(hh, entry)
        who = hh.member_name(entry.get("by")) if entry.get("by") else "a former member"
        more = len(entry["records"]) - 1
        extra = f" (and {plural(more, 'subtask')})" if more and entry["kind"] == "task" else ""
        items.append({"kind": entry["kind"], "id": entry["records"][0]["id"], "name": name, "deleted": day.isoformat(),
                      "by": who, "until": until.isoformat()})  # fmt: skip
        lines.append(f"• {LABELS[entry['kind']].capitalize()}: {name}{extra}, deleted {hh.day(day)} by {who} "
                     f"(until {hh.day(until)})")  # fmt: skip
    summary = f"{plural(len(items), 'deleted item')} in the bin." if items else "The bin is empty."
    return {"items": items, "text": "\n".join(lines) or "The bin is empty.", "summary": summary}


# --------------------------------------------------------------------------- restoring


def _clash(existing: list, name: str, what: str, key: str = "name") -> None:
    if any(fold(item[key]) == fold(name) for item in existing):
        raise ToolError(f"There's already a {what} called {name}.", hint="Rename that one first, then restore this.",
                        code="exists")  # fmt: skip


def _put_back(ctx, data: dict, entry: dict) -> list:
    """Put an entry's records back into the module data; returns notes for the summary."""
    from . import budget, events, notes, todos

    kind, records = entry["kind"], entry["records"]
    record, said, extra = records[0], [], entry.get("extra") or {}
    if kind == "task":
        lists = {lst["id"]: lst for lst in data["lists"]}
        home = lists.get(record.get("list"))
        if home is None or home.get("deleted_at"):
            home = next((lst for lst in data["lists"]
                         if lst["name"] == todos.HOUSEHOLD_LIST and not lst.get("owner") and not lst.get("deleted_at")),
                        None)  # fmt: skip
            if home is None:
                raise ToolError("Its list is gone, and so is Household Tasks.", hint="Restore a list first.",
                                code="not_found")  # fmt: skip
            for task in records:
                task["list"] = home["id"]
            said.append(f"Its list is gone, so it's on {home['name']}.")
        if record.get("parent") and not any(t["id"] == record["parent"] for t in data["tasks"]):
            record["parent"] = None
        data["tasks"].extend(records)
    elif kind == "event":
        events._owned_or_editor(ctx, record)
        data["events"].append(record)
    elif kind == "note":
        notes._can_change(ctx, record)
        mine_or_shared = [n for n in data["notes"]
                          if n.get("visibility") != "private" or n.get("author") == ctx.member["id"]]  # fmt: skip
        _clash(mine_or_shared, record["title"], "note", key="title")
        data["notes"].append(record)
    elif kind == "recipe":
        _clash(data["recipes"], record["title"], "recipe", key="title")
        data["recipes"].append(record)
    elif kind == "expense":
        if not any(c["id"] == record["category"] for c in data["categories"]):
            other = next((c for c in data["categories"] if fold(c["name"]) == "other"), None)
            other = other or budget._new_category(ctx.household, data, "Other", None, "📦")
            record["category"] = other["id"]
            said.append("Its category is gone, so it's under Other.")
        data["expenses"].append(record)
        for bill_id, due in extra.get("paid", []):
            bill = next((b for b in data["bills"] if b["id"] == bill_id), None)
            if bill is not None and due not in bill.get("paid", {}):
                bill.setdefault("paid", {})[due] = record["id"]
                when = ctx.household.day(_dt.date.fromisoformat(due))
                said.append(f"{bill['name']} is marked paid again for {when}.")
    elif kind == "bill":
        _clash(data["bills"], record["name"], "bill")
        if record.get("category") and not any(c["id"] == record["category"] for c in data["categories"]):
            record["category"] = None
        data["bills"].append(record)
    elif kind == "goal":
        _clash(data["goals"], record["name"], "savings goal")
        data["goals"].append(record)
    elif kind == "category":
        _clash(data["categories"], record["name"], "budget category")
        data["categories"].append(record)
        for bill in data["bills"]:
            if bill["id"] in extra.get("bills", []) and not bill.get("category"):
                bill["category"] = record["id"]
        if extra.get("moved"):
            moved = plural(extra["moved"], "expense")
            said.append(f"Its {moved} stay in {extra.get('moved_to') or 'the category they moved to'}.")
    return said


def cmd_restore(ctx, args) -> dict:
    hh = ctx.household
    pool = [{"id": entry["records"][0]["id"], "name": _name(hh, entry), "kind": entry["kind"], "module": module,
             "deleted_at": entry.get("deleted_at")} for module, entry in _entries(ctx, args.kind)]  # fmt: skip
    found = match_one(pool, args.item, "deleted item", hint="See what's in the bin: fridge bin show",
                      label=lambda item: f"{LABELS[item['kind']]}: {item['name']}")  # fmt: skip
    module = found["module"]
    ctx.viewer.require(module, "edit", f"restore a {LABELS[found['kind']]}")
    with hh.transaction(dry_run=args.dry_run):
        data = hh.data(module)
        entry = next((e for e in data.get("bin", []) if e["records"][0]["id"] == found["id"]
                      and e.get("deleted_at") == found["deleted_at"]), None)  # fmt: skip
        if entry is None:
            raise ToolError("That's no longer in the bin.", hint="See what's there: fridge bin show", code="not_found")
        said = _put_back(ctx, data, entry)
        data["bin"].remove(entry)
        hh.touch(module)
        hh.log("bin.restore", ctx.member["id"], kind=entry["kind"], record=found["id"])
    verb = "Would restore" if args.dry_run else "Restored"
    summary = f"{verb} the {LABELS[found['kind']]} {found['name']}." + "".join(f" {s}" for s in said)
    return {"restored": {"kind": found["kind"], "id": found["id"], "name": found["name"]}, "dry_run": args.dry_run,
            "summary": summary}  # fmt: skip


def register(cli) -> None:
    grp = cli.group("bin", "Deleted tasks, events, notes, recipes and budget items, kept for the retention period.")
    kinds = tuple(KINDS)
    p = grp.add("show", "What's in the bin that you may see, newest first, and until when.",
                ["fridge bin show", "fridge bin show --kind event"], cmd_show)  # fmt: skip
    p.add_argument("--kind", choices=kinds)
    p = grp.add(
        "restore",
        "Put something deleted back where it was (by its name, or its id for an expense).",
        ['fridge bin restore "Fix the gate"', "fridge bin restore X12", 'fridge bin restore Dentist --kind event'],
        cmd_restore,
    )
    p.add_argument("item", help="What to restore: its name, or an id such as X12")
    p.add_argument("--kind", choices=kinds)
    p.add_argument("--dry-run", action="store_true")
