"""To-do lists, tasks and chores: due dates, priority, subtasks, notes, photos, repeats, rotation and stars.

- Lists: a shared "Household Tasks" list, a personal "My Tasks" for each adult (only its owner ever sees it, and
  never in a group chat), and custom lists with an emoji and colour.
- Assigning a task to someone else leaves them a notice (notices.py); kids and teens see their chores on the
  fridge sheet instead, and an adult ticks them off with --by <kid>, which gives the kid a star.
- Repeating tasks: finishing one creates the next exactly once (its id is the series plus the date), with the
  next person in the rotation.
"""

from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path

from . import access, notices, recur
from .util import ToolError, clean_text, day_text, fold, get_tz, match_one, now_stamp, parse_stamp, plural

HOUSEHOLD_LIST = "Household Tasks"
PERSONAL_LIST = "My Tasks"
PRIORITIES = ("none", "low", "medium", "high")
DONE_VISIBLE_HOURS = 24
WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


# --------------------------------------------------------------------------- lists


def new_list(hh, name: str, owner: str | None = None, icon: str | None = None, color=None, default=None) -> dict:
    record = {
        "id": hh.next_id("list"),
        "name": name,
        "kind": "todo",
        "owner": owner,  # a member id for a personal list; None for a shared one
        "icon": icon or ("✅" if owner else "🏠"),
        "color": color,
        "created_at": now_stamp(),
    }
    if default:
        record["default"] = default
    return record


def ensure_default_lists(hh) -> list:
    """Create any missing default lists: Household Tasks, and My Tasks for each adult. Returns what was made."""
    data = hh.data("todos")
    made = []
    if not any(lst.get("default") == "household" for lst in data["lists"]):
        lst = new_list(hh, HOUSEHOLD_LIST, default="household")
        data["lists"].insert(0, lst)
        made.append(lst)
    for member in hh.members:
        if member["role"] not in access.ADULT_ROLES:
            continue
        if not any(lst.get("default") == "personal" and lst.get("owner") == member["id"] for lst in data["lists"]):
            lst = new_list(hh, PERSONAL_LIST, owner=member["id"], default="personal")
            data["lists"].append(lst)
            made.append(lst)
    if made:
        hh.touch("todos")
    return made


def forget_member(hh, member_id: str) -> list:
    """Erase a member from to-dos: their personal lists and tasks go; they're unassigned and leave rotations."""
    data = hh.data("todos")
    changes = []
    personal = {lst["id"] for lst in data["lists"] if lst.get("owner") == member_id}
    if personal:
        before = len(data["tasks"])
        data["tasks"] = [t for t in data["tasks"] if t.get("list") not in personal]
        data["lists"] = [lst for lst in data["lists"] if lst["id"] not in personal]
        changes.append(f"deleted their personal list ({before - len(data['tasks'])} tasks)")
    unassigned, passed = [], []
    for task in data["tasks"]:
        rotation = task.get("rotation")
        if rotation and member_id in rotation.get("members", []):
            old = rotation["members"]
            index = rotation.get("index", 0) % len(old)
            rotation["members"] = [m for m in old if m != member_id]
            if not rotation["members"]:
                task["rotation"] = None
            elif old[index] == member_id:  # it was their turn: it passes to the next person in line
                nxt = old[(index + 1) % len(old)]
                rotation["index"] = rotation["members"].index(nxt)
                if task.get("assignee") == member_id and not is_done(task):
                    task["assignee"] = nxt
                    passed.append(task["title"])
            else:
                rotation["index"] = rotation["members"].index(old[index])
        if task.get("assignee") == member_id:
            task["assignee"] = None
            if not is_done(task):
                unassigned.append(task["title"])
        for key in ("created_by", "completed_by", "star_to"):
            if task.get(key) == member_id:
                task[key] = None
    if passed:
        changes.append(f"passed their turn on {', '.join(dict.fromkeys(passed))} to the next person")
    if unassigned:
        names = list(dict.fromkeys(unassigned))
        more = f" and {len(names) - 5} more" if len(names) > 5 else ""
        changes.append(f"left {plural(len(unassigned), 'task')} with nobody on: {', '.join(names[:5])}{more}")
    hh.touch("todos")
    return changes


def list_visible(viewer, lst: dict) -> bool:
    if lst.get("deleted_at"):
        return False
    if lst.get("owner"):
        return viewer.sees_private_of(lst["owner"])
    return viewer.sees("todos")


def visible_lists(ctx, data: dict) -> list:
    if not ctx.viewer.can_act("todos", "view"):
        return []
    lists = [lst for lst in data["lists"] if list_visible(ctx.viewer, lst)]
    # My own list first, then shared lists in creation order (ported ordering).
    return sorted(lists, key=lambda lst: (0 if lst.get("owner") == ctx.member["id"] else 1))


def find_list(ctx, data: dict, query=None, need: str = "view", mine: bool = False) -> dict:
    """A to-do list by name or id. "My Tasks" (or --mine) is always the person's own list; the default is the
    shared Household Tasks list."""
    ctx.viewer.require("todos", need, "see to-dos" if need == "view" else "change to-dos")
    pool = visible_lists(ctx, data)
    if mine or fold(query) in ("my tasks", "mine", "my list", "me"):
        own = [lst for lst in pool if lst.get("owner") == ctx.member["id"]]
        if not own:
            raise ToolError(
                "Personal lists are private, so they don't show in group chats.",
                hint="Ask for your own tasks in a direct chat.",
                code="hidden_in_group" if ctx.viewer.group else "not_found",
            )
        return own[0]
    if not query:
        lst = next((x for x in pool if x.get("default") == "household"), None) or next(iter(pool), None)
        if lst is None:
            raise ToolError("There's no to-do list here.", hint="Make one: fridge todo list-new --name Chores",
                            code="not_found")  # fmt: skip
    else:
        lst = match_one(pool, query, "to-do list", hint="See the lists with: fridge todo lists")
    ctx.viewer.require_sees("todos")
    return lst


# --------------------------------------------------------------------------- dates and display


