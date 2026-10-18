"""The household calendar: events, repeats, birthdays and important dates, views, and busy evenings.

- An event is all day or has a time (local to the household's time zone), optionally a location, a type with an
  icon, reminders, and who it's for (their colours mark it).
- Visibility: the whole household, selected members, or private (only its owner, and never in a group chat).
- Repeats use the shared RRULE engine; one date can be changed or skipped without touching the rest.
- Birthdays repeat every year by themselves; for kids and teens only the day and month are kept.
- Planned meals and bills can be shown as optional layers.
"""

from __future__ import annotations

import datetime as _dt
import re

from . import access, recur
from .util import MONTH_WORDS, ToolError, clean_text, day_text, fold, match_one, now_stamp, parse_time, plural

TYPES = {
    "appointment": "📅", "school": "🏫", "sports": "⚽", "birthday": "🎂", "anniversary": "💍", "bill": "💳",
    "work": "💼", "social": "🎉", "travel": "✈️", "health": "🩺", "meal": "🍽️", "chore": "🧹", "holiday": "🏖️",
    "reminder": "🔔", "other": "📌",
}  # fmt: skip
_TYPE_WORDS = (
    ("birthday", r"\bbirthday\b(?!\s+(?:cake|card|present|gift|order|form|shopping))|\bb-?day\b"),
    ("anniversary", r"anniversary"),
    ("health", r"dentist|doctor|\bgp\b|clinic|hospital|physio|check-?up|vaccin|therap|optician|orthodont|vet\b"),
    ("school", r"school|class\b|teacher|\bpta\b|exam|field trip|parent.?teacher|term starts|recital|tutor"),
    ("sports", r"soccer|football|hockey|swim|practi[cs]e|\bgame\b|match|training|gym|rugby|netball|basketball|"
               r"baseball|tennis|karate|cricket|dance class|lacrosse|volleyball|yoga|pilates|five-a-side|"
               r"\brun\b|running club|\bcycling\b|climbing|martial arts|gymnastics"),
    ("work", r"\bwork\b|shift|meeting|office|conference"),
    ("travel", r"flight|airport|\btrip\b|train to|vacation|holiday to|ferry"),
    ("social", r"party|dinner with|bbq|barbecue|wedding|drinks|visit|playdate|sleepover|brunch with"),
    ("bill", r"\bbill\b|payment|rent due|mortgage|due date"),
    ("chore", r"\bbins\b|recycling|cleaning|clean the"),
    ("appointment", r"appointment|haircut|barber|mechanic|service|interview|vet appt"),
)  # fmt: skip
VISIBILITY = ("household", "members", "private")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
DINNER_WINDOW = ("17:00", "19:30")  # evening events in this window make a night "busy" for cooking
MAX_SPAN_DAYS = 366  # an event lasting longer than a year is a mistake (and would be slow to show)

# name -> function(ctx, first, last) returning extra occurrences (meals, bills)
LAYERS: dict = {}


_SPORT_ICONS = (
    (r"hockey", "🏒"), (r"swim", "🏊"), (r"basketball", "🏀"), (r"tennis", "🎾"), (r"cricket", "🏏"),
    (r"rugby", "🏉"), (r"baseball|softball", "⚾"), (r"volleyball", "🏐"), (r"\bcycling\b", "🚴"),
    (r"\brun\b|running", "🏃"), (r"yoga|pilates", "🧘"), (r"\bgym\b", "🏋️"), (r"dance|ballet", "💃"),
    (r"karate|martial arts|judo|taekwondo", "🥋"), (r"climbing", "🧗"), (r"gymnastics", "🤸"),
)  # fmt: skip


def guess_type(title: str) -> str:
    text = fold(title)
    for kind, pattern in _TYPE_WORDS:
        if re.search(pattern, text):
            return kind
    return "other"


def guess_icon(title: str, kind: str) -> str:
    """The type's icon, or a closer one: 🏒 for hockey, 🏊 for swimming, ♻️ for recycling."""
    text = fold(title)
    if kind == "sports":
        for pattern, icon in _SPORT_ICONS:
            if re.search(pattern, text):
                return icon
    if kind == "chore" and "recycl" in text:
        return "♻️"
    return TYPES[kind]


def parse_reminders(value) -> list:
    """ "30m, 1h, 1d" -> [30, 60, 1440] minutes before; "at start" -> 0."""
    if not value:
        return []
    out = []
    for part in re.split(r"[,;]|\band\b", str(value)):
        text = fold(part).replace("before", "").strip()
        if not text:
            continue
        if text in ("at start", "at time", "on time", "0", "start"):
            out.append(0)
            continue
        match = re.fullmatch(r"(\d+)\s*(m|min|mins|minutes?|h|hr|hrs|hours?|d|days?|w|weeks?)", text)
        if not match:
            raise ToolError(f"{part.strip()!r} isn't a reminder time.", hint='e.g. "30m, 1h, 1d" before the start.',
                            code="bad_reminder")  # fmt: skip
        number, unit = int(match.group(1)), match.group(2)[0]
        out.append(number * {"m": 1, "h": 60, "d": 1440, "w": 10080}[unit])
    return sorted(set(out))


