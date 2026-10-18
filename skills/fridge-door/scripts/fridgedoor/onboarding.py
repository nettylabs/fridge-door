"""Setup in one step, more households, household settings, export, and the doctor check."""

from __future__ import annotations

import platform
import re

from . import __version__, access, budget, confirm, members, regions, shopping, todos
from .store import DEFAULT_RETENTION_DAYS, Hub, create_household, remove_household_folder
from .util import (ToolError, and_list, clean_text, fold, no_tz_data, now_stamp, parse_hours_range, plural,
                   set_local_tz, tz_database_ok, tz_known)

# Old and new names for a few time zones, for computers with an older time zone database.
_TZ_ALIASES = {"Europe/Kyiv": "Europe/Kiev", "Asia/Kolkata": "Asia/Calcutta", "Asia/Ho_Chi_Minh": "Asia/Saigon"}

DEFAULT_QUIET_HOURS = {"start": "21:00", "end": "07:00"}
CURRENCY_DISPLAY = ("auto", "always", "never")


def _timezone(name: str) -> str:
    if tz_known(name):
        return name
    alias = _TZ_ALIASES.get(name)
    if alias and tz_known(alias):
        return alias
    if not tz_database_ok():
        raise no_tz_data()
    raise ToolError(
        f"{name!r} isn't a time zone this computer knows.",
        hint="Use an IANA name such as Europe/London, America/Chicago or Australia/Perth.",
        code="bad_timezone",
    )


def _currency(code: str) -> str:
    text = str(code or "").strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", text):
        raise ToolError(f"{code!r} isn't a currency code.", hint="Use the 3-letter code, e.g. CAD, GBP, EUR, JPY.",
                        code="bad_currency")  # fmt: skip
    return text


def _choice(value: str, options, label: str) -> str:
    key = str(value or "").strip()
    for option in options:
        if fold(option) == fold(key):
            return option
    raise ToolError(f"{value!r} isn't a {label}.", hint="Use one of: " + ", ".join(options) + ".", code="bad_setting")


def _zone_choices(zones) -> str:
    """The zones to offer in a hint: "Europe/Moscow (MSK+00 - Moscow area); ...", or how to name one."""
    if not zones:
        return "their IANA time zone (Region/City, e.g. Europe/Belgrade)"
    return "the zone for their place: " + "; ".join(f"{tz} ({where})" if where else tz for tz, where in zones)


def build_settings(args) -> tuple:
    """Settings from the country's defaults plus any explicit choices. Returns (settings, notes for the reply)."""
    code = regions.country_code(args.country)
    base = regions.defaults(code)
    notes = []
    settings = {
        "country": code,
        "currency": _currency(args.currency) if args.currency else base["currency"],
        "timezone": _timezone(args.timezone) if args.timezone else None,
        "week_start": _choice(args.week_start, regions.WEEK_STARTS, "week start")
        if args.week_start
        else base["week_start"],
        "date_format": _choice(args.date_format, regions.DATE_FORMATS, "date format")
        if args.date_format
        else base["date_format"],
        "time_format": _choice(args.time_format, regions.TIME_FORMATS, "time format")
        if args.time_format
        else base["time_format"],
        "units": _choice(args.units, regions.UNITS, "unit system") if args.units else base["units"],
        "paper": _choice(args.paper, regions.PAPERS, "paper size") if args.paper else base["paper"],
        "currency_display": "auto",
        "retention_days": DEFAULT_RETENTION_DAYS,
        "quiet_hours": dict(DEFAULT_QUIET_HOURS),
        "sensitive_notes_in_groups": False,
        "reminders_outside_chat": None,
    }
    name = regions.name_of(code)
    # A country without defaults gets the time zone database's zone when it lists exactly one; otherwise ask. Never
    # quietly UTC: a household's reminders and "today" would be hours off.
    zones = [] if base["known"] or settings["timezone"] else [z for z in regions.table_zones(code) if tz_known(z[0])]
    only_zone = zones[0][0] if len(zones) == 1 else None
    ask_zone = settings["timezone"] is None and not base["known"] and not only_zone
    zone_list = {"zones": [{"timezone": tz, "where": where} for tz, where in zones]} if ask_zone and zones else {}
    if not settings["currency"]:
        raise ToolError(
            f"I don't have defaults for {name}, so I need the currency{' and the time zone' if ask_zone else ''}.",
            hint="Ask, then add --currency with the 3-letter code"
            + (f" and --timezone with {_zone_choices(zones)}." if ask_zone else "."),
            code="needs_currency",
            **zone_list,
        )
    if settings["timezone"] is None:
        if base["several_time_zones"]:
            main = regions.ZONES.get(code, [])
            raise ToolError(
                f"{name} has several time zones. Which province, state or city is the household in?",
                hint=f"Ask, then run this again with --timezone and {_zone_choices(main)}. Any IANA name "
                "(Region/City) works too.",
                code="needs_timezone",
                zones=[{"timezone": tz, "where": where} for tz, where in main],
            )
        if ask_zone:
            raise ToolError(
                f"{name} has several time zones. Which region or city is the household in?" if zones else
                f"I don't know the time zone for {name}. Which city is the household in?",
                hint=f"Ask, then run this again with --timezone and {_zone_choices(zones)}.",
                code="needs_timezone",
                **zone_list,
            )
        settings["timezone"] = _timezone(base["timezone"] if base["known"] else only_zone)
    if not base["known"]:
        notes.append("I used international formats for this country; change any setting that's wrong.")
    return settings, notes