def describe_due(due: str | None, today: _dt.date, settings: dict | None = None) -> dict | None:
    """Day labels (ported): Today, Tomorrow, Yesterday, a weekday name for the next 2-6 days, else a short date.
    Overdue means a past day."""
    if not due:
        return None
    day = _dt.date.fromisoformat(due)
    diff = (day - today).days
    if diff == 0:
        label = "Today"
    elif diff == 1:
        label = "Tomorrow"
    elif diff == -1:
        label = "Yesterday"
    elif 2 <= diff <= 6:
        label = WEEKDAY_NAMES[day.weekday()]
    else:
        label = day_text(day, settings, today, weekday=False)
    return {"date": due, "label": label, "overdue": diff < 0}


def parse_priority(value) -> int:
    if value is None:
        return 0
    text = fold(value)
    if text in PRIORITIES:
        return PRIORITIES.index(text)
    if re.fullmatch(r"[0-3]", text):
        return int(text)
    if re.fullmatch(r"!{1,3}", text):
        return len(text)
    if text in ("urgent", "important", "top"):
        return 3
    raise ToolError(f"{value!r} isn't a priority.", hint="Use none, low, medium or high.", code="bad_priority")


def is_done(task: dict) -> bool:
    return bool(task.get("completed_at"))


def task_view(hh, task: dict, today: _dt.date, children=None) -> dict:
    out = {
        "id": task["id"],
        "title": task["title"],
        "list": task["list"],
        "due": describe_due(task.get("due"), today, hh.settings),
        "priority": PRIORITIES[int(task.get("priority") or 0)],
        "assignee": hh.member_name(task.get("assignee")),
        "done": is_done(task),
    }
    if task.get("notes"):
        out["notes"] = task["notes"]
    if task.get("rrule"):
        out["repeats"] = recur.describe(task["rrule"])
    if task.get("rotation"):
        out["rotation"] = [hh.member_name(m) for m in task["rotation"]["members"]]
    if task.get("photos"):
        out["photos"] = list(task["photos"])
    if is_done(task):
        out["completed_at"] = task["completed_at"]
        out["completed_by"] = hh.member_name(task.get("completed_by"))
        if task.get("star_to"):
            out["star_to"] = hh.member_name(task["star_to"])
    if children:
        out["subtasks"] = [{"id": c["id"], "title": c["title"], "done": is_done(c)} for c in children]
        out["progress"] = f"{sum(1 for c in children if is_done(c))}/{len(children)}"
    return out


def build_tree(tasks: list, now: _dt.datetime):
    """One level of subtasks (ported): orphaned subtasks show as top-level; open tasks, and tasks done in the last
    24 hours, newest first."""
    ids = {t["id"] for t in tasks}
    children: dict = {}
    parents = []
    for task in tasks:
        parent = task.get("parent")
        if parent and parent in ids:
            children.setdefault(parent, []).append(task)
        else:
            parents.append(task)
    open_tasks = [t for t in parents if not is_done(t)]
    cutoff = now - _dt.timedelta(hours=DONE_VISIBLE_HOURS)
    done = [t for t in parents if is_done(t) and parse_stamp(t["completed_at"]) >= cutoff]
    done.sort(key=lambda t: (t["completed_at"], t["id"]), reverse=True)
    return open_tasks, done, children


def sort_open(tasks: list) -> list:
    """Overdue and soonest first, then higher priority, then oldest; tasks without a due date last."""
    return sorted(tasks, key=lambda t: (t.get("due") is None, t.get("due") or "", -int(t.get("priority") or 0),
                                        t.get("created_at", ""), t["id"]))  # fmt: skip


def prune_done(hh, data: dict) -> int:
    """Finished tasks older than the retention period go (star totals stay on the member)."""
    days = int(hh.settings.get("retention_days") or 90)
    cutoff = hh.now() - _dt.timedelta(days=days)
    old = {t["id"] for t in data["tasks"] if is_done(t) and parse_stamp(t["completed_at"]) < cutoff}
    if not old:
        return 0
    data["tasks"] = [t for t in data["tasks"] if t["id"] not in old and t.get("parent") not in old]
    hh.touch("todos")
    return len(old)


# --------------------------------------------------------------------------- finding tasks


def visible_tasks(ctx, data: dict) -> list:
    lists = {lst["id"] for lst in visible_lists(ctx, data)}
    return [t for t in data["tasks"] if t["list"] in lists]


def find_task(ctx, data: dict, query, include_done: bool = True) -> dict:
    tasks = visible_tasks(ctx, data)
    open_first = [t for t in tasks if not is_done(t)] + ([t for t in tasks if is_done(t)] if include_done else [])
    try:
        return match_one(open_first, query, "task", key="title", hint="See the tasks with: fridge todo show")
    except ToolError as exc:
        if exc.code == "ambiguous":
            open_matches = [c for c in exc.extra.get("candidates", []) if any(
                t["id"] == c["id"] and not is_done(t) for t in tasks)]  # fmt: skip
            if len(open_matches) == 1:
                return next(t for t in tasks if t["id"] == open_matches[0]["id"])
        raise


def _member(ctx, query) -> dict:
    from .context import find_member

    return find_member(ctx.household, query)


def _check_assignee(ctx, lst: dict, member: dict) -> None:
    if lst.get("owner") and member["id"] != lst["owner"]:
        raise ToolError(
            f"{lst['name']} is a personal list, so its tasks can't go to someone else.",
            hint=f'Put it on a shared list instead: --list "{HOUSEHOLD_LIST}"',
            code="private_list",
        )
    if not access.can(member, "todos", "view"):
        raise ToolError(
            f"{member['name']} can't see to-dos, so they wouldn't know about it.",
            hint=f"The owner can change that: fridge member access {member['name']} --set todos=view",
            code="cannot_see_todos",
        )


def _rotation(ctx, text: str, first: dict | None) -> dict:
    names = [part.strip() for part in re.split(r",|\band\b|&", text) if part.strip()]
    if len(names) < 2:
        raise ToolError("A rotation needs at least two people.", hint='e.g. --rotate "Theo, Lily, Zoe"',
                        code="bad_rotation")  # fmt: skip
    members = []
    for name in names:
        member = _member(ctx, name)
        if member["id"] in members:
            raise ToolError(f"{member['name']} is in the rotation twice.", code="bad_rotation")
        members.append(member["id"])
    index = members.index(first["id"]) if first and first["id"] in members else 0
    return {"members": members, "index": index}