def _month_day(value: str, base: _dt.date) -> tuple:
    """Birthdays: "1948-03-14", "03-14", "14 March", "March 14", "14/03" -> (year or None, month, day)."""
    text = fold(value)
    match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if match:
        return int(match.group(1)), int(match.group(2)), int(match.group(3))
    match = re.fullmatch(r"(\d{1,2})-(\d{1,2})", text)
    if match:
        return None, int(match.group(1)), int(match.group(2))
    months = [m.lower() for m in MONTHS]
    match = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)(?:\s+(\d{4}))?", text) or None
    if match and match.group(2)[:3] in months:
        year = int(match.group(3)) if match.group(3) else None
        return year, months.index(match.group(2)[:3]) + 1, int(match.group(1))
    match = re.fullmatch(r"([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?", text)
    if match and match.group(1)[:3] in months:
        year = int(match.group(3)) if match.group(3) else None
        return year, months.index(match.group(1)[:3]) + 1, int(match.group(2))
    raise ToolError(f"{value!r} isn't a birthday I can read.", hint='Use "14 March", "March 14", "03-14" or '
                    '"1948-03-14".', code="bad_date")  # fmt: skip


# --------------------------------------------------------------------------- visibility and expansion


def visible(viewer, event: dict) -> bool:
    if not viewer.sees("calendar"):
        return False
    vis = event.get("visibility", "household")
    if vis == "private":
        return viewer.sees_private_of(event.get("owner"))
    if vis == "members":
        return viewer.sees_selected(set(event.get("members") or []) | {event.get("owner")})
    return True


def _start_date(event: dict) -> _dt.date:
    return _dt.date.fromisoformat(event["date"])


def _span_days(event: dict) -> int:
    if event.get("end_date"):
        return min(MAX_SPAN_DAYS, max(0, (_dt.date.fromisoformat(event["end_date"]) - _start_date(event)).days))
    return 0


def occurrences(hh, event: dict, first: _dt.date, last: _dt.date) -> list:
    """Every occurrence of an event that overlaps first..last, with single-date changes applied."""
    start = _start_date(event)
    span = _span_days(event)
    skip = {_dt.date.fromisoformat(d) for d in event.get("exdates", [])}
    if event.get("rrule"):
        try:
            rule = recur.parse(event["rrule"])
        except ToolError:
            return []
        dates = recur.between(rule, start, first - _dt.timedelta(days=span), last, include_start=True, skip=skip)
    else:
        dates = [start] if start <= last and start + _dt.timedelta(days=span) >= first and start not in skip else []
    out = []
    names = {m["id"]: m for m in hh.members}
    for day in dates:
        change = (event.get("overrides") or {}).get(day.isoformat(), {})
        if change.get("cancelled"):
            continue
        when = _dt.date.fromisoformat(change["date"]) if change.get("date") else day
        if when > last or when + _dt.timedelta(days=span) < first:
            continue
        people = [names[m] for m in event.get("members") or [] if m in names]
        occ = {
            "event": event["id"],
            "date": when.isoformat(),
            "end_date": (when + _dt.timedelta(days=span)).isoformat() if span else None,
            "time": change.get("time", event.get("time")),
            "end_time": change.get("end_time", event.get("end_time")),
            "all_day": not change.get("time", event.get("time")),
            "title": change.get("title", event["title"]),
            "type": event.get("type", "other"),
            "kind": event.get("kind", "event"),
            "icon": event.get("icon") or TYPES.get(event.get("type", "other"), "📌"),
            "location": change.get("location", event.get("location")),
            "members": [p["name"] for p in people],
            "color": people[0]["color"] if people else None,
            "repeats": bool(event.get("rrule")),
            "original_date": day.isoformat(),
        }
        if event.get("kind") == "birthday" and (event.get("birthday") or {}).get("year"):
            occ["turns"] = when.year - event["birthday"]["year"]
        out.append(occ)
    return out


def _involves(occ: dict, event: dict, member_id: str | None) -> bool:
    """For a member filter: events for them, or for everyone (a private event only counts for its owner)."""
    if member_id is None:
        return True
    people = event.get("members") or []
    if people:
        return member_id in people
    return event.get("visibility") != "private" or event.get("owner") == member_id


def agenda(ctx, first: _dt.date, last: _dt.date, member_id: str | None = None, layers=()) -> list:
    """Visible occurrences between two dates (optionally only one member's), plus layers, in time order."""
    hh = ctx.household
    events = hh.data("calendar")["events"]
    found = []
    for event in events:
        if not visible(ctx.viewer, event) or not _involves(None, event, member_id):
            continue
        found += occurrences(hh, event, first, last)
    for name in layers:
        if name not in LAYERS:
            raise ToolError(f"There's no {name!r} layer.", hint="Layers: " + ", ".join(sorted(LAYERS)) + ".",
                            code="bad_layer")  # fmt: skip
        found += LAYERS[name](ctx, first, last)
    return sorted(found, key=lambda o: (o["date"], o.get("time") or "", o["title"].lower()))