def describe_settings(settings: dict) -> str:
    week = settings["week_start"].capitalize()
    units = "metric" if settings["units"] == "metric" else "US"
    return (
        f"{settings['currency']}, {settings['timezone']}, weeks start {week}, dates {settings['date_format']}, "
        f"{settings['time_format']} clock, {units} units, {'A4' if settings['paper'] == 'a4' else 'Letter'} paper"
    )


def _create(hub: Hub, args, own_chat: str | None = None) -> dict:
    """A new household. own_chat (setup's --chat) registers the owner's own one-to-one chat with the agent: from then
    on every message must say which chat it came from, so no other chat can act as the owner (context.resolve)."""
    people = members.parse_member_list(args.members)
    settings, notes = build_settings(args)
    owner_name = people[0][0] if people[0][1] == "owner" else next(n for n, r in people if r == "owner")
    name = clean_text(args.name, "household name", max_len=60, required=False) or f"{owner_name}'s home"
    roster = []
    for index, (person, role) in enumerate(people, start=1):
        roster.append(members.new_member(roster, f"M{index}", person, role))
    for member in roster:
        if member["role"] == "owner":
            member["chat_ok"] = {"owner_said": "set up the household", "at": now_stamp(), "by": member["id"]}
    owner = next(m for m in roster if m["role"] == "owner")
    chats = {}
    if own_chat:
        own_chat = clean_text(own_chat, "chat id", max_len=200)
        chats[own_chat] = {"type": "direct", "minors_present": False, "participants": {}, "member": owner["id"],
                           "registered_at": now_stamp()}  # fmt: skip
    if args.dry_run:
        return {
            "dry_run": True,
            "household": {"name": name, "settings": settings, "members": [members.public(m) for m in roster]},
            "notes": notes,
            "summary": f"Would set up {name} with {plural(len(roster), 'member')}: {describe_settings(settings)}.",
        }
    with hub.transaction() as data:
        if any(fold(e["name"]) == fold(name) for e in data["households"]):
            raise ToolError(
                f"There's already a household called {name}.", hint="Pick another name.", code="exists"
            )
        household = create_household(hub, name, settings, roster, chats=chats)
        for chat_id in chats:
            data.setdefault("chats", {})[chat_id] = household.id
        set_local_tz(settings["timezone"])
        with household.transaction():
            made = todos.ensure_default_lists(household) + shopping.ensure_default_lists(household)
            budget.add_default_categories(household)
            household.log("household.create", roster[0]["id"], members=len(roster))
        data["active"] = household.id
        data.setdefault("speakers", {})[household.id] = owner["id"]
    kids = [m["name"] for m in roster if m["role"] in access.MINOR_ROLES]
    summary = f"{name} is set up with {plural(len(roster), 'member')}: {describe_settings(settings)}."
    if kids:
        summary += (
            f" {and_list(kids)} {'takes' if len(kids) == 1 else 'take'} part through you: their chores and stars go "
            "on the fridge sheet, and they don't chat with the agent."
        )
    return {
        "household": {"id": household.id, "name": name},
        "members": [members.public(m, settings) for m in roster],
        "settings": settings,
        "lists": [{"id": lst["id"], "name": lst["name"] + (f" ({household.member_name(lst['owner'])})"
                                                            if lst.get("owner") else ""), "kind": lst["kind"]}
                  for lst in made],  # fmt: skip
        "notes": notes,
        "summary": summary,
        "chat": own_chat,
        "next": ([] if own_chat else [
            "If your platform gives each chat an id, register this one-to-one chat now, so no other chat can act as "
            "the owner: fridge who chat <chat-id> --type direct. Then pass --chat <chat-id> with every message.",
        ]) + [
            "Offer a Today summary every morning (time and days), if the platform has scheduled routines.",
            "In a group chat, register it once: fridge who chat <chat-id> --type group --minors yes|no",
        ] + ([
            "If another adult chats with you in their own one-to-one chat, register it once: fridge who chat "
            "<chat-id> --type direct --member <name> (the owner confirms they're 18 or older).",
        ] if sum(m["role"] in access.ADULT_ROLES for m in roster) > 1 else []),
    }