def _next_rotation(hh, rotation: dict) -> tuple:
    """The next person after the current one, skipping members who've left (ported rule). Returns (assignee or
    None, new index); if nobody is left, the task is unassigned but the turn still moves on."""
    members = rotation["members"]
    current = int(rotation.get("index", -1))
    for step in range(1, len(members) + 1):
        index = (current + step) % len(members)
        if hh.member(members[index]):
            return members[index], index
    return None, (current + 1) % len(members)


def new_task(hh, lst: dict, title: str, created_by: str | None, parent=None, notes=None, assignee=None, due=None,
             priority: int = 0, rrule=None, rotation=None) -> dict:  # fmt: skip
    """A task record (the caller appends it). On a personal list it belongs to the list's owner."""
    task_id = hh.next_id("task")
    return {
        "id": task_id,
        "list": lst["id"],
        "parent": parent,
        "title": title,
        "notes": notes,
        "assignee": assignee or (lst["owner"] if lst.get("owner") else None),
        "due": due,
        "priority": priority,
        "photos": [],
        "rrule": rrule,
        "series": task_id if rrule else None,
        "occurrence": 1,
        "rotation": rotation,
        "completed_at": None,
        "created_by": created_by,
        "created_at": now_stamp(),
    }


# --------------------------------------------------------------------------- commands: lists


def cmd_lists(ctx, args) -> dict:
    hh = ctx.household
    data = hh.data("todos")
    views = []
    for lst in visible_lists(ctx, data):
        open_count = sum(1 for t in data["tasks"] if t["list"] == lst["id"] and not t.get("parent") and not is_done(t))
        views.append({"id": lst["id"], "name": lst["name"], "icon": lst.get("icon"), "personal": bool(lst.get("owner")),
                      "open": open_count, "label": plural(open_count, "task")})  # fmt: skip
    text = "\n".join(f"{v['icon']} {v['name']}: {v['label']}" for v in views) or "No to-do lists here."
    return {"lists": views, "text": text, "summary": f"{plural(len(views), 'to-do list')}."}


def cmd_list_new(ctx, args) -> dict:
    ctx.viewer.require("todos", "edit", "make to-do lists")
    ctx.viewer.require_sees("todos")
    hh = ctx.household
    name = clean_text(args.name, "list name", max_len=60)
    with hh.transaction(dry_run=args.dry_run):
        data = hh.data("todos")
        if any(fold(lst["name"]) == fold(name) and not lst.get("owner") and not lst.get("deleted_at")
               for lst in data["lists"]) or fold(name) == fold(PERSONAL_LIST):  # fmt: skip
            raise ToolError(f"There's already a list called {name}.", code="exists")
        color = None
        if args.color:
            from .members import color_hex

            color = color_hex(args.color)
        lst = new_list(hh, name, icon=args.icon or "📋", color=color)
        data["lists"].append(lst)
        hh.touch("todos")
        hh.log("todo.list_new", ctx.member["id"], list=lst["id"])
    verb = "Would make" if args.dry_run else "Made"
    return {"list": {"id": lst["id"], "name": name, "icon": lst["icon"]}, "dry_run": args.dry_run,
            "summary": f"{verb} the to-do list {lst['icon']} {name}."}  # fmt: skip


def cmd_list_edit(ctx, args) -> dict:
    hh = ctx.household
    with hh.transaction():
        data = hh.data("todos")
        lst = find_list(ctx, data, args.list, need="edit")
        changed = []
        if args.name:
            lst["name"] = clean_text(args.name, "list name", max_len=60)
            changed.append("name")
        if args.icon:
            lst["icon"] = clean_text(args.icon, "icon", max_len=8)
            changed.append("icon")
        if args.color:
            from .members import color_hex

            lst["color"] = color_hex(args.color)
            changed.append("colour")
        if not changed:
            raise ToolError("Nothing to change.", hint="Pass --name, --icon or --color.", code="usage")
        hh.touch("todos")
        hh.log("todo.list_edit", ctx.member["id"], list=lst["id"], fields=changed)
    return {"summary": f"Updated {lst['name']}: {', '.join(changed)}."}


def cmd_list_delete(ctx, args) -> dict:
    hh = ctx.household
    with hh.transaction():
        data = hh.data("todos")
        lst = find_list(ctx, data, args.list, need="edit")
        if lst.get("default"):
            raise ToolError(f"{lst['name']} is a default list and can't be deleted.", hint="You can rename it.",
                            code="protected")  # fmt: skip
        lst["deleted_at"] = now_stamp()
        hh.touch("todos")
        hh.log("todo.list_delete", ctx.member["id"], list=lst["id"])
    return {"summary": f"Deleted {lst['name']}. Restore it with: fridge todo list-restore \"{lst['name']}\""}


def cmd_list_restore(ctx, args) -> dict:
    ctx.viewer.require("todos", "edit", "restore lists")
    hh = ctx.household
    with hh.transaction():
        data = hh.data("todos")
        deleted = [lst for lst in data["lists"] if lst.get("deleted_at") and not lst.get("owner")]
        lst = match_one(deleted, args.list, "deleted list")
        lst.pop("deleted_at", None)
        hh.touch("todos")
        hh.log("todo.list_restore", ctx.member["id"], list=lst["id"])
    return {"summary": f"Restored {lst['name']}."}


# --------------------------------------------------------------------------- commands: tasks


def week_start(hh) -> int:
    """The household's first day of the week as a weekday number (Monday = 0)."""
    names = [d.lower() for d in WEEKDAY_NAMES]
    start = hh.settings.get("week_start", "monday")
    return names.index(start) if start in names else 0


def _due(hh, value) -> str | None:
    if value is None:
        return None
    return hh.date(value).isoformat()