def busy_evenings(ctx, first: _dt.date, last: _dt.date, window=DINNER_WINDOW) -> dict:
    """Nights with a timed event overlapping the dinner window: {date: [titles]} (only events the chat may see)."""
    start_w, end_w = parse_time(window[0]), parse_time(window[1])
    busy: dict = {}
    for occ in agenda(ctx, first, last):
        if occ["all_day"] or not occ.get("time"):
            continue
        begins = parse_time(occ["time"])
        ends = parse_time(occ["end_time"]) if occ.get("end_time") else (
            _dt.datetime.combine(_dt.date.today(), begins) + _dt.timedelta(hours=1)).time()  # fmt: skip
        if ends <= begins:  # runs past midnight
            ends = _dt.time.max
        if begins < end_w and ends > start_w:
            busy.setdefault(occ["date"], []).append(occ["title"])
    return busy


def fmt_time(value: str | None, settings: dict) -> str:
    if not value:
        return ""
    moment = parse_time(value)
    if settings.get("time_format") == "12h":
        hour = moment.hour % 12 or 12
        suffix = "am" if moment.hour < 12 else "pm"
        return f"{hour}:{moment.minute:02d}{suffix}" if moment.minute else f"{hour}{suffix}"
    return moment.strftime("%H:%M")


def day_label(day: _dt.date, today: _dt.date, settings: dict | None = None) -> str:
    base = day_text(day, settings, today)
    return {0: f"Today, {base}", 1: f"Tomorrow, {base}"}.get((day - today).days, base)


def occ_line(occ: dict, settings: dict) -> str:
    when = "All day" if occ["all_day"] else fmt_time(occ["time"], settings)
    if occ.get("end_time") and not occ["all_day"]:
        when += f"–{fmt_time(occ['end_time'], settings)}"
    who = f" ({', '.join(occ['members'])})" if occ.get("members") else ""
    where = f" @ {occ['location']}" if occ.get("location") else ""
    turns = f", turns {occ['turns']}" if occ.get("turns") else ""
    return f"{when}  {occ['icon']} {occ['title']}{turns}{who}{where}"


def agenda_text(occs: list, settings: dict, today: _dt.date, empty: str = "Nothing on the calendar.",
                first: _dt.date | None = None, last: _dt.date | None = None, headings: bool = True) -> str:  # fmt: skip
    """Occurrences by day. An event lasting several days is listed on each of its days (within first..last)."""
    by_day: dict = {}
    for occ in occs:
        start = _dt.date.fromisoformat(occ["date"])
        end = _dt.date.fromisoformat(occ["end_date"]) if occ.get("end_date") else start
        span = (end - start).days + 1
        shown_from, shown_to = max(start, first or start), min(end, last or start)  # only the days asked for
        for offset in range((shown_from - start).days, (shown_to - start).days + 1):
            day = start + _dt.timedelta(days=offset)
            line = occ_line(occ, settings) + (f" (day {offset + 1} of {span})" if span > 1 else "")
            by_day.setdefault(day, []).append((occ.get("time") or "", line))
    if not by_day:
        return empty
    lines = []
    for day in sorted(by_day):
        if headings:
            lines.append(day_label(day, today, settings))
        lines += ["  " + line for _, line in sorted(by_day[day], key=lambda item: item[0])]
    return "\n".join(lines)


# --------------------------------------------------------------------------- commands


def _week_start(hh) -> int:
    return hh.week_start()


def _date(hh, value, default=None) -> _dt.date:
    if value is None:
        return default or hh.today()
    return hh.date(value)


def _month_named(hh, value) -> _dt.date:
    """The first day of a month given as YYYY-MM, "november" or "nov 2026" (a month named alone is the coming one,
    this month included)."""
    text = fold(value)
    match = re.fullmatch(r"(\d{4})-(\d{1,2})", text)
    if match and 1 <= int(match.group(2)) <= 12:
        return _dt.date(int(match.group(1)), int(match.group(2)), 1)
    words = text.replace(",", " ").split()
    if words and words[0] in MONTH_WORDS and (len(words) == 1 or re.fullmatch(r"\d{4}", words[-1])):
        month = MONTH_WORDS[words[0]]
        today = hh.today()
        year = int(words[-1]) if len(words) > 1 else today.year + (month < today.month)
        return _dt.date(year, month, 1)
    raise ToolError(f"{value!r} isn't a month.", hint="Use YYYY-MM or the month's name, e.g. 2026-11 or November.",
                    code="bad_date")  # fmt: skip


def _clock(hh, value) -> str:
    """A time as HH:MM. In a household on the 12-hour clock, a one-digit hour with no am or pm ("4:30", "7") is
    asked about, not guessed; "10:00" or "09:30" read as the 24-hour clock."""
    text = fold(value).replace(" ", "")
    if hh.settings.get("time_format") == "12h" and re.fullmatch(r"[1-9](?::[0-5]\d)?", text):
        raise ToolError(f"Is {value} in the morning or the evening?",
                        hint=f"Say {value}am or {value}pm (or use the 24-hour clock).", code="ambiguous_time")  # fmt: skip
    return parse_time(value).strftime("%H:%M")