def cmd_setup(home, args) -> dict:
    hub = Hub(home)
    if hub.exists():
        raise ToolError(
            f"{hub.home} already has a household.",
            hint='Add another with: fridge household add --name "..." --members "..." --country XX',
            code="already_set_up",
        )
    return _create(hub, args, own_chat=getattr(args, "chat", None))


def cmd_household_add(ctx, args) -> dict:
    """Another household for the same person (a parent's, say). Only the owner adds one, as its owner too, and it
    becomes the active one. From their own one-to-one chat, that chat is registered in the new household as theirs
    and its messages go there (household switch moves them back), so the which-chat rule covers it from the start."""
    ctx.viewer.require_owner("add a household")
    _direct_only(ctx, "Adding a household")
    people = members.parse_member_list(args.members)
    owner_name = people[0][0] if people[0][1] == "owner" else next(n for n, r in people if r == "owner")
    if fold(owner_name) != fold(ctx.member["name"]):
        raise ToolError(
            f"The new household's owner would be {owner_name}, but {ctx.member['name']} is adding it.",
            hint=f'List yourself as its owner: --members "{ctx.member["name"]} (owner), ...". Your direct chat then '
            "stays yours in both households.",
            code="not_the_owner",
        )
    result = _create(ctx.hub, args, own_chat=ctx.chat_id)
    if not args.dry_run:
        result["summary"] += " It's now the active household" + (
            f" for this chat; household switch \"{ctx.household.name}\" goes back." if ctx.chat_id else ".")
    return result


def _direct_only(ctx, what: str) -> None:
    if ctx.viewer.group:
        raise ToolError(f"{what} only works in a direct chat.", code="direct_chat_only")


def _yours(ctx, hh):
    """Who the person asking is in household hh, or None if they aren't in it: from a one-to-one chat, the member
    that chat is registered to there; on a platform without chat ids, the adult with their name."""
    if ctx.chat_id:
        chat = hh.meta().get("chats", {}).get(ctx.chat_id) or {}
        member = hh.member(chat.get("member") or "") if chat.get("type") == "direct" else None
    else:
        member = next((m for m in hh.members if fold(m["name"]) == fold(ctx.member["name"])), None)
    return member if member and access.is_adult(member) else None


def cmd_household_list(ctx, args) -> dict:
    """The households the person asking belongs to (never anyone else's), and who they are in each."""
    _direct_only(ctx, "Listing households")
    hub = ctx.hub
    active = (hub.chat_household(ctx.chat_id) if ctx.chat_id else None) or hub.household().id
    items = []
    for entry in hub.households():
        hh = hub.household(entry["id"])
        you = _yours(ctx, hh)
        if you:
            items.append({"id": hh.id, "name": hh.name, "members": len(hh.members), "active": hh.id == active,
                          "you": you["name"]})  # fmt: skip
    current = next((i["name"] for i in items if i["active"]), ctx.household.name)
    return {"households": items, "summary": f"{plural(len(items), 'household')} you're in; active: {current}."}