def cmd_add(ctx, args) -> dict:
    hh = ctx.household
    title = clean_text(args.title, "task title", max_len=200)
    with hh.transaction(dry_run=args.dry_run):
        data = hh.data("todos")
        prune_done(hh, data)
        parent = None
        if args.parent:
            parent = find_task(ctx, data, args.parent, include_done=False)
            if parent.get("parent"):
                raise ToolError("Subtasks can't have their own subtasks (one level only).", code="too_deep")
            lst = next(x for x in data["lists"] if x["id"] == parent["list"])
            ctx.viewer.require("todos", "edit", "change to-dos")
        else:
            lst = find_list(ctx, data, args.list, need="edit", mine=args.mine)
        assignee = _member(ctx, args.assign) if args.assign else None
        if assignee:
            _check_assignee(ctx, lst, assignee)
        if parent and (args.repeat or args.rotate):
            raise ToolError("Subtasks don't repeat; set the repeat on the main task.", code="usage")
        due = _due(hh, args.due)
        rrule, moved = None, False
        if args.repeat:
            start = _dt.date.fromisoformat(due) if due else hh.today()
            until = hh.date(args.until) if args.until else None
            rrule = recur.from_words(args.repeat, start, until=until, count=args.times)
            # The first one falls on the first day the repeat allows ("weekly on tue" added on a Monday: Tuesday).
            first = recur.next_after(recur.parse(rrule), start, start - _dt.timedelta(days=1)) or start
            moved = bool(due) and first != start
            due = first.isoformat()
        elif args.until or args.times:
            raise ToolError("--until and --times go with --repeat.", code="usage")
        rotation = None
        if args.rotate:
            if not rrule:
                raise ToolError("A rotation needs a repeat (e.g. --repeat weekly).", code="bad_rotation")
            if lst.get("owner"):
                raise ToolError("Personal lists can't rotate between people.", code="private_list")
            rotation = _rotation(ctx, args.rotate, assignee)
            assignee = hh.member(rotation["members"][rotation["index"]])
            for member_id in rotation["members"]:
                _check_assignee(ctx, lst, hh.member(member_id))
        task = new_task(
            hh, lst, title, ctx.member["id"],
            parent=parent["id"] if parent else None,
            notes=clean_text(args.notes, "notes", max_len=2000, required=False),
            assignee=assignee["id"] if assignee else None,
            due=due, priority=parse_priority(args.priority), rrule=rrule, rotation=rotation,
        )  # fmt: skip
        data["tasks"].append(task)
        hh.touch("todos")
        delivery = notices.assignment(hh, task, assignee, ctx.member, ctx.viewer) if assignee else None
        hh.log("todo.add", ctx.member["id"], task=task["id"], list=lst["id"])
        view = task_view(hh, task, hh.today())
    verb = "Would add" if args.dry_run else "Added"
    summary = f"{verb} \"{title}\" to {lst['name']}"
    if view["due"]:
        label = view["due"]["label"]
        summary += f", due {label.lower() if label in ('Today', 'Tomorrow') else label}"
    if rrule:
        summary += f", repeating {recur.describe(rrule)}"
    if moved:
        summary += " (moved to the first day that matches the repeat)"
    if rotation:
        summary += f", rotating {' → '.join(hh.member_name(m) for m in rotation['members'])}"
    summary += "."
    out = {"task": view, "dry_run": args.dry_run}
    out.update(_delivery_words(assignee, delivery))
    out["summary"] = summary + out.pop("_extra", "")
    return out


def _delivery_words(assignee, delivery) -> dict:
    if not assignee or not delivery:
        return {}
    how = delivery["how"]
    name = assignee["name"]
    if how == "self":
        return {"_extra": ""}
    if how == "fridge_sheet":
        return {"_extra": f" It's on {name}'s chore list and the fridge sheet.", "delivery": how}
    if how == "in_this_chat":
        return {"_extra": f" Tell {name} here: they're in this chat.", "delivery": how}
    return {
        "_extra": f" {name} will hear about it the next time they talk to me.",
        "delivery": how,
        "outside_chat": f"Don't message {name} anywhere else unless the owner says so.",
    }


def _award(hh, task: dict, by: dict | None) -> str | None:
    """A kid or teen who did the chore gets a star (once per task)."""
    if not by or not access.is_minor(by) or task.get("stars_awarded"):
        return None
    member = hh.member(by["id"])
    member["stars"] = int(member.get("stars", 0)) + 1
    hh.touch("household")
    task["stars_awarded"] = 1
    task["star_to"] = member["id"]
    return member["name"]


def _materialize_next(hh, data: dict, task: dict, completed_day: _dt.date) -> dict | None:
    """Create the next occurrence of a repeating task, once only (its id is the series plus the date)."""
    if task.get("parent") or not task.get("rrule"):
        return None
    due = _dt.date.fromisoformat(task["due"]) if task.get("due") else None
    nxt = recur.next_due(task["rrule"], due, completed_day, occurrence=int(task.get("occurrence") or 1))
    if nxt is None:
        return None
    series = task.get("series") or task["id"]
    new_id = f"{series}.{nxt:%Y%m%d}"
    existing = next((t for t in data["tasks"] if t["id"] == new_id), None)
    if existing:
        return existing
    assignee = task.get("assignee")
    rotation = None
    if task.get("rotation"):
        assignee, index = _next_rotation(hh, task["rotation"])
        rotation = {"members": list(task["rotation"]["members"]), "index": index}
    new = {
        "id": new_id,
        "list": task["list"],
        "parent": None,
        "title": task["title"],
        "notes": task.get("notes"),
        "assignee": assignee,
        "due": nxt.isoformat(),
        "priority": task.get("priority") or 0,
        "photos": [],
        "rrule": task["rrule"],
        "series": series,
        "occurrence": int(task.get("occurrence") or 1) + 1,
        "rotation": rotation,
        "completed_at": None,
        "created_by": task.get("created_by"),
        "created_at": now_stamp(),
    }
    subtasks = [t for t in data["tasks"] if t.get("parent") == task["id"]]
    data["tasks"].append(new)
    for index, sub in enumerate(subtasks):  # the next one starts with the same checklist, all unticked
        data["tasks"].append({
            "id": f"{new_id}.{index + 1}", "list": task["list"], "parent": new_id, "title": sub["title"],
            "notes": None, "assignee": None, "due": None, "priority": 0, "photos": [], "rrule": None,
            "series": None, "occurrence": 1, "rotation": None, "completed_at": None,
            "created_by": sub.get("created_by"), "created_at": now_stamp(),
        })  # fmt: skip
    return new