def _members(ctx, text) -> list:
    if not text:
        return []
    from .context import find_member

    ids = []
    for name in re.split(r",|\band\b|&", text):
        if name.strip():
            try:
                member = find_member(ctx.household, name.strip())
            except ToolError as exc:
                if exc.code != "not_found":
                    raise
                raise ToolError(f"{name.strip()} isn't in the household.",
                                hint="--for names household members only. For someone else, put their name in the "
                                "title or --notes (and use --private to keep it to yourself).",
                                code="not_found") from None  # fmt: skip
            if member["id"] not in ids:
                ids.append(member["id"])
    return ids


def find_event(ctx, data: dict, query) -> dict:
    ctx.viewer.require("calendar", "view", "see the calendar")
    ctx.viewer.require_sees("calendar")
    pool = [e for e in data["events"] if visible(ctx.viewer, e)]
    hh = ctx.household

    def label(event):
        when = hh.day(_dt.date.fromisoformat(event["date"]))
        when += f" {fmt_time(event['time'], hh.settings)}" if event.get("time") else ""
        return f"{event['title']}, {when}" + (f", {recur.describe(event['rrule'])}" if event.get("rrule") else "")

    return match_one(pool, query, "event", key="title", hint="See the calendar with: fridge cal agenda", label=label)


def _times(hh, args) -> tuple:
    time = _clock(hh, args.time) if args.time else None
    end_time = None
    if args.end and not time:
        raise ToolError("--end needs a start --time.", code="usage")
    if args.end:
        end_time = _clock(hh, args.end)
    elif args.minutes and time:
        begin = _dt.datetime.combine(_dt.date(2000, 1, 1), parse_time(time))
        end_time = (begin + _dt.timedelta(minutes=args.minutes)).strftime("%H:%M")
    return time, end_time


def cmd_add(ctx, args) -> dict:
    ctx.viewer.require("calendar", "edit", "add events")
    hh = ctx.household
    title = clean_text(args.title, "event title", max_len=150)
    day = _date(hh, args.date)
    time, end_time = _times(hh, args)
    end_date = _date(hh, args.until_date).isoformat() if args.until_date else None
    if end_date and end_date < day.isoformat():
        raise ToolError("The event ends before it starts.", code="bad_date")
    if end_date and (_dt.date.fromisoformat(end_date) - day).days > MAX_SPAN_DAYS:
        raise ToolError("An event can last a year at most.", hint="Check --until-date, or make it a repeating event.",
                        code="bad_date")  # fmt: skip
    kind = (args.type or guess_type(title)).lower()
    if kind not in TYPES:
        raise ToolError(f"{args.type!r} isn't an event type.", hint="Types: " + ", ".join(TYPES) + ".",
                        code="bad_type")  # fmt: skip
    members = _members(ctx, args.who)
    vis = "private" if args.private else (args.visibility or ("members" if args.only else "household"))
    if vis not in VISIBILITY:
        raise ToolError(f"{vis!r} isn't a visibility.", hint="household, members or private.", code="usage")
    if vis == "members" and not members:
        raise ToolError("Who should see it? Name them with --for.", code="usage")
    rrule = None
    if args.repeat:
        until = _date(hh, args.until) if args.until else None
        rrule = recur.from_words(args.repeat, day, until=until, count=args.times)
        first = recur.next_after(recur.parse(rrule), day, day - _dt.timedelta(days=1))
        moved = first and first != day
        day = first or day
    elif args.until or args.times:
        raise ToolError("--until and --times go with --repeat.", code="usage")
    else:
        moved = False
    with hh.transaction(dry_run=args.dry_run):
        data = hh.data("calendar")
        event = {
            "id": hh.next_id("event"), "title": title, "type": kind, "icon": guess_icon(title, kind), "kind": "event",
            "date": day.isoformat(), "time": time, "end_time": end_time, "end_date": end_date,
            "location": clean_text(args.location, "location", max_len=200, required=False),
            "notes": clean_text(args.notes, "notes", max_len=2000, required=False),
            "visibility": vis, "members": members, "owner": ctx.member["id"],
            "reminders": parse_reminders(args.remind), "rrule": rrule, "exdates": [], "overrides": {},
            "source": "manual", "created_at": now_stamp(),
        }  # fmt: skip
        data["events"].append(event)
        hh.touch("calendar")
        hh.log("cal.add", ctx.member["id"], event=event["id"])
        occ = occurrences(hh, event, day, day)[0]
    verb = "Would add" if args.dry_run else "Added"
    summary = f"{verb} {occ['icon']} {title} — {day_label(day, hh.today(), hh.settings)}"
    if end_date:
        summary += f" to {hh.day(_dt.date.fromisoformat(end_date))}"
    if time:
        summary += f", {fmt_time(time, hh.settings)}" + (f"–{fmt_time(end_time, hh.settings)}" if end_time else "")
    if rrule:
        summary += f", repeating {recur.describe(rrule)}"
    if moved:
        summary += " (moved to the first date that matches the repeat)"
    if vis != "household":
        summary += " (private)" if vis == "private" else f" (only {', '.join(hh.member_name(m) for m in members)})"
    return {"event": occ, "event_id": event["id"], "dry_run": args.dry_run, "summary": summary + "."}