def cmd_household_switch(ctx, args) -> dict:
    """Make another household the one messages act in. From a one-to-one chat, this chat moves, and only to a
    household where it's registered as the same person's chat (household add does that for the owner). On a platform
    without chat ids, the owner switches the household everything acts in, to one where they're the speaker too."""
    _direct_only(ctx, "Switching households")
    target = ctx.hub.household(args.name)
    if ctx.chat_id:
        if _yours(ctx, target) is None:
            raise ToolError(
                f"This chat isn't registered in {target.name}, so it can't act there.",
                hint=f"Households this chat is in: fridge household list. The owner of {target.name} can register it "
                "there: fridge who chat <chat-id> --type direct --member <name>",
                code="chat_not_linked",
            )
        with ctx.hub.transaction() as data:
            data.setdefault("chats", {})[ctx.chat_id] = target.id
        return {"household": {"id": target.id, "name": target.name},
                "summary": f"Switched this chat to {target.name}."}  # fmt: skip
    ctx.viewer.require_owner("switch the active household")
    there = target.member(ctx.hub.speaker(target.id) or "")
    if there is None or fold(there["name"]) != fold(ctx.member["name"]):
        raise ToolError(
            f"In {target.name}, direct chats run as {there['name'] if there else 'nobody yet'}, not "
            f"{ctx.member['name']}.",
            hint="Run that household's commands with --household instead, or ask its owner to make you its "
            "direct-chat speaker there.",
            code="not_the_owner",
        )
    with ctx.hub.transaction() as data:
        data["active"] = target.id
    return {"household": {"id": target.id, "name": target.name}, "summary": f"Switched to {target.name}."}


def cmd_household_show(ctx, args) -> dict:
    hh = ctx.household
    roster = [members.public(m, hh.settings, ctx.viewer) for m in hh.members]
    return {
        "household": {"id": hh.id, "name": hh.name, "created_at": hh.meta().get("created_at")},
        "settings": hh.settings,
        "members": roster,
        "summary": f"{hh.name}: {plural(len(roster), 'member')}; {describe_settings(hh.settings)}.",
    }


def cmd_household_rename(ctx, args) -> dict:
    ctx.viewer.require_owner("rename the household")
    name = clean_text(args.to, "household name", max_len=60)
    hh = ctx.household
    with ctx.hub.transaction() as data:
        if any(fold(e["name"]) == fold(name) and e["id"] != hh.id for e in data["households"]):
            raise ToolError(f"There's already a household called {name}.", code="exists")
        with hh.transaction():
            hh.meta()["name"] = name
            hh.touch("household")
            hh.log("household.rename", ctx.member["id"])
        for entry in data["households"]:
            if entry["id"] == hh.id:
                entry["name"] = name
    return {"summary": f"Renamed the household to {name}."}


SETTING_KEYS = (
    "country",
    "currency",
    "timezone",
    "week_start",
    "date_format",
    "time_format",
    "units",
    "paper",
    "currency_display",
    "retention_days",
    "quiet_hours",
    "sensitive_notes_in_groups",
    "reminders_outside_chat",
)


# Settings that open something up: turning one on needs the owner's clear yes to its question (confirm.owner_yes).
NEEDS_OWNER = {
    "sensitive_notes_in_groups": "Show notes marked sensitive in group chats too?",
    "reminders_outside_chat": "Allow reminders to be sent outside this chat (by email or another app)?",
}
_ON, _OFF = ("yes", "on", "true", "1"), ("no", "off", "false", "0")


def _split_setting(item: str) -> tuple:
    if "=" not in item:
        raise ToolError(f"{item!r} should look like key=value.", hint="e.g. week_start=monday", code="bad_setting")
    key, value = item.split("=", 1)
    return key.strip().lower().replace("-", "_"), value