def _done_today_in_series(hh, data: dict, task: dict, today: _dt.date) -> dict | None:
    """For a repeating task due in the future: the occurrence of the same series finished today, if any."""
    if not task.get("series") or not task.get("due") or task["due"] <= today.isoformat():
        return None
    from .util import get_tz

    tz = get_tz(hh.tz())
    for other in data["tasks"]:
        if other.get("series") == task["series"] and other["id"] != task["id"] and is_done(other):
            if parse_stamp(other["completed_at"]).astimezone(tz).date() == today:
                return other
    return None


def cmd_done(ctx, args) -> dict:
    hh = ctx.household
    by = _member(ctx, args.by) if args.by else None
    results = []
    with hh.transaction(dry_run=args.dry_run):
        data = hh.data("todos")
        ctx.viewer.require("todos", "edit", "tick off tasks")
        today = hh.today()
        for query in args.tasks:
            task = find_task(ctx, data, query)
            if is_done(task):
                results.append({"task": task["id"], "title": task["title"], "status": "already_done"})
                continue
            early = _done_today_in_series(hh, data, task, today) if fold(query) != fold(task["id"]) else None
            if early:
                # Asked twice by name: this period's one is done; don't silently tick off the next one too.
                results.append({"task": early["id"], "title": task["title"], "status": "already_done",
                                "next": {"id": task["id"], "due": describe_due(task["due"], today, hh.settings)}})  # fmt: skip
                continue
            doer = by
            if doer is None and task.get("assignee"):
                assignee = hh.member(task["assignee"])
                if assignee and access.is_minor(assignee):
                    doer = assignee  # a kid's chore marked done: the star goes to them (say if someone else did it)
            task["completed_at"] = now_stamp()
            task["completed_by"] = (doer or ctx.member)["id"]
            star = _award(hh, task, doer)
            nxt = _materialize_next(hh, data, task, hh.today())
            entry = {"task": task["id"], "title": task["title"], "status": "done", "star_to": star}
            if nxt:
                entry["next"] = {"id": nxt["id"], "due": describe_due(nxt["due"], hh.today(), hh.settings),
                                 "assignee": hh.member_name(nxt.get("assignee"))}  # fmt: skip
                if nxt.get("assignee") and nxt["assignee"] != task.get("assignee"):
                    who = hh.member(nxt["assignee"])
                    if who:
                        notices.assignment(hh, nxt, who, ctx.member, ctx.viewer, turn=True)
            results.append(entry)
        hh.touch("todos")
        hh.log("todo.done", ctx.member["id"], tasks=[r["task"] for r in results], by=by["id"] if by else None)
        stars = {m["name"]: m.get("stars", 0) for m in hh.members if access.is_minor(m)}
    parts = []
    for r in results:
        if r["status"] == "already_done":
            text = f"\"{r['title']}\" was already done"
            if r.get("next"):
                when = _in_sentence(r["next"]["due"]["label"])
                also = "too" if when.startswith("today") else "early"
                text += f" today; the next one is {when} (to tick that one off {also}, use its id {r['next']['id']})"
            parts.append(text)
            continue
        text = f"Done: {r['title']}"
        if r.get("star_to"):
            text += f" (a star for {r['star_to']}, now {stars.get(r['star_to'], 0)})"
        if r.get("next"):
            when = _in_sentence(r["next"]["due"]["label"]) if r["next"]["due"] else "later"
            who = f" for {r['next']['assignee']}" if r["next"]["assignee"] else ""
            text += f"; next one {when}{who}"
        parts.append(text)
    return {"results": results, "dry_run": args.dry_run, "summary": ". ".join(parts) + "."}


def _in_sentence(label: str) -> str:
    """A due label inside a sentence: "Tomorrow" reads "tomorrow" there; dates and weekdays keep their capitals."""
    first = label.split(" ", 1)[0].rstrip(",")
    return label[:1].lower() + label[1:] if first in ("Today", "Tomorrow", "Yesterday") else label


def cmd_undo(ctx, args) -> dict:
    hh = ctx.household
    with hh.transaction():
        data = hh.data("todos")
        ctx.viewer.require("todos", "edit", "change to-dos")
        task = find_task(ctx, data, args.task)
        if not is_done(task) and task.get("series") and fold(args.task) != fold(task["id"]):
            # By name, a repeating chore finds its open next one: undo the last one ticked off instead.
            done = [t for t in visible_tasks(ctx, data) if t.get("series") == task["series"] and is_done(t)]
            if done:
                task = max(done, key=lambda t: t["completed_at"])
        if not is_done(task):
            return {"summary": f"\"{task['title']}\" isn't done yet."}
        task["completed_at"] = None
        task["completed_by"] = None
        took = None
        if task.get("stars_awarded") and task.get("star_to"):
            member = hh.member(task["star_to"])
            if member:
                member["stars"] = max(0, int(member.get("stars", 0)) - 1)
                hh.touch("household")
                took = member["name"]
        task["stars_awarded"] = None
        task["star_to"] = None
        hh.touch("todos")
        hh.log("todo.undo", ctx.member["id"], task=task["id"])
        later = [t for t in data["tasks"] if t.get("series") and t.get("series") == task.get("series")
                 and t["id"] != task["id"] and not is_done(t)]  # fmt: skip
    summary = f"\"{task['title']}\" is open again."
    if took:
        summary += f" Took back {took}'s star."
    if later:
        summary += " The next one is still on the list; delete it if it isn't needed."
    return {"summary": summary}