def _range_command(ctx, first: _dt.date, last: _dt.date, args, title: str) -> dict:
    hh = ctx.household
    ctx.viewer.require("calendar", "view", "see the calendar")
    ctx.viewer.require_sees("calendar")
    member_id = None
    if getattr(args, "who", None):
        from .context import find_member

        member_id = find_member(hh, args.who)["id"]
    layers = [x.strip() for x in (args.layers or "").split(",") if x.strip()]
    occs = agenda(ctx, first, last, member_id, layers)
    text = f"{title}\n" + agenda_text(occs, hh.settings, hh.today(), first=first, last=last, headings=first != last)
    span = hh.day(first) if first == last else f"{hh.day(first)} to {hh.day(last)}"
    summary = f"{plural(len(occs), 'thing')} on the calendar, {span}."
    return {"from": first.isoformat(), "to": last.isoformat(), "occurrences": occs, "text": text, "summary": summary}


def cmd_agenda(ctx, args) -> dict:
    hh = ctx.household
    first = _date(hh, args.start)
    last = first + _dt.timedelta(days=max(1, args.days) - 1)
    return _range_command(ctx, first, last, args, f"Next {plural(args.days, 'day')}")


def cmd_day(ctx, args) -> dict:
    day = _date(ctx.household, args.date)
    return _range_command(ctx, day, day, args, day_label(day, ctx.household.today(), ctx.household.settings))


def cmd_week(ctx, args) -> dict:
    hh = ctx.household
    day = _date(hh, args.date)
    first = day - _dt.timedelta(days=(day.weekday() - _week_start(hh)) % 7)
    title = f"Week of {hh.day(first)}"
    return _range_command(ctx, first, first + _dt.timedelta(days=6), args, title)


def cmd_month(ctx, args) -> dict:
    hh = ctx.household
    if args.month:
        first = _month_named(hh, args.month)
    else:
        first = hh.today().replace(day=1)
    last = (first.replace(day=28) + _dt.timedelta(days=4)).replace(day=1) - _dt.timedelta(days=1)
    return _range_command(ctx, first, last, args, f"{MONTHS[first.month - 1]} {first.year}")


def cmd_show(ctx, args) -> dict:
    hh = ctx.household
    data = hh.data("calendar")
    event = find_event(ctx, data, args.event)
    upcoming = occurrences(hh, event, hh.today(), hh.today() + _dt.timedelta(days=370))[:5]
    view = {k: event.get(k) for k in ("id", "title", "type", "date", "time", "end_time", "end_date", "location",
                                      "notes", "visibility", "reminders")}  # fmt: skip
    view["for"] = [hh.member_name(m) for m in event.get("members", [])]
    view["repeats"] = recur.describe(event.get("rrule"))
    view["next"] = [o["date"] for o in upcoming]
    nxt = ", ".join(view["next"][:3]) or "none"
    return {"event": view, "summary": f"{event['title']}: {view['repeats']}; next {nxt}."}


def _owned_or_editor(ctx, event: dict) -> None:
    ctx.viewer.require("calendar", "edit", "change events")
    if event.get("visibility") == "private" and event.get("owner") != ctx.member["id"]:
        raise ToolError("That's someone else's private event.", code="not_authorized")


