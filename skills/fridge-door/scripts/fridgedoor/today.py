"""The Today summary: the first thing each day, for one member, showing only what the chat may show.

Sections come from providers so each module plugs in: tasks, lists and notices here; events, dinner and birthdays
from the calendar and meal plan; bills from the budget. Each member chooses their sections.
"""

from __future__ import annotations

import datetime as _dt

from . import access, members, todos
from .util import now_stamp, parse_date, plural

MONTH_NAMES = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
               "November", "December")  # fmt: skip
DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

# name -> function(ctx, member, day) returning {"title", "items", "lines"} or None. Order = TODAY_SECTIONS.
PROVIDERS: dict = {}


def greeting_for(hour: int) -> str:
    """Morning from 5am, afternoon from midday, evening from 5pm (ported)."""
    if 5 <= hour < 12:
        return "Good morning"
    if 12 <= hour < 17:
        return "Good afternoon"
    return "Good evening"


def friendly_date(day: _dt.date, settings: dict) -> str:
    if str(settings.get("date_format", "")).startswith("MM"):
        return f"{DAY_NAMES[day.weekday()]}, {MONTH_NAMES[day.month - 1]} {day.day}"
    return f"{DAY_NAMES[day.weekday()]} {day.day} {MONTH_NAMES[day.month - 1]}"


def my_day(tasks: list, member_id: str, day: _dt.date) -> list:
    """Tasks assigned to the member, open, top level, due on or before the day; oldest due first, then id
    (ported selector, so overdue ones lead)."""
    bound = day.isoformat()
    picked = [t for t in tasks if t.get("assignee") == member_id and not t.get("parent") and not todos.is_done(t)
              and t.get("due") and t["due"] <= bound]  # fmt: skip
    return sorted(picked, key=lambda t: (t["due"], t["id"]))


def list_cards(lists: list, counts: dict) -> list:
    """Lists with something left, busiest first, then by name and id (ported)."""
    cards = [(lst, counts.get(lst["id"], 0)) for lst in lists]
    cards = [c for c in cards if c[1] > 0]
    return sorted(cards, key=lambda c: (-c[1], c[0]["name"].lower(), c[0]["id"]))


def _tasks(ctx, member, day):
    viewer = ctx.viewer
    if not viewer.sees("todos") or not access.can(member, "todos", "view"):
        return None
    hh = ctx.household
    data = todos.kid_level(ctx, hh.data("todos"))
    shared = {lst["id"] for lst in data["lists"] if not lst.get("owner") and not lst.get("deleted_at")}
    own = {lst["id"] for lst in data["lists"] if lst.get("owner") == member["id"] and not lst.get("deleted_at")}
    allowed = shared | (own if viewer.sees_private_of(member["id"]) else set())
    tasks = [t for t in data["tasks"] if t["list"] in allowed]
    mine = my_day(tasks, member["id"], day)
    unassigned = [t for t in tasks if not t.get("assignee") and not t.get("parent") and not todos.is_done(t)
                  and t.get("due") and t["due"] <= day.isoformat() and t["list"] in shared]  # fmt: skip
    items = [todos.task_view(hh, t, day) for t in mine]
    lines = []
    for item in items:
        flag = "⚠️ " if item["due"]["overdue"] else "• "
        late = f" ({item['due']['label']})" if item["due"]["overdue"] else ""
        lines.append(f"{flag}{item['title']}{late}")
    if not items:
        lines.append("Nothing due today.")
    if unassigned:
        names = ", ".join(t["title"] for t in sorted(unassigned, key=lambda t: t["due"]))
        lines.append(f"Also due, nobody assigned: {names}")
    return {"title": "✅ Your tasks" if member["id"] == ctx.member["id"] else f"✅ {member['name']}'s tasks",
            "items": items, "unassigned": [t["title"] for t in unassigned], "lines": lines}  # fmt: skip


def _lists(ctx, member, day):
    hh = ctx.household
    data = hh.data("shopping")
    visible = [lst for lst in data["lists"] if not lst.get("deleted_at")
               and ctx.viewer.sees(access.LIST_KIND_MODULE[lst["kind"]])
               and access.can(member, access.LIST_KIND_MODULE[lst["kind"]], "view")]  # fmt: skip
    if not visible:
        return None
    counts = {}
    for item in data["items"]:
        if not item.get("crossed_at"):
            counts[item["list"]] = counts.get(item["list"], 0) + 1
    cards = list_cards(visible, counts)
    if not cards:
        return None
    items = [{"id": lst["id"], "name": lst["name"], "icon": lst.get("icon"), "open": n} for lst, n in cards]
    line = " · ".join(f"{i['name']}: {plural(i['open'], 'item')}" for i in items)
    return {"title": "🛒 Lists", "items": items, "lines": [line]}