def _set(settings: dict, key: str, value: str, owner_said: str | None, actor_id: str) -> None:
    """One setting. For a NEEDS_OWNER one being turned on, owner_said is the owner's confirmed yes."""
    if key == "country":
        settings["country"] = regions.country_code(value)
    elif key == "currency":
        settings["currency"] = _currency(value)
    elif key == "timezone":
        settings["timezone"] = _timezone(value.strip())
    elif key == "week_start":
        settings["week_start"] = _choice(value, regions.WEEK_STARTS, "week start")
    elif key == "date_format":
        settings["date_format"] = _choice(value, regions.DATE_FORMATS, "date format")
    elif key == "time_format":
        settings["time_format"] = _choice(value, regions.TIME_FORMATS, "time format")
    elif key == "units":
        settings["units"] = _choice(value, regions.UNITS, "unit system")
    elif key == "paper":
        settings["paper"] = _choice(value, regions.PAPERS, "paper size")
    elif key == "currency_display":
        settings["currency_display"] = _choice(value, CURRENCY_DISPLAY, "currency display")
    elif key == "retention_days":
        if not re.fullmatch(r"\d{1,4}", value.strip()) or not 7 <= int(value) <= 3650:
            raise ToolError("retention_days must be a whole number from 7 to 3650.", code="bad_setting")
        settings["retention_days"] = int(value)
    elif key == "quiet_hours":
        if fold(value) in ("none", "off", "no"):
            settings["quiet_hours"] = None
        else:
            start, end = parse_hours_range(value)
            settings["quiet_hours"] = {"start": start, "end": end}
    elif key in NEEDS_OWNER:
        if fold(value) in _OFF:
            settings[key] = False if key == "sensitive_notes_in_groups" else None
        elif fold(value) in _ON and owner_said:
            settings[key] = True if key == "sensitive_notes_in_groups" else {
                "owner_said": owner_said, "at": now_stamp(), "by": actor_id,
            }  # fmt: skip
        else:
            raise ToolError(f"{key} needs yes or no.", code="bad_setting")
    else:
        raise ToolError(f"{key!r} isn't a setting.", hint="Settings: " + ", ".join(SETTING_KEYS) + ".",
                        code="bad_setting")  # fmt: skip


def cmd_household_settings(ctx, args) -> dict:
    hh = ctx.household
    if not args.set:
        return {"settings": hh.settings, "summary": f"{hh.name}: {describe_settings(hh.settings)}."}
    ctx.viewer.require_owner("change household settings")
    changes = [_split_setting(item) for item in args.set]
    opening = [key for key, value in changes if key in NEEDS_OWNER and fold(value) in _ON]
    if len(opening) > 1:
        raise ToolError("Turn these on one at a time: each needs the owner's own yes to its own question.",
                        hint="Run household settings once for each.", code="usage")  # fmt: skip
    words = None
    if opening:
        key = opening[0]
        words = confirm.owner_yes(hh, ctx.member["id"], f"settings|{key}=yes", NEEDS_OWNER[key], args.owner_confirmed,
                                  args.confirm, why="This needs the owner's own OK.",
                                  echo=("allow", "show", "turn", "switch", "it", "them", "on"))  # fmt: skip
    with hh.transaction(dry_run=args.dry_run):
        settings = hh.meta()["settings"]
        for key, value in changes:
            _set(settings, key, value, words, ctx.member["id"])
        hh.touch("household")
        hh.log("household.settings", ctx.member["id"], keys=[i.split("=", 1)[0] for i in args.set])
        result = dict(settings)
    verb = "Would change" if args.dry_run else "Changed"
    return {"settings": result, "dry_run": args.dry_run, "summary": f"{verb} {plural(len(args.set), 'setting')}."}


def cmd_household_delete(ctx, args) -> dict:
    ctx.viewer.require_owner("delete the household")
    hh = ctx.household
    if ctx.viewer.group:
        raise ToolError("Deleting a household only works in a direct chat with the owner.", code="direct_chat_only")
    if args.dry_run:
        counts = [plural(len(hh.members), "member"), plural(len(hh.data("todos")["tasks"]), "task"),
                  plural(len(hh.data("calendar")["events"]), "event"),
                  plural(len(hh.data("recipes")["recipes"]), "recipe"), plural(len(hh.data("notes")["notes"]), "note"),
                  plural(len(hh.data("budget")["expenses"]), "expense")]  # fmt: skip
        return {"dry_run": True, "summary": f"Would delete {hh.name} and everything in it: {', '.join(counts)}, "
                "and every list, bill and printout. It can't be undone; an export first keeps a copy."}
    confirm.owner_yes(
        hh, ctx.member["id"], f"household.delete|{hh.id}",
        f"Delete {hh.name} and everything in it? This can't be undone.", args.owner_confirmed, args.confirm,
        why=f"Deleting {hh.name} erases all its lists, tasks, events, recipes, notes and budget. It can't be undone. "
        "Suggest `fridge export` first if they want a copy.",
        echo=("delete", "it", "all", "everything", "the household", hh.name),
    )
    with ctx.hub.transaction() as data:
        remove_household_folder(ctx.hub, hh)
        data["households"] = [e for e in data["households"] if e["id"] != hh.id]
        data.get("speakers", {}).pop(hh.id, None)
        for chat_id in list(data.get("chats", {})):  # the owner's chat may also be in another household
            ctx.hub.rehome_chat(data, chat_id, hh.id)
        if data.get("active") == hh.id:
            data["active"] = data["households"][0]["id"] if data["households"] else None
    return {"summary": f"Deleted {hh.name} and everything in it."}