def cmd_edit(ctx, args) -> dict:
    hh = ctx.household
    with hh.transaction(dry_run=args.dry_run):
        data = hh.data("calendar")
        event = find_event(ctx, data, args.event)
        _owned_or_editor(ctx, event)
        changes = {}
        if args.title:
            changes["title"] = clean_text(args.title, "event title", max_len=150)
        if args.time:
            changes["time"] = _clock(hh, args.time)
        if args.end:
            changes["end_time"] = _clock(hh, args.end)
        if args.all_day:
            changes["time"] = None
            changes["end_time"] = None
        if args.location is not None:
            changes["location"] = clean_text(args.location, "location", max_len=200, required=False)
        if args.date:
            changes["date"] = _date(hh, args.date).isoformat()
        if args.on:
            # Just one date of a repeating event.
            day = _date(hh, args.on).isoformat()
            if not event.get("rrule"):
                raise ToolError("--on is for one date of a repeating event.", code="usage")
            if not occurrences(hh, event, _dt.date.fromisoformat(day), _dt.date.fromisoformat(day)):
                raise ToolError(f"{event['title']} doesn't happen on {hh.day(_dt.date.fromisoformat(day))}.",
                                code="not_found")  # fmt: skip
            override = event.setdefault("overrides", {}).setdefault(day, {})
            _keep_length(changes, override.get("time", event.get("time")),
                         override.get("end_time", event.get("end_time")))  # fmt: skip
            override.update({k: v for k, v in changes.items()})
            what = f"{hh.day(_dt.date.fromisoformat(day))} only"
        else:
            restricted = event.get("visibility", "household") != "household"
            if (args.visibility or (args.who is not None and restricted)) and event.get("owner") != ctx.member["id"]:
                raise ToolError(
                    "Only the person who made this event can change who sees it.",
                    hint=f"Ask {hh.member_name(event.get('owner')) or 'them'} to change it.",
                    code="not_authorized",
                )
            if args.who is not None:
                changes["members"] = _members(ctx, args.who)
            if args.remind is not None:
                changes["reminders"] = parse_reminders(args.remind)
            if args.notes is not None:
                changes["notes"] = clean_text(args.notes, "notes", max_len=2000, required=False)
            if args.visibility:
                if args.visibility not in VISIBILITY:
                    raise ToolError("household, members or private.", code="usage")
                changes["visibility"] = args.visibility
            if args.type:
                if args.type not in TYPES:
                    raise ToolError("Unknown type.", hint=", ".join(TYPES), code="bad_type")
                changes["type"], changes["icon"] = args.type, TYPES[args.type]
            if args.no_repeat:
                changes["rrule"] = None
            elif args.repeat:
                start = _dt.date.fromisoformat(changes.get("date", event["date"]))
                changes["rrule"] = recur.from_words(args.repeat, start)
            _keep_length(changes, event.get("time"), event.get("end_time"))
            event.update(changes)
            what = "every date" if event.get("rrule") else "the event"
        if not changes:
            raise ToolError("Nothing to change.", hint="See: fridge cal edit --help", code="usage")
        event["updated_at"] = now_stamp()
        hh.touch("calendar")
        hh.log("cal.edit", ctx.member["id"], event=event["id"], fields=sorted(changes))
    now_at = ""
    if changes.get("time"):
        now_at = f" It's now {fmt_time(changes['time'], hh.settings)}"
        now_at += (f"–{fmt_time(changes['end_time'], hh.settings)}." if changes.get("end_time") else ".")
    verb = "Would update" if args.dry_run else "Updated"
    return {"event_id": event["id"], "changed": sorted(changes), "dry_run": args.dry_run,
            "summary": f"{verb} {event['title']} ({what}): {', '.join(sorted(changes))}.{now_at}"}  # fmt: skip


def _keep_length(changes: dict, old_time, old_end) -> None:
    """A new start time with no new end keeps the event's length (6:30 for a 5:30-7:00 practice ends at 8:00)."""
    if not changes.get("time") or "end_time" in changes or not old_time or not old_end:
        return
    begin, end = parse_time(old_time), parse_time(old_end)
    length = (_dt.datetime.combine(_dt.date(2000, 1, 1), end) - _dt.datetime.combine(_dt.date(2000, 1, 1), begin))
    if length.total_seconds() <= 0:
        length += _dt.timedelta(days=1)  # it ran past midnight
    new_begin = _dt.datetime.combine(_dt.date(2000, 1, 1), parse_time(changes["time"]))
    changes["end_time"] = (new_begin + length).strftime("%H:%M")


def cmd_skip(ctx, args) -> dict:
    hh = ctx.household
    with hh.transaction(dry_run=args.dry_run):
        data = hh.data("calendar")
        event = find_event(ctx, data, args.event)
        _owned_or_editor(ctx, event)
        day = _date(hh, args.on)
        if args.undo:
            event["exdates"] = [d for d in event.get("exdates", []) if d != day.isoformat()]
            verb = "Brought back"
        else:
            if not occurrences(hh, event, day, day):
                raise ToolError(f"{event['title']} doesn't happen on {hh.day(day)}.", code="not_found")
            event.setdefault("exdates", []).append(day.isoformat())
            verb = "Skipped"
        hh.touch("calendar")
        hh.log("cal.skip", ctx.member["id"], event=event["id"], date=day.isoformat())
    if args.dry_run:
        verb = "Would bring back" if args.undo else "Would skip"
    soon = {0: " (today)", 1: " (tomorrow)"}.get((day - hh.today()).days, "")
    return {"dry_run": args.dry_run, "summary": f"{verb} {event['title']} on {hh.day(day)}{soon}."}


def cmd_delete(ctx, args) -> dict:
    hh = ctx.household
    with hh.transaction():
        data = hh.data("calendar")
        event = find_event(ctx, data, args.event)
        _owned_or_editor(ctx, event)
        if args.start:
            if not event.get("rrule"):
                raise ToolError("--from-date is for repeating events.", code="usage")
            stop = _date(hh, args.start) - _dt.timedelta(days=1)
            rule = recur.parse(event["rrule"])
            rule["until"], rule["count"] = stop, None
            event["rrule"] = recur.to_text(rule)
            summary = f"{event['title']} now ends on {hh.day(stop)}."
        else:
            data["events"] = [e for e in data["events"] if e["id"] != event["id"]]
            summary = f"Deleted {event['title']}" + (" and all its repeats." if event.get("rrule") else ".")
        hh.touch("calendar")
        hh.log("cal.delete", ctx.member["id"], event=event["id"])
    return {"summary": summary}