def cmd_edit(ctx, args) -> dict:
    hh = ctx.household
    with hh.transaction(dry_run=args.dry_run):
        data = hh.data("todos")
        ctx.viewer.require("todos", "edit", "change to-dos")
        task = find_task(ctx, data, args.task)
        lst = next(x for x in data["lists"] if x["id"] == task["list"])
        changed = []
        delivery = None
        if args.title:
            task["title"] = clean_text(args.title, "task title", max_len=200)
            changed.append("title")
        if args.notes is not None:
            task["notes"] = clean_text(args.notes, "notes", max_len=2000, required=False)
            changed.append("notes")
        if args.list:
            target = find_list(ctx, data, args.list, need="edit")
            if target.get("owner") and task.get("assignee") not in (None, target["owner"]):
                raise ToolError("Personal lists can't hold someone else's task.", code="private_list")
            task["list"] = target["id"]
            for sub in data["tasks"]:
                if sub.get("parent") == task["id"]:
                    sub["list"] = target["id"]
            lst = target
            changed.append("list")
        if args.no_due:
            task["due"] = None
            changed.append("due date")
        elif args.due:
            task["due"] = _due(hh, args.due)
            changed.append("due date")
        if args.priority is not None:
            task["priority"] = parse_priority(args.priority)
            changed.append("priority")
        if args.no_repeat:
            task["rrule"] = None
            task["rotation"] = None  # a rotation without a repeat would never turn
            changed.append("repeat")
        elif args.repeat:
            start = _dt.date.fromisoformat(task["due"]) if task.get("due") else hh.today()
            until = hh.date(args.until) if args.until else None
            task["rrule"] = recur.from_words(args.repeat, start, until=until, count=args.times)
            task["series"] = task.get("series") or task["id"]
            task["due"] = task.get("due") or start.isoformat()
            changed.append("repeat")
        if args.no_rotate:
            task["rotation"] = None
            changed.append("rotation")
        elif args.rotate:
            if not task.get("rrule"):
                raise ToolError("A rotation needs a repeat (add --repeat weekly).", code="bad_rotation")
            current = hh.member(task["assignee"]) if task.get("assignee") else None
            task["rotation"] = _rotation(ctx, args.rotate, current)  # keeps the current person's turn if still in it
            for member_id in task["rotation"]["members"]:
                _check_assignee(ctx, lst, hh.member(member_id))
            task["assignee"] = task["rotation"]["members"][task["rotation"]["index"]]
            changed.append("rotation")
        if args.unassign:
            task["assignee"] = None
            changed.append("assignee")
        elif args.assign:
            member = _member(ctx, args.assign)
            _check_assignee(ctx, lst, member)
            if member["id"] != task.get("assignee"):
                task["assignee"] = member["id"]
                if task.get("rotation") and member["id"] in task["rotation"]["members"]:
                    task["rotation"]["index"] = task["rotation"]["members"].index(member["id"])
                if not is_done(task):
                    delivery = notices.assignment(hh, task, member, ctx.member, ctx.viewer)
            changed.append("assignee")
        if not changed:
            raise ToolError("Nothing to change.", hint="See: fridge todo edit --help", code="usage")
        hh.touch("todos")
        hh.log("todo.edit", ctx.member["id"], task=task["id"], fields=changed)
        view = task_view(hh, task, hh.today())
        assignee = hh.member(task["assignee"]) if task.get("assignee") else None
    out = {"task": view, "dry_run": args.dry_run}
    out.update(_delivery_words(assignee, delivery))
    out["summary"] = f"Updated \"{view['title']}\": {', '.join(changed)}." + out.pop("_extra", "")
    return out


def cmd_assign(ctx, args) -> dict:
    args.assign, args.unassign = args.member, False
    for key in ("title", "notes", "list", "due", "priority", "repeat", "rotate", "until", "times"):
        setattr(args, key, None)
    args.no_due = args.no_repeat = args.no_rotate = False
    return cmd_edit(ctx, args)


def cmd_delete(ctx, args) -> dict:
    hh = ctx.household
    with hh.transaction():
        data = hh.data("todos")
        ctx.viewer.require("todos", "edit", "delete tasks")
        task = find_task(ctx, data, args.task)
        gone = [t for t in data["tasks"] if t["id"] == task["id"] or t.get("parent") == task["id"]]
        ids = {t["id"] for t in gone}
        data["tasks"] = [t for t in data["tasks"] if t["id"] not in ids]
        hh.touch("todos")
        hh.log("todo.delete", ctx.member["id"], task=task["id"], count=len(gone))
    extra = f" and its {plural(len(gone) - 1, 'subtask')}" if len(gone) > 1 else ""
    return {"summary": f"Deleted \"{task['title']}\"{extra}."}


def cmd_photo(ctx, args) -> dict:
    hh = ctx.household
    with hh.transaction():
        data = hh.data("todos")
        ctx.viewer.require("todos", "edit", "change to-dos")
        task = find_task(ctx, data, args.task)
        photos = task.setdefault("photos", [])
        if args.add:
            path = str(Path(args.add).expanduser())
            if not Path(path).is_file():
                raise ToolError(f"There's no file at {path}.", hint="Save the photo first, then pass its path.",
                                code="no_file")  # fmt: skip
            if path not in photos:  # each photo once
                photos.append(path)
            summary = f"Added the photo to \"{task['title']}\" ({plural(len(photos), 'photo')})."
        elif args.remove:
            if args.remove not in photos:
                raise ToolError("That photo isn't on this task.", code="not_found")
            photos.remove(args.remove)
            summary = f"Removed the photo from \"{task['title']}\"."
        else:
            raise ToolError("Pass --add <path> or --remove <path>.", code="usage")
        hh.touch("todos")
        hh.log("todo.photo", ctx.member["id"], task=task["id"])
    return {"photos": list(photos), "summary": summary}


def _filter(hh, tasks: list, args, today: _dt.date) -> list:
    out = tasks
    if getattr(args, "assignee", None):
        from .context import find_member

        member = find_member(hh, args.assignee)
        out = [t for t in out if t.get("assignee") == member["id"]]
    due = getattr(args, "due_filter", None)
    if due == "today":
        out = [t for t in out if t.get("due") and t["due"] <= today.isoformat()]
    elif due == "overdue":
        out = [t for t in out if t.get("due") and t["due"] < today.isoformat()]
    elif due == "week":
        out = [t for t in out if t.get("due") and t["due"] <= (today + _dt.timedelta(days=6)).isoformat()]
    return out