def _own_copy(me: str) -> dict:
    """Filters for the owner's export: other members' private events, notes, personal to-do lists and notices
    stay out, the same as everywhere else."""

    def calendar(data):
        def mine(event):
            vis = event.get("visibility", "household")
            if vis == "private":
                return event.get("owner") == me
            return vis != "members" or event.get("owner") == me or me in (event.get("members") or [])

        return dict(data, events=[e for e in data.get("events", []) if mine(e)],
                    bin=[b for b in data.get("bin", []) if all(mine(e) for e in b["records"])])  # fmt: skip

    def notes(data):
        def mine(note):
            return note.get("visibility") != "private" or note.get("author") == me

        return dict(data, notes=[n for n in data.get("notes", []) if mine(n)],
                    bin=[b for b in data.get("bin", []) if all(mine(n) for n in b["records"])])  # fmt: skip

    def todos(data):
        hidden = {lst["id"] for lst in data.get("lists", []) if lst.get("owner") and lst.get("owner") != me}
        return dict(data, lists=[lst for lst in data.get("lists", []) if lst["id"] not in hidden],
                    tasks=[t for t in data.get("tasks", []) if t.get("list") not in hidden],
                    bin=[b for b in data.get("bin", []) if all(t.get("list") not in hidden for t in b["records"])])

    def notices(data):
        return dict(data, notices=[n for n in data.get("notices", []) if n.get("to") == me], sent={})

    return {"calendar.json": calendar, "notes.json": notes, "todos.json": todos, "notices.json": notices}


def cmd_export(ctx, args) -> dict:
    ctx.viewer.require_owner("export the household")
    if ctx.viewer.group:
        raise ToolError("Exports only work in a direct chat with the owner.", code="direct_chat_only")
    path = ctx.household.export_zip(_own_copy(ctx.member["id"]))
    return {"file": str(path),
            "summary": f"Exported {ctx.household.name} to {path.name} (other members' private events, notes and "
                       "to-do lists are left out)."}  # fmt: skip


def cmd_doctor(home, args) -> dict:
    hub = Hub(home)
    missing, notes = [], []
    if not hub.exists():
        missing.append("a household (fridge setup)")
        return {
            "home": str(hub.home),
            "initialized": False,
            "setup": {"missing": missing},
            "version": __version__,
            "python": platform.python_version(),
            "timezone_database": tz_known("Europe/London"),
        }
    active = hub.household()
    for entry in hub.households():
        hh = hub.household(entry["id"])
        tz = hh.settings.get("timezone")
        if tz and tz != "UTC" and not tz_database_ok():
            missing.append("a time zone list on this computer: run `pip install tzdata` once (Python on Windows "
                           "doesn't come with one)")  # fmt: skip
        elif not tz or (tz != "UTC" and not tz_known(tz)):
            missing.append(f"a time zone this computer knows for {hh.name}")
        elif tz.upper() in ("UTC", "ETC/UTC") and _has_local_zone(hh.settings.get("country")):
            missing.append(f"the local time zone for {hh.name}: it runs on plain UTC, so times are off (ask which "
                           "city, then: fridge household settings --set timezone=Region/City)")  # fmt: skip
        if hub.speaker(hh.id) is None:
            missing.append(f"who's talking in direct chats for {hh.name} (fridge --as <owner> who speaker <name>)")
    return {
        "home": str(hub.home),
        "initialized": True,
        "households": [{"id": e["id"], "name": e["name"]} for e in hub.households()],
        "active": {"id": active.id, "name": active.name},
        "speaker": active.member_name(hub.speaker(active.id)),
        "setup": {"missing": missing},
        "notes": notes,
        "version": __version__,
        "python": platform.python_version(),
        "timezone_database": tz_known("Europe/London"),
        "summary": f"Ready: {active.name} is active." if not missing else "Setup is incomplete: " + "; ".join(missing),
    }


def _has_local_zone(country) -> bool:
    """Whether a country has a time zone of its own (every country Fridge Door knows, and any the database lists)."""
    return bool(country) and (regions.defaults(country)["known"] or bool(regions.table_zones(country)))