def cmd_birthday(ctx, args) -> dict:
    ctx.viewer.require("calendar", "edit", "add birthdays")
    hh = ctx.household
    member = None
    if args.member:
        from .context import find_member

        member = find_member(hh, args.member)
    name = clean_text(args.name or (member["name"] if member else None), "name", max_len=60)
    year, month, day = _month_day(args.date, hh.today())
    dropped = bool(member and access.is_minor(member) and year)
    if dropped:
        year = None  # kids' and teens' birth years and ages aren't kept
    try:
        start = _dt.date(year or 2000, month, day)
    except ValueError:
        raise ToolError(f"{args.date!r} isn't a real date.", code="bad_date") from None
    if month == 2 and day == 29:
        rrule = "FREQ=YEARLY;BYMONTH=2;BYMONTHDAY=-1"  # Feb 28 in other years
    else:
        rrule = f"FREQ=YEARLY;BYMONTH={month};BYMONTHDAY={day}"
    kind = "anniversary" if args.anniversary else "birthday"
    title = f"{name}'s birthday" if kind == "birthday" else clean_text(args.name, "name", max_len=100)
    with hh.transaction(dry_run=args.dry_run):
        data = hh.data("calendar")
        event = {
            "id": hh.next_id("event"), "title": title, "type": kind, "icon": TYPES[kind], "kind": "birthday",
            "date": start.isoformat(), "time": None, "end_time": None, "end_date": None, "location": None,
            "notes": None, "visibility": "household", "members": [member["id"]] if member else [],
            "owner": ctx.member["id"], "reminders": [1440], "rrule": rrule, "exdates": [], "overrides": {},
            "birthday": {"name": name, "member": member["id"] if member else None, "year": year},
            "source": "birthday", "created_at": now_stamp(),
        }  # fmt: skip
        data["events"].append(event)
        hh.touch("calendar")
        hh.log("cal.birthday", ctx.member["id"], event=event["id"])
        nxt = recur.next_after(recur.parse(rrule), start, hh.today() - _dt.timedelta(days=1))
    turns = f" (turns {nxt.year - year})" if year and nxt else ""
    note = " Only the day and month are kept for kids and teens." if dropped else ""
    return {"event_id": event["id"], "dry_run": args.dry_run,
            "summary": f"{'Would add' if args.dry_run else 'Added'} 🎂 {title}: next on {hh.day(nxt)}{turns}, "
                       f"every year.{note}"}  # fmt: skip


def upcoming_birthdays(ctx, first: _dt.date, days: int) -> list:
    last = first + _dt.timedelta(days=days - 1)
    return [o for o in agenda(ctx, first, last) if o.get("kind") == "birthday"]


def cmd_birthdays(ctx, args) -> dict:
    hh = ctx.household
    ctx.viewer.require_sees("calendar")
    occs = upcoming_birthdays(ctx, hh.today(), args.days)
    text = agenda_text(occs, hh.settings, hh.today(), empty=f"No birthdays in the next {args.days} days.")
    summary = f"{plural(len(occs), 'birthday')} in the next {args.days} days."
    return {"birthdays": occs, "text": text, "summary": summary}


def cmd_busy(ctx, args) -> dict:
    hh = ctx.household
    first = _date(hh, args.start)
    last = first + _dt.timedelta(days=max(1, args.days) - 1)
    busy = busy_evenings(ctx, first, last)
    lines = []
    for day, titles in sorted(busy.items()):
        lines.append(f"{day_label(_dt.date.fromisoformat(day), hh.today(), hh.settings)}: {', '.join(titles)}")
    summary = f"{plural(len(busy), 'busy evening')} between {hh.day(first)} and {hh.day(last)}."
    return {"busy": busy, "text": "\n".join(lines) or "No busy evenings.", "summary": summary}


def forget_member(hh, member_id: str) -> list:
    data = hh.data("calendar")
    before = len(data["events"])
    def theirs(event: dict) -> bool:
        private = event.get("visibility") == "private" and event.get("owner") == member_id
        return private or (event.get("birthday") or {}).get("member") == member_id

    data["events"] = [e for e in data["events"] if not theirs(e)]
    for event in data["events"]:
        event["members"] = [m for m in event.get("members", []) if m != member_id]
        if event.get("owner") == member_id:
            event["owner"] = None
    hh.touch("calendar")
    gone = before - len(data["events"])
    return [f"deleted {plural(gone, 'private event')}"] if gone else []