def cmd_show(ctx, args) -> dict:
    hh = ctx.household
    data = hh.data("todos")
    today = hh.today()
    lists = [find_list(ctx, data, args.list, mine=args.mine)] if (args.list or args.mine) else visible_lists(ctx, data)
    if not lists:
        ctx.viewer.require_sees("todos")
    sections, lines = [], []
    for lst in lists:
        tasks = [t for t in data["tasks"] if t["list"] == lst["id"]]
        open_tasks, done, children = build_tree(tasks, hh.now())
        open_tasks = sort_open(_filter(hh, open_tasks, args, today))
        views = [task_view(hh, t, today, children.get(t["id"])) for t in open_tasks]
        done_views = [task_view(hh, t, today) for t in done] if args.done else []
        if not views and not done_views and (args.assignee or args.due_filter):
            continue
        sections.append({"list": {"id": lst["id"], "name": lst["name"], "icon": lst.get("icon")},
                         "open": views, "done_today": done_views, "done_count": len(done)})  # fmt: skip
        lines.append(f"{lst.get('icon') or ''} {lst['name']}".strip())
        for v in views:
            bits = []
            if v["due"]:
                bits.append(("⚠️ " if v["due"]["overdue"] else "") + v["due"]["label"])
            if v["assignee"] and not (lst.get("owner")):
                bits.append(v["assignee"])
            if v["priority"] != "none":
                bits.append(v["priority"])
            if v.get("repeats"):
                bits.append("🔁")
            if v.get("progress"):
                bits.append(v["progress"])
            lines.append(f"  ☐ {v['title']}" + (f" — {', '.join(bits)}" if bits else ""))
        if not views:
            lines.append("  Nothing to do.")
        finished_today = [t for t in done if parse_stamp(t["completed_at"]).astimezone(get_tz(hh.tz())).date() == today]
        if finished_today and not args.done:
            lines.append(f"  Done today: {len(finished_today)}")
        for v in done_views:
            lines.append(f"  ☑ {v['title']}")
    total = sum(len(s["open"]) for s in sections)
    return {"lists": sections, "text": "\n".join(lines), "summary": f"{plural(total, 'open task')}."}


def cmd_task(ctx, args) -> dict:
    hh = ctx.household
    data = hh.data("todos")
    task = find_task(ctx, data, args.task)
    children = [t for t in data["tasks"] if t.get("parent") == task["id"]]
    view = task_view(hh, task, hh.today(), children)
    lst = next(x for x in data["lists"] if x["id"] == task["list"])
    view["list_name"] = lst["name"]
    return {"task": view, "summary": f"{view['title']} ({lst['name']})."}


def chore_chart(hh, data: dict, today: _dt.date, days: int = 7) -> list:
    """Each member's chores for the coming week (shared lists only), with the turns of rotating chores worked out
    the same way as the fridge sheet, plus their open tasks with no due date; and the kids' stars. Chores nobody
    is on come under "Anyone"."""
    last = today + _dt.timedelta(days=days - 1)
    shared = {lst["id"] for lst in data["lists"] if not lst.get("owner") and not lst.get("deleted_at")}
    overdue = [t for t in data["tasks"] if t["list"] in shared and not is_done(t) and not t.get("parent")
               and t.get("due") and t["due"] < today.isoformat()]  # fmt: skip
    turns = project_chores(hh, data, today, last)
    chart = []
    for member in hh.members + [None]:
        member_id = member["id"] if member else None
        rows = [task_view(hh, t, today) for t in sort_open([t for t in overdue if t.get("assignee") == member_id])]
        rows += [dict({"id": turn["task"], "title": turn["title"], "repeats": turn["repeats"]},
                      due=describe_due(turn["date"], today, hh.settings))
                 for turn in turns if turn["member_id"] == member_id]  # fmt: skip
        undated = [t for t in data["tasks"] if t["list"] in shared and t.get("assignee") == member_id and member
                   and not is_done(t) and not t.get("parent") and not t.get("due")]  # fmt: skip
        rows += [task_view(hh, t, today) for t in sort_open(undated)]
        if member is None and not rows:
            continue
        entry = {"member": member["name"] if member else "Anyone", "color": member["color"] if member else None,
                 "tasks": rows}  # fmt: skip
        if member and access.is_minor(member):
            entry["stars"] = int(member.get("stars", 0))
        chart.append(entry)
    return chart


def cmd_chores(ctx, args) -> dict:
    hh = ctx.household
    ctx.viewer.require_sees("todos")
    data = hh.data("todos")
    chart = chore_chart(hh, data, hh.today())
    if args.member:
        from .context import find_member

        wanted = find_member(hh, args.member)["name"]
        chart = [c for c in chart if c["member"] == wanted]
    lines = []
    for entry in chart:
        star = f" ⭐ {entry['stars']}" if "stars" in entry else ""
        lines.append(f"{entry['member']}{star}")
        for t in entry["tasks"]:
            when = f" ({t['due']['label']})" if t["due"] else ""
            lines.append(f"  ☐ {t['title']}{when}")
        if not entry["tasks"]:
            lines.append("  Nothing this week.")
    return {"chart": chart, "text": "\n".join(lines), "summary": "Chores for the coming week."}