def _add_household_args(p) -> None:
    p.add_argument("--name", help='The household name, e.g. "The Garcias" (default: "<owner>\'s home")')
    p.add_argument("--members", required=True, help='Who lives there: "Ana, Luis, Sofia (kid), Mateo (15)"')
    p.add_argument("--country", required=True, help="Country code or name, e.g. CA or Canada")
    p.add_argument("--currency", help="3-letter currency code (default: the country's)")
    p.add_argument("--timezone", help="IANA time zone, e.g. America/Vancouver (default: the country's main one)")
    p.add_argument("--week-start", help="monday ... sunday (default: the country's)")
    p.add_argument("--date-format", help="e.g. DD/MM/YYYY, MM/DD/YYYY, YYYY-MM-DD")
    p.add_argument("--time-format", help="24h or 12h")
    p.add_argument("--units", help="metric or us")
    p.add_argument("--paper", help="a4 or letter")
    p.add_argument("--dry-run", action="store_true", help="Show what would be set up without saving")


def register(cli) -> None:
    p = cli.top(
        "setup",
        "Set up the first household in one step: its name, who's in it and the country (everything else defaults).",
        [
            'fridge setup --name "The Garcias" --members "Ana, Luis, Sofia (kid), Mateo (teen)" --country MX',
            'fridge setup --members "Jo" --country GB',
            'fridge setup --name "Flat 4" --members "Kai, Jess, Sam" --country AU --timezone Australia/Perth',
        ],
        cmd_setup,
        needs="none",
    )
    _add_household_args(p)
    cli.top("doctor", "Show the setup status and what's missing.", ["fridge doctor"], cmd_doctor, needs="none")
    cli.top("export", "Zip this household's data into the exports folder (owner, direct chat).", ["fridge export"],
            cmd_export)  # fmt: skip

    hh = cli.group("household", "Households: add, list, switch, show, rename, settings, delete.")
    p = hh.add(
        "add",
        "Add another household (e.g. an extended family's) and make it the active one.",
        ['fridge household add --name "Grandma\'s" --members "Ana (owner), Grandma Rosa, Uncle Leo" --country PT'],
        cmd_household_add,
    )
    _add_household_args(p)
    hh.add("list", "List the households in this data folder (direct chat).", ["fridge household list"],
           cmd_household_list)  # fmt: skip
    p = hh.add("switch", "Make another household the active one (direct chat).",
               ['fridge household switch "Grandma\'s"'], cmd_household_switch)  # fmt: skip
    p.add_argument("name", help="Household name or id")
    hh.add("show", "Show the household's settings and members.", ["fridge household show"], cmd_household_show)
    p = hh.add("rename", "Rename the household (owner).", ['fridge household rename --to "The Garcia-Lopez home"'],
               cmd_household_rename)  # fmt: skip
    p.add_argument("--to", required=True, help="The new name")
    p = hh.add(
        "settings",
        "Show the settings, or change them with --set key=value (owner).",
        [
            "fridge household settings",
            "fridge household settings --set week_start=monday --set units=us",
            'fridge household settings --set quiet_hours="22:00-07:00"',
            'fridge household settings --set reminders_outside_chat=yes --owner-confirmed "yes, allow it" '
            "--confirm 1c5e2a0-8d41f2-3f9b27d41c",
        ],
        cmd_household_settings,
    )
    p.add_argument("--set", action="append", help="key=value; repeat for more. Keys: " + ", ".join(SETTING_KEYS))
    p.add_argument("--owner-confirmed", help="The owner's own words, for settings that need their OK")
    p.add_argument("--confirm", help="The code that came with the owner's question (confirm)")
    p.add_argument("--dry-run", action="store_true")
    p = hh.add(
        "delete",
        "Delete this household and everything in it (owner, direct chat, needs the owner's words).",
        ["fridge household delete",
         'fridge household delete --owner-confirmed "yes, delete it" --confirm 1c5e2a0-8d41f2-3f9b27d41c'],
        cmd_household_delete,
    )
    p.add_argument("--owner-confirmed", help="The owner's own words confirming the deletion")
    p.add_argument("--confirm", help="The code that came with the owner's question (confirm)")
    p.add_argument("--dry-run", action="store_true", help="Say what would be deleted (no owner's yes needed)")