def register(cli) -> None:
    from .members import FORGET_HOOKS

    FORGET_HOOKS.append(forget_member)
    grp = cli.group("cal", "The household calendar: events, repeats, birthdays, views, busy evenings.")
    p = grp.add(
        "add",
        "Add an event: all day, or with a time; who it's for; visibility; reminders; repeats.",
        [
            'fridge cal add "Dentist" --date friday --time 15:30 --minutes 45 --for Theo --remind 1d,1h',
            'fridge cal add "Soccer practice" --date tuesday --time 17:30 --end 19:00 --for Lily --repeat weekly',
            'fridge cal add "Camping trip" --date 2026-11-06 --until-date 2026-11-08',
            'fridge cal add "Surprise party planning" --date saturday --time 20:00 --for "Ana, Luis" --only',
        ],
        cmd_add,
    )
    p.add_argument("title")
    p.add_argument("--date", help="today, friday, next week, 2026-11-02 ... (default today)")
    p.add_argument("--time", help="Start time; leave out for all day")
    p.add_argument("--end", help="End time")
    p.add_argument("--minutes", type=int, help="Length in minutes (instead of --end)")
    p.add_argument("--until-date", help="Last day of a multi-day event")
    p.add_argument("--location")
    p.add_argument("--type", help="appointment, school, sports, health, social, work, travel, ... (guessed)")
    p.add_argument("--for", dest="who", help='Who it\'s for: "Theo, Lily"')
    p.add_argument("--only", action="store_true", help="Only the people in --for (and you) can see it")
    p.add_argument("--private", action="store_true", help="Only you can see it, and never in a group chat")
    p.add_argument("--visibility", help="household, members or private")
    p.add_argument("--remind", help='Reminders before the start: "30m, 1d"')
    p.add_argument("--repeat", help="daily, weekly, every 2 weeks, monthly on the 2nd tuesday, yearly ...")
    p.add_argument("--until")
    p.add_argument("--times", type=int)
    p.add_argument("--notes")
    p.add_argument("--dry-run", action="store_true")
    for name, func, text, extra in (
        ("agenda", cmd_agenda, "The next days, in order (default 7).", ["fridge cal agenda --days 14 --for Lily"]),
        ("day", cmd_day, "One day.", ["fridge cal day tomorrow"]),
        ("week", cmd_week, "The week containing a date.", ["fridge cal week --layers meals"]),
        ("month", cmd_month, "A whole month.", ["fridge cal month 2026-11"]),
    ):  # fmt: skip
        p = grp.add(name, text, extra, func)
        if name == "agenda":
            p.add_argument("--days", type=int, default=7)
            p.add_argument("--from-date", dest="start", help="Start from this date")
        elif name == "month":
            p.add_argument("month", nargs="?", help="YYYY-MM (default this month)")
        else:
            p.add_argument("date", nargs="?")
        p.add_argument("--for", dest="who", help="Only events involving this member")
        p.add_argument("--layers", help="Extra layers, comma list: meals, bills")
    p = grp.add("show", "One event with its repeat and next dates.", ['fridge cal show "Soccer practice"'], cmd_show)
    p.add_argument("event")
    p = grp.add(
        "edit",
        "Change an event, or with --on just one date of a repeating event.",
        ['fridge cal edit "Soccer practice" --on 2026-10-27 --time 18:00', 'fridge cal edit Dentist --date monday'],
        cmd_edit,
    )
    p.add_argument("event")
    p.add_argument("--on", help="Only this date of a repeating event")
    p.add_argument("--title")
    p.add_argument("--date")
    p.add_argument("--time")
    p.add_argument("--end")
    p.add_argument("--all-day", action="store_true")
    p.add_argument("--location")
    p.add_argument("--for", dest="who")
    p.add_argument("--remind")
    p.add_argument("--notes")
    p.add_argument("--visibility")
    p.add_argument("--type")
    p.add_argument("--repeat")
    p.add_argument("--no-repeat", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p = grp.add("skip", "Skip one date of a repeating event (--undo to bring it back).",
                ['fridge cal skip "Soccer practice" --on 2026-10-27'], cmd_skip)  # fmt: skip
    p.add_argument("event")
    p.add_argument("--on", required=True)
    p.add_argument("--undo", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p = grp.add(
        "delete",
        "Delete an event (all repeats), or end a repeating one from a date.",
        ["fridge cal delete Dentist", 'fridge cal delete "Soccer practice" --from-date 2026-12-01'],
        cmd_delete,
    )
    p.add_argument("event")
    p.add_argument("--from-date", dest="start", help="Start from this date")
    p = grp.add(
        "birthday",
        "Add a birthday (or --anniversary) that repeats every year. For kids, day and month only.",
        ['fridge cal birthday --name "Grandma Rosa" --date 1948-03-14', "fridge cal birthday --member Theo --date "
         '"14 March"', 'fridge cal birthday --name "Our anniversary" --date 2012-06-02 --anniversary'],
        cmd_birthday,
    )  # fmt: skip
    p.add_argument("--name")
    p.add_argument("--member", help="A household member (their name is used)")
    p.add_argument("--date", required=True)
    p.add_argument("--anniversary", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p = grp.add("birthdays", "Birthdays and anniversaries coming up.", ["fridge cal birthdays --days 30"],
                cmd_birthdays)  # fmt: skip
    p.add_argument("--days", type=int, default=30)
    p = grp.add("busy", "Busy evenings (events around dinner time), for planning meals.", ["fridge cal busy"],
                cmd_busy)  # fmt: skip
    p.add_argument("--from-date", dest="start", help="Start from this date")
    p.add_argument("--days", type=int, default=7)