def register(cli) -> None:
    grp = cli.group("todo", "To-dos and chores: lists, tasks, assigning, repeats, rotation, stars.")
    grp.add("lists", "Show the to-do lists you can see (your own list first).", ["fridge todo lists"], cmd_lists)
    p = grp.add("list-new", "Make a shared to-do list with an emoji and colour.",
                ['fridge todo list-new --name "Garden" --icon 🌱 --color green'], cmd_list_new)  # fmt: skip
    p.add_argument("--name", required=True)
    p.add_argument("--icon")
    p.add_argument("--color")
    p.add_argument("--dry-run", action="store_true")
    p = grp.add("list-edit", "Rename a to-do list or change its emoji or colour.",
                ['fridge todo list-edit Garden --icon 🌻'], cmd_list_edit)  # fmt: skip
    p.add_argument("list")
    p.add_argument("--name")
    p.add_argument("--icon")
    p.add_argument("--color")
    p = grp.add("list-delete", "Delete a custom to-do list (restorable).", ["fridge todo list-delete Garden"],
                cmd_list_delete)  # fmt: skip
    p.add_argument("list")
    p = grp.add("list-restore", "Bring back a deleted to-do list.", ["fridge todo list-restore Garden"],
                cmd_list_restore)  # fmt: skip
    p.add_argument("list")
    p = grp.add(
        "add",
        "Add a task. Assigning someone else leaves them a notice; --rotate turns a repeating chore between people.",
        [
            'fridge todo add "Book the dentist" --mine --due friday',
            'fridge todo add "Fix the gate" --assign Luis --due "this weekend" --priority high',
            'fridge todo add "Take out the bins" --repeat "weekly on mon" --rotate "Theo, Lily, Zoe"',
            'fridge todo add "Wipe the mirror" --parent "Clean the bathroom"',
        ],
        cmd_add,
    )
    p.add_argument("title")
    p.add_argument("--list", help='Which list (default: "Household Tasks")')
    p.add_argument("--mine", action="store_true", help="Put it on your own private My Tasks list")
    p.add_argument("--due", help="today, tomorrow, friday, next week, +3, 2026-11-02 ...")
    p.add_argument("--priority", help="none, low, medium or high")
    p.add_argument("--assign", help="Who it's for (a member)")
    p.add_argument("--notes")
    p.add_argument("--repeat", help='e.g. daily, weekdays, "weekly on mon,thu", "every 2 weeks", monthly')
    p.add_argument("--until", help="Last date for the repeat")
    p.add_argument("--times", type=int, help="How many times in all")
    p.add_argument("--rotate", help='People who take turns, in order: "Theo, Lily, Zoe"')
    p.add_argument("--parent", help="Make it a subtask of this task (one level only)")
    p.add_argument("--dry-run", action="store_true")
    p = grp.add(
        "show",
        "Show open tasks by list (overdue first), with today's finished ones counted.",
        ["fridge todo show", "fridge todo show --mine", "fridge todo show --assignee Luis --due week",
         "fridge todo show --list Garden --done"],
        cmd_show,
    )  # fmt: skip
    p.add_argument("--list")
    p.add_argument("--mine", action="store_true")
    p.add_argument("--assignee", help="Only this person's tasks")
    p.add_argument("--due", dest="due_filter", choices=("today", "overdue", "week"))
    p.add_argument("--done", action="store_true", help="List the tasks finished in the last 24 hours")
    p = grp.add("task", "Show one task with its subtasks.", ['fridge todo task "Fix the gate"'], cmd_task)
    p.add_argument("task")
    p = grp.add(
        "done",
        "Tick tasks off. --by <kid> gives the kid who did it a star; a repeating task makes its next one.",
        ['fridge todo done "Fix the gate"', 'fridge todo done "Take out the bins" --by Theo', "fridge todo done T4 T7"],
        cmd_done,
    )
    p.add_argument("tasks", nargs="+")
    p.add_argument("--by", help="Who actually did it (a kid or teen gets a star)")
    p.add_argument("--dry-run", action="store_true")
    p = grp.add("undo", "Re-open a finished task (and take back its star).", ['fridge todo undo "Fix the gate"'],
                cmd_undo)  # fmt: skip
    p.add_argument("task")
    p = grp.add(
        "edit",
        "Change a task: title, notes, list, due date, priority, assignee, repeat or rotation.",
        ['fridge todo edit "Fix the gate" --due tomorrow', 'fridge todo edit T9 --repeat "every 2 weeks" '
         '--rotate "Kai, Jess, Sam"', "fridge todo edit T3 --no-due"],
        cmd_edit,
    )  # fmt: skip
    p.add_argument("task")
    p.add_argument("--title")
    p.add_argument("--notes")
    p.add_argument("--list")
    p.add_argument("--due")
    p.add_argument("--no-due", action="store_true")
    p.add_argument("--priority")
    p.add_argument("--assign")
    p.add_argument("--unassign", action="store_true")
    p.add_argument("--repeat")
    p.add_argument("--until")
    p.add_argument("--times", type=int)
    p.add_argument("--no-repeat", action="store_true")
    p.add_argument("--rotate")
    p.add_argument("--no-rotate", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p = grp.add("assign", "Give a task to someone (they get a notice; kids see it on the fridge sheet).",
                ['fridge todo assign "Fix the gate" Luis'], cmd_assign)  # fmt: skip
    p.add_argument("task")
    p.add_argument("member")
    p.add_argument("--dry-run", action="store_true")
    p = grp.add("delete", "Delete a task and its subtasks.", ['fridge todo delete "Fix the gate"'], cmd_delete)
    p.add_argument("task")
    p = grp.add("photo", "Attach a saved photo to a task (kept as a file path), or remove one.",
                ['fridge todo photo "Fix the gate" --add /workspace/photos/gate.jpg'], cmd_photo)  # fmt: skip
    p.add_argument("task")
    p.add_argument("--add", help="Path of a saved photo")
    p.add_argument("--remove", help="Path to remove")
    p = grp.add("chores", "Everyone's chores for the coming week, with the kids' stars.",
                ["fridge todo chores", "fridge todo chores --member Theo"], cmd_chores)  # fmt: skip
    p.add_argument("--member")


def project_chores(hh, data: dict, first: _dt.date, last: _dt.date) -> list:
    """Every chore turn between two dates on shared lists: one-off tasks due then, and repeating tasks projected
    forward from their next occurrence with the rotation stepping on (only the next one is stored).
    Returns [{"date", "title", "member_id", "task", "repeats"}]."""
    shared = {lst["id"] for lst in data["lists"] if not lst.get("owner") and not lst.get("deleted_at")}
    out = []
    for task in data["tasks"]:
        if task["list"] not in shared or task.get("parent") or is_done(task) or not task.get("due"):
            continue
        due = _dt.date.fromisoformat(task["due"])
        if not task.get("rrule"):
            if first <= due <= last:
                out.append({"date": due.isoformat(), "title": task["title"], "member_id": task.get("assignee"),
                            "task": task["id"], "repeats": False})  # fmt: skip
            continue
        try:
            rule = recur.parse(task["rrule"])
        except ToolError:
            continue
        dates = recur.between(rule, due, due, last, include_start=True)
        rotation = task.get("rotation")
        index = int(rotation.get("index", 0)) if rotation else 0
        for step, day in enumerate(dates):
            who = task.get("assignee")
            if rotation and step:
                state = {"members": rotation["members"], "index": index}
                who, index = _next_rotation(hh, state)
            if day >= first:
                out.append({"date": day.isoformat(), "title": task["title"], "member_id": who, "task": task["id"],
                            "repeats": True})  # fmt: skip
    return sorted(out, key=lambda c: (c["date"], c["title"]))