def _notices(ctx, member, day):
    from .notices import readable

    if member["id"] != ctx.member["id"]:
        return None
    notes = ctx.household.data("notices")["notices"]
    waiting = [n for n in notes if n["to"] == member["id"] and not n.get("delivered_at")]
    if not waiting:
        return None
    if ctx.viewer.group:  # only the count in a group; they stay new until read in a direct chat
        return {"title": "🔔 New for you", "items": [], "count": len(waiting),
                "lines": [f"{plural(len(waiting), 'new notice')}: ask me in a direct chat."]}  # fmt: skip
    shown = [n for n in waiting if readable(ctx, n)]
    if not shown:
        return None
    return {"title": "🔔 New for you", "items": [{"id": n["id"], "text": n["text"]} for n in shown],
            "lines": [n["text"] for n in shown], "_deliver": [n["id"] for n in shown]}  # fmt: skip


def _events(ctx, member, day):
    from . import events

    if not ctx.viewer.sees("calendar") or not access.in_their_day(member, "calendar"):
        return None
    by_id = {e["id"]: e for e in ctx.household.data("calendar")["events"]}
    kids = {m["id"] for m in ctx.household.members if access.is_minor(m)}

    def theirs(event: dict) -> bool:
        """Their events, everyone's, and (for an adult) the kids' too; someone's private event only for them."""
        people = set(event.get("members") or [])
        if not people:
            return event.get("visibility") != "private" or event.get("owner") == member["id"]
        return member["id"] in people or (not access.is_minor(member) and bool(people & kids))

    occs = [o for o in events.agenda(ctx, day, day) if o["event"] not in by_id or theirs(by_id[o["event"]])]
    if not occs:
        return {"title": "📅 Today", "items": [], "lines": ["Nothing on the calendar."]}
    return {"title": "📅 Today", "items": occs, "lines": [events.occ_line(o, ctx.household.settings) for o in occs]}


def _dinner(ctx, member, day):
    from . import mealplan

    return mealplan.tonight(ctx, member, day)


def _birthdays(ctx, member, day):
    from . import events

    if not ctx.viewer.sees("calendar") or not access.in_their_day(member, "calendar"):
        return None
    occs = events.upcoming_birthdays(ctx, day, 14)
    if not occs:
        return None
    lines = []
    for occ in occs:
        when = events.day_label(_dt.date.fromisoformat(occ["date"]), day, ctx.household.settings)
        turns = f" (turns {occ['turns']})" if occ.get("turns") else ""
        lines.append(f"{when}: {occ['title']}{turns}")
    return {"title": "🎂 Coming up", "items": occs, "lines": lines}


def _bills(ctx, member, day):
    from . import budget

    return budget.today_bills(ctx, member, day)


PROVIDERS.update({"events": _events, "tasks": _tasks, "dinner": _dinner, "lists": _lists, "birthdays": _birthdays,
                  "bills": _bills, "notices": _notices})  # fmt: skip


def build(ctx, member: dict, day: _dt.date) -> dict:
    hh = ctx.household
    wanted = member.get("today_sections") or list(members.TODAY_SECTIONS)
    sections, deliver = {}, []
    for name in members.TODAY_SECTIONS:
        if name not in wanted or name not in PROVIDERS:
            continue
        section = PROVIDERS[name](ctx, member, day)
        if section:
            deliver += section.pop("_deliver", [])
            sections[name] = section
    hour = hh.now().hour
    head = f"{greeting_for(hour)}, {member['name']}" if member["id"] == ctx.member["id"] else f"{member['name']}'s day"
    head += f" — {friendly_date(day, hh.settings)}"
    lines = [head]
    for section in sections.values():
        lines.append(section["title"])
        lines += ["  " + line for line in section["lines"]]
    if len(lines) == 1:
        lines.append("Nothing planned. Enjoy the day.")
    return {"sections": sections, "text": "\n".join(lines), "deliver": deliver, "headline": head}


def cmd_today(ctx, args) -> dict:
    hh = ctx.household
    member = ctx.member
    if args.member:
        from .context import find_member

        member = find_member(hh, args.member)
    day = parse_date(args.date, hh.today(), week_start=todos.week_start(hh)) if args.date else hh.today()
    result = build(ctx, member, day)
    if result["deliver"] and not args.peek:
        with hh.transaction():
            ids = set(result["deliver"])
            stamp = now_stamp()
            for notice in hh.data("notices")["notices"]:
                if notice["id"] in ids and not notice.get("delivered_at"):
                    notice["delivered_at"] = stamp
            hh.touch("notices")
    counts = {name: len(sec.get("items", [])) for name, sec in result["sections"].items()}
    return {
        "member": member["name"],
        "date": day.isoformat(),
        "sections": result["sections"],
        "text": result["text"],
        "summary": result["headline"],
        "counts": counts,
    }


def register(cli) -> None:
    p = cli.top(
        "today",
        "The Today summary: today's events, tasks due, tonight's dinner, lists to shop, birthdays, bills and new "
        "notices, in the member's chosen sections. Run it first thing each day.",
        ["fridge today", "fridge today --for Theo", "fridge today --date tomorrow",
         "fridge today --chat family --from @ana"],  # fmt: skip
        cmd_today,
    )
    p.add_argument("--for", dest="member", help="Someone else's day (e.g. a kid's chores)")
    p.add_argument("--date", help="Another day (default today)")
    p.add_argument("--peek", action="store_true", help="Don't mark the notices shown as delivered")
