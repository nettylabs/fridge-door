"""Calendar files (.ics, RFC 5545): export the household calendar, and import events from Google, Apple or Outlook.

- Export: only what the person may see; times carry the household's time zone (with a VTIMEZONE block worked out
  from the computer's time zone database), repeats as RRULE, skipped dates as EXDATE, moved dates as their own
  VEVENT with RECURRENCE-ID, reminders as VALARM.
- Import: VEVENTs with dates or times (UTC, a named zone, or floating), DTEND or DURATION, RRULE, EXDATE,
  RECURRENCE-ID changes and cancelled events. Times are converted to the household's time zone. Re-importing the
  same file updates the events it made (matched by UID) instead of duplicating them, but only events the person
  could change by hand: never someone else's private event, never who sees someone else's event, and a private
  import never writes into someone else's event. A file this household exported is recognised (its UIDs carry the
  household's random calendar key) and its events are left as they are.
"""

from __future__ import annotations

import datetime as _dt
import re
import secrets
from pathlib import Path

from . import events, recur
from .util import ToolError, clean_text, get_tz, now_stamp, plural, tz_known, utc_now

PRODID = "-//Netty Labs//Fridge Door//EN"
MAX_BYTES = 5 * 1024 * 1024


# --------------------------------------------------------------------------- writing


def _escape(text: str) -> str:
    return (str(text).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\\n")
            .replace("\n", "\\n"))  # fmt: skip


def _fold(line: str) -> str:
    """Lines longer than 75 octets continue on the next line after a space (RFC 5545 3.1)."""
    data = line.encode("utf-8")
    if len(data) <= 75:
        return line
    parts, current = [], b""
    for char in line:
        piece = char.encode("utf-8")
        if len(current) + len(piece) > (75 if not parts else 74):
            parts.append(current.decode("utf-8"))
            current = b""
        current += piece
    parts.append(current.decode("utf-8"))
    return "\r\n ".join(parts)


def _offset(delta: _dt.timedelta) -> str:
    total = int(delta.total_seconds() // 60)
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    return f"{sign}{total // 60:02d}{total % 60:02d}"


def _nth_weekday(day: _dt.date) -> str:
    """BYDAY for a transition date: "2SU", or "-1SU" when it's the last one in the month."""
    nth = (day.day - 1) // 7 + 1
    last = (day + _dt.timedelta(days=7)).month != day.month
    return f"{-1 if last and nth >= 4 else nth}{recur.DAY_CODES[day.weekday()]}"


def vtimezone(tz_name: str, year: int) -> list:
    """A VTIMEZONE block for a named zone, from the transitions the time zone database has for that year."""
    tz = get_tz(tz_name)
    if tz_name in ("UTC", "") or tz is _dt.timezone.utc:
        return []
    moment = _dt.datetime(year, 1, 1, tzinfo=_dt.timezone.utc)
    previous = moment.astimezone(tz).utcoffset()
    transitions = []
    while moment.year == year:
        later = moment + _dt.timedelta(hours=1)
        offset = later.astimezone(tz).utcoffset()
        if offset != previous:
            wall = (later + previous).replace(tzinfo=None)  # the local time the change happens at, in the old offset
            transitions.append((wall, previous, offset, later.astimezone(tz).dst()))
            previous = offset
        moment = later
    lines = ["BEGIN:VTIMEZONE", f"TZID:{tz_name}"]
    if not transitions:
        jan = _dt.datetime(year, 1, 1, 12, tzinfo=tz)
        off = _offset(jan.utcoffset())
        return lines + ["BEGIN:STANDARD", f"DTSTART:{year}0101T000000", f"TZOFFSETFROM:{off}", f"TZOFFSETTO:{off}",
                        f"TZNAME:{jan.tzname()}", "END:STANDARD", "END:VTIMEZONE"]  # fmt: skip
    for wall, before, after, dst in transitions:
        kind = "DAYLIGHT" if dst else "STANDARD"
        rule = f"RRULE:FREQ=YEARLY;BYMONTH={wall.month};BYDAY={_nth_weekday(wall.date())}"
        lines += [f"BEGIN:{kind}", f"DTSTART:{wall.strftime('%Y%m%dT%H%M%S')}", f"TZOFFSETFROM:{_offset(before)}",
                  f"TZOFFSETTO:{_offset(after)}", rule, f"END:{kind}"]  # fmt: skip
    return lines + ["END:VTIMEZONE"]


def _dt_prop(name: str, day: str, time: str | None, tz_name: str) -> str:
    stamp = _dt.date.fromisoformat(day).strftime("%Y%m%d")
    if not time:
        return f"{name};VALUE=DATE:{stamp}"
    return f"{name};TZID={tz_name}:{stamp}T{time.replace(':', '')}00"


def _calendar_key(hh) -> str:
    """A random tag for this household's event UIDs, so they're unique across every Fridge Door home (two homes
    both have an event E1) and a file this household exported can be recognised when it comes back."""
    key = hh.meta().get("calendar_key")
    if not key:
        with hh.transaction():
            key = hh.meta().setdefault("calendar_key", secrets.token_hex(6))
            hh.touch("household")
    return key


def _own_uid(event_id: str, key: str) -> str:
    return f"{event_id}.{key}@fridge-door"


def _vevent(event: dict, key: str, tz_name: str, stamp: str, override_day: str | None = None,
            change: dict | None = None):  # fmt: skip
    change = change or {}
    day = change.get("date") or (override_day or event["date"])
    time = change.get("time", event.get("time"))
    end_time = change.get("end_time", event.get("end_time"))
    lines = ["BEGIN:VEVENT", f"UID:{event.get('uid') or _own_uid(event['id'], key)}", f"DTSTAMP:{stamp}",
             _dt_prop("DTSTART", day, time, tz_name)]  # fmt: skip
    if time and end_time:
        end_day = day if end_time > time else (_dt.date.fromisoformat(day) + _dt.timedelta(days=1)).isoformat()
        lines.append(_dt_prop("DTEND", end_day, end_time, tz_name))
    elif not time:
        last = event.get("end_date") or event["date"]
        span = (_dt.date.fromisoformat(last) - _dt.date.fromisoformat(event["date"])).days
        end = _dt.date.fromisoformat(day) + _dt.timedelta(days=span + 1)
        lines.append(f"DTEND;VALUE=DATE:{end.strftime('%Y%m%d')}")
    if override_day:
        lines.append(_dt_prop("RECURRENCE-ID", override_day, event.get("time"), tz_name))
    lines.append(f"SUMMARY:{_escape(change.get('title', event['title']))}")
    if change.get("location", event.get("location")):
        lines.append(f"LOCATION:{_escape(change.get('location', event.get('location')))}")
    if event.get("notes"):
        lines.append(f"DESCRIPTION:{_escape(event['notes'])}")
    lines.append(f"CATEGORIES:{_escape(event.get('type', 'other').upper())}")
    if event.get("visibility") in ("private", "members"):
        lines.append("CLASS:PRIVATE")
    if not override_day and event.get("rrule"):
        lines.append(f"RRULE:{_until_utc(event['rrule'], time, tz_name)}")
        for skipped in event.get("exdates", []):
            lines.append(_dt_prop("EXDATE", skipped, event.get("time"), tz_name))
    for minutes in event.get("reminders") or []:
        lines += ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{_escape(event['title'])}",
                  f"TRIGGER:-PT{minutes}M", "END:VALARM"]  # fmt: skip
    lines.append("END:VEVENT")
    return lines


def _until_utc(rule: str, time: str | None, tz_name: str) -> str:
    """A timed event's UNTIL must be a UTC date-time: the end of that day, in the household's time zone."""
    match = re.search(r"UNTIL=(\d{8})(?![T\d])", rule)
    if not time or not match:
        return rule
    end = _dt.datetime.combine(_dt.datetime.strptime(match.group(1), "%Y%m%d").date(), _dt.time(23, 59, 59))
    stamp = end.replace(tzinfo=get_tz(tz_name)).astimezone(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return rule.replace(match.group(0), f"UNTIL={stamp}")


def export(ctx, member_id: str | None = None) -> tuple:
    hh = ctx.household
    key = _calendar_key(hh)
    tz_name = hh.tz()
    stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:{PRODID}", "CALSCALE:GREGORIAN",
             f"X-WR-CALNAME:{_escape(hh.name)}", f"X-WR-TIMEZONE:{tz_name}"]  # fmt: skip
    chosen = [e for e in hh.data("calendar")["events"] if events.visible(ctx.viewer, e)
              and events._involves(None, e, member_id)]  # fmt: skip
    if any(e.get("time") for e in chosen):
        lines += vtimezone(tz_name, hh.today().year)
    for event in chosen:
        lines += _vevent(event, key, tz_name, stamp)
        for day, change in sorted((event.get("overrides") or {}).items()):
            if change.get("cancelled"):
                continue
            lines += _vevent(event, key, tz_name, stamp, override_day=day, change=change)
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n", len(chosen)


# --------------------------------------------------------------------------- reading


def _unescape(text: str) -> str:
    return re.sub(r"\\([nN,;\\])", lambda m: "\n" if m.group(1) in "nN" else m.group(1), text)


def _split(raw: str) -> tuple:
    """Name-and-parameters vs value: the first colon that isn't inside a quoted parameter."""
    quoted = False
    for index, char in enumerate(raw):
        if char == '"':
            quoted = not quoted
        elif char == ":" and not quoted:
            return raw[:index], raw[index + 1 :]
    return raw, ""


def parse_lines(text: str) -> list:
    """Unfold and split content lines into (name, params, value)."""
    unfolded = re.sub(r"\r?\n[ \t]", "", text)
    out = []
    for raw in unfolded.splitlines():
        if not raw.strip() or ":" not in raw:
            continue
        head, value = _split(raw)
        parts = head.split(";")
        params = {}
        for part in parts[1:]:
            if "=" in part:
                key, val = part.split("=", 1)
                params[key.upper()] = val.strip('"')
        out.append((parts[0].upper(), params, value))
    return out


# Outlook and Exchange name time zones the Windows way. The main ones, mapped to IANA names (from CLDR).
WINDOWS_ZONES = {
    "dateline standard time": "Etc/GMT+12", "hawaiian standard time": "Pacific/Honolulu",
    "alaskan standard time": "America/Anchorage", "pacific standard time": "America/Los_Angeles",
    "pacific standard time (mexico)": "America/Tijuana", "us mountain standard time": "America/Phoenix",
    "mountain standard time": "America/Denver", "mountain standard time (mexico)": "America/Mazatlan",
    "central standard time": "America/Chicago", "central standard time (mexico)": "America/Mexico_City",
    "canada central standard time": "America/Regina", "central america standard time": "America/Guatemala",
    "eastern standard time": "America/New_York", "us eastern standard time": "America/Indiana/Indianapolis",
    "atlantic standard time": "America/Halifax", "newfoundland standard time": "America/St_Johns",
    "sa pacific standard time": "America/Bogota", "venezuela standard time": "America/Caracas",
    "pacific sa standard time": "America/Santiago", "e. south america standard time": "America/Sao_Paulo",
    "argentina standard time": "America/Argentina/Buenos_Aires", "greenland standard time": "America/Nuuk",
    "azores standard time": "Atlantic/Azores", "utc": "UTC", "gmt standard time": "Europe/London",
    "greenwich standard time": "Atlantic/Reykjavik", "w. europe standard time": "Europe/Berlin",
    "central europe standard time": "Europe/Budapest", "romance standard time": "Europe/Paris",
    "central european standard time": "Europe/Warsaw", "w. central africa standard time": "Africa/Lagos",
    "gtb standard time": "Europe/Bucharest", "e. europe standard time": "Europe/Chisinau",
    "fle standard time": "Europe/Kiev", "egypt standard time": "Africa/Cairo",
    "south africa standard time": "Africa/Johannesburg", "israel standard time": "Asia/Jerusalem",
    "turkey standard time": "Europe/Istanbul", "arab standard time": "Asia/Riyadh",
    "russian standard time": "Europe/Moscow", "e. africa standard time": "Africa/Nairobi",
    "iran standard time": "Asia/Tehran", "arabian standard time": "Asia/Dubai",
    "afghanistan standard time": "Asia/Kabul", "pakistan standard time": "Asia/Karachi",
    "india standard time": "Asia/Kolkata", "sri lanka standard time": "Asia/Colombo",
    "nepal standard time": "Asia/Kathmandu", "bangladesh standard time": "Asia/Dhaka",
    "myanmar standard time": "Asia/Yangon", "se asia standard time": "Asia/Bangkok",
    "china standard time": "Asia/Shanghai", "singapore standard time": "Asia/Singapore",
    "taipei standard time": "Asia/Taipei", "w. australia standard time": "Australia/Perth",
    "tokyo standard time": "Asia/Tokyo", "korea standard time": "Asia/Seoul",
    "cen. australia standard time": "Australia/Adelaide", "aus central standard time": "Australia/Darwin",
    "e. australia standard time": "Australia/Brisbane", "aus eastern standard time": "Australia/Sydney",
    "tasmania standard time": "Australia/Hobart", "west pacific standard time": "Pacific/Port_Moresby",
    "new zealand standard time": "Pacific/Auckland", "fiji standard time": "Pacific/Fiji",
    "tonga standard time": "Pacific/Tongatapu", "philippine standard time": "Asia/Manila",
    "north asia standard time": "Asia/Krasnoyarsk", "n. central asia standard time": "Asia/Novosibirsk",
    "ekaterinburg standard time": "Asia/Yekaterinburg", "morocco standard time": "Africa/Casablanca",
}  # fmt: skip


def _zone(tzid: str, household_tz: str, warnings: list):
    """The tzinfo for a TZID: an IANA name, a Windows name, or (if neither is known) the household's time zone,
    with a warning so the person can check those times."""
    name = tzid.strip().strip('"')
    if tz_known(name):
        return get_tz(name)
    mapped = WINDOWS_ZONES.get(name.lower())
    if mapped and tz_known(mapped):
        return get_tz(mapped)
    note = (f"The time zone {name!r} in the file isn't one I know, so its times were read as the household's own "
            f"({household_tz}). Check them.")  # fmt: skip
    if note not in warnings:
        warnings.append(note)
    return get_tz(household_tz)


def _to_local(value: str, params: dict, household_tz: str, warnings: list | None = None):
    """A DTSTART-like value -> (date ISO, "HH:MM" or None) in the household's time zone."""
    if params.get("VALUE") == "DATE" or re.fullmatch(r"\d{8}", value):
        return _dt.datetime.strptime(value[:8], "%Y%m%d").date().isoformat(), None
    moment = _dt.datetime.strptime(value[:15], "%Y%m%dT%H%M%S")
    if value.endswith("Z"):
        moment = moment.replace(tzinfo=_dt.timezone.utc)
    elif params.get("TZID"):
        moment = moment.replace(tzinfo=_zone(params["TZID"], household_tz, [] if warnings is None else warnings))
    else:
        moment = moment.replace(tzinfo=get_tz(household_tz))  # floating time: as the household's
    local = moment.astimezone(get_tz(household_tz))
    return local.date().isoformat(), local.strftime("%H:%M")


def _duration(value: str) -> _dt.timedelta:
    match = re.fullmatch(r"([+-])?P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?", value.strip())
    if not match:
        return _dt.timedelta(0)
    sign = -1 if match.group(1) == "-" else 1
    weeks, days, hours, mins, secs = (int(g) if g else 0 for g in match.groups()[1:])
    return sign * _dt.timedelta(weeks=weeks, days=days, hours=hours, minutes=mins, seconds=secs)


def read_events(text: str, household_tz: str) -> tuple:
    """VEVENTs as plain dicts, plus warnings."""
    found, warnings, current, depth_alarm = [], [], None, False
    for name, params, value in parse_lines(text):
        if name == "BEGIN" and value.upper() == "VEVENT":
            current = {"exdates": [], "reminders": []}
        elif name == "BEGIN" and value.upper() == "VALARM" and current is not None:
            depth_alarm = True
        elif name == "END" and value.upper() == "VALARM":
            depth_alarm = False
        elif name == "END" and value.upper() == "VEVENT" and current is not None:
            found.append(current)
            current = None
        elif current is not None and depth_alarm:
            if name == "TRIGGER":
                delta = _duration(value)
                if delta <= _dt.timedelta(0):
                    current["reminders"].append(int(-delta.total_seconds() // 60))
        elif current is not None:
            if name == "UID":
                current["uid"] = value.strip()
            elif name == "SUMMARY":
                current["title"] = _unescape(value)
            elif name == "LOCATION":
                current["location"] = _unescape(value)
            elif name == "DESCRIPTION":
                current["notes"] = _unescape(value)
            elif name == "STATUS":
                current["status"] = value.upper()
            elif name == "DTSTART":
                current["start"] = _to_local(value, params, household_tz, warnings)
                current["start_raw"] = (value, params)
            elif name == "DTEND":
                current["end"] = _to_local(value, params, household_tz, warnings)
                current["end_is_date"] = params.get("VALUE") == "DATE" or re.fullmatch(r"\d{8}", value) is not None
            elif name == "DURATION":
                current["duration"] = _duration(value)
            elif name == "RRULE":
                current["rrule"] = value
            elif name == "EXDATE":
                for item in value.split(","):
                    current["exdates"].append(_to_local(item, params, household_tz, warnings)[0])
            elif name == "RECURRENCE-ID":
                current["recurrence_id"] = _to_local(value, params, household_tz, warnings)[0]
            elif name == "CLASS":
                current["class"] = value.upper()
    return found, warnings


def _may_update(ctx, event: dict) -> bool:
    """An import only changes events the person could change by hand: ones they can see, and never someone else's
    private event (the same rules as fridge cal edit)."""
    if not events.visible(ctx.viewer, event):
        return False
    return event.get("visibility") != "private" or event.get("owner") == ctx.member["id"]


IMPORTED = ("title", "date", "time", "end_time", "end_date", "location", "notes", "rrule", "exdates", "reminders")


def _is_private(item: dict, private: bool) -> bool:
    return private or item.get("class") in ("PRIVATE", "CONFIDENTIAL")


def import_events(ctx, text: str, members=(), private: bool = False, dry_run: bool = False) -> dict:
    hh = ctx.household
    tz_name = hh.tz()
    raw, warnings = read_events(text, tz_name)
    masters = [e for e in raw if not e.get("recurrence_id")]
    changes = [e for e in raw if e.get("recurrence_id")]
    added, updated, skipped, already, unchanged, removed, preview = [], [], [], [], [], [], []
    me = ctx.member["id"]

    def when(day: str, time: str | None) -> str:
        return hh.day(_dt.date.fromisoformat(day)) + (f" {events.fmt_time(time, hh.settings)}" if time else "")

    key = hh.meta().get("calendar_key")  # none yet: this household never exported, so no file can be its own
    ours = re.compile(rf"(E\d+)\.{re.escape(key)}@fridge-door") if key else None
    with hh.transaction(dry_run=dry_run):
        data = hh.data("calendar")
        by_id = {e["id"]: e for e in data["events"] if _may_update(ctx, e)}
        by_uid = {}
        for event in by_id.values():  # when two events share a UID, the person's own one wins
            if event.get("uid") and (event["uid"] not in by_uid or event.get("owner") == me):
                by_uid[event["uid"]] = event
        touched = {}  # UID in the file -> the event this import added or updated

        def own(uid):
            return ours.fullmatch(uid) if ours and uid else None

        def target(uid, is_private: bool):
            event = by_uid.get(uid) if uid else None
            if event and is_private and event.get("owner") != me:
                return None  # a private import never writes into someone else's event: everyone who sees it would
            return event

        for item in masters:
            if item.get("status") == "CANCELLED" and item.get("uid") and not own(item.get("uid")):
                gone = target(item["uid"], _is_private(item, private))
                if gone:  # cancelled at the source since the last import: it comes off the calendar here too
                    data["events"].remove(gone)
                    removed.append(gone["title"])
                    preview.append(f"- {gone['title']} — {when(gone['date'], gone.get('time'))} (cancelled)")
                    continue
            if item.get("status") == "CANCELLED" or "start" not in item:
                skipped.append(item.get("title") or "(untitled)")
                continue
            day, time = item["start"]
            end_date, end_time = None, None
            if time:
                if "end" in item:
                    end_time = item["end"][1]
                elif item.get("duration"):
                    clock = _dt.datetime.strptime(time, "%H:%M").time()
                    begin = _dt.datetime.combine(_dt.date.fromisoformat(day), clock)
                    end_time = (begin + item["duration"]).strftime("%H:%M")
            elif "end" in item:
                last = _dt.date.fromisoformat(item["end"][0]) - _dt.timedelta(days=1 if item.get("end_is_date") else 0)
                longest = _dt.date.fromisoformat(day) + _dt.timedelta(days=events.MAX_SPAN_DAYS)
                if last > longest:
                    warnings.append(f"{item.get('title') or 'An event'} lasted over a year; it was cut to one.")
                    last = longest
                if last > _dt.date.fromisoformat(day):
                    end_date = last.isoformat()
            rrule = None
            if item.get("rrule"):
                try:
                    rrule = recur.normalize(item["rrule"])
                except ToolError as exc:
                    warnings.append(f"{item.get('title')}: its repeat can't be read ({exc.message}); only the first "
                                    "date was imported.")  # fmt: skip
            title = clean_text(item.get("title") or "Untitled", "event title", max_len=150)
            uid = item.get("uid")
            match = own(uid)
            if match and match.group(1) in by_id:
                already.append(title)  # exported from this household: it's here already, left as it is
                continue
            if match:
                uid = None  # from this household but not one this person may change: a new event with its own UID
            is_private = _is_private(item, private)
            kind = events.guess_type(title)
            record = {
                "title": title, "type": kind, "icon": events.TYPES[kind], "kind": "event", "date": day,
                "time": time, "end_time": end_time, "end_date": end_date,
                "location": clean_text(item.get("location"), "location", max_len=200, required=False),
                "notes": (item.get("notes") or "")[:2000] or None,
                "visibility": "private" if is_private else "household",
                "members": list(members), "reminders": sorted(set(item.get("reminders", []))), "rrule": rrule,
                "exdates": sorted(set(item.get("exdates", []))), "source": "ics", "uid": uid,
            }  # fmt: skip
            existing = target(uid, is_private)
            if existing:
                # Only what the file changed since the last import is changed here, so edits made in Fridge Door
                # (a note, a new time) stay. Who sees it stays as it is (a re-import never widens it); only its maker
                # may make it private, and --for changes who it's for only where fridge cal edit would allow it.
                before = existing.get("ics_fields") or {}
                fields = [f for f in IMPORTED if record[f] != before.get(f, existing.get(f))]
                for field in fields:
                    existing[field] = record[field]
                if "title" in fields:
                    existing["type"], existing["icon"] = kind, events.guess_icon(title, kind)
                existing["ics_fields"] = {f: record[f] for f in IMPORTED}
                if is_private and existing.get("visibility") != "private":
                    existing["visibility"] = "private"
                    fields.append("visibility")
                if members and existing.get("members") != list(members) and (
                        existing.get("owner") == me or existing.get("visibility", "household") == "household"):
                    existing["members"] = list(members)
                    fields.append("members")
                if fields:
                    existing["updated_at"] = now_stamp()
                    updated.append(title)
                    preview.append(f"~ {title} — {when(existing['date'], existing.get('time'))} "
                                   f"({', '.join(fields)} changed)")  # fmt: skip
                else:
                    unchanged.append(title)
            else:
                record.update({"id": hh.next_id("event"), "owner": me, "overrides": {}, "created_at": now_stamp(),
                               "icon": events.guess_icon(title, kind),
                               "ics_fields": {f: record[f] for f in IMPORTED}})  # fmt: skip
                data["events"].append(record)
                existing = record
                added.append(title)
                preview.append(f"+ {title} — {when(day, time)}")
            if item.get("uid"):
                touched[item["uid"]] = existing
        for item in changes:
            uid = item.get("uid")
            master = touched.get(uid) or (None if own(uid) else target(uid, _is_private(item, private)))
            if not master and not own(uid):
                warnings.append(f"A change to {item.get('title') or 'an event'} on {item['recurrence_id']} was left "
                                "out: its main event isn't in the file or the calendar.")  # fmt: skip
            if not master or "start" not in item:
                continue
            original = item["recurrence_id"]
            if item.get("status") == "CANCELLED":
                master.setdefault("exdates", []).append(original)
                continue
            day, time = item["start"]
            change = {"date": day, "time": time}
            if "end" in item and time:
                change["end_time"] = item["end"][1]
            if item.get("title") and item["title"] != master["title"]:
                change["title"] = item["title"]
            if item.get("location"):
                change["location"] = item["location"]
            master.setdefault("overrides", {})[original] = change
        hh.touch("calendar")
        hh.log("cal.import", me, added=len(added), updated=len(updated), already=len(already), removed=len(removed))
    return {"added": added, "updated": updated, "unchanged": unchanged, "removed": removed, "already": already,
            "skipped": skipped, "warnings": warnings, "text": "\n".join(preview) or "Nothing new."}


# --------------------------------------------------------------------------- commands


def cmd_export(ctx, args) -> dict:
    ctx.viewer.require("calendar", "view", "export the calendar")
    ctx.viewer.require_sees("calendar")
    hh = ctx.household
    member_id = None
    if args.who:
        from .context import find_member

        member_id = find_member(hh, args.who)["id"]
    text, count = export(ctx, member_id)
    name = re.sub(r"[^A-Za-z0-9_-]+", "-", args.file or f"{hh.name}-calendar").strip("-").lower() or "calendar"
    folder = hh.output_for(ctx.member["id"], ctx.chat_id if ctx.viewer.group else None)  # whose it is
    path = folder / (name if name.endswith(".ics") else f"{name}.ics")
    path.write_bytes(text.encode("utf-8"))  # keep the CRLF line ends calendars expect
    return {"file": str(path), "events": count,
            "summary": f"Saved {plural(count, 'event')} to {path.name}. Open it with Google, Apple or Outlook Calendar "
                       "to add them there."}  # fmt: skip


def cmd_import(ctx, args) -> dict:
    ctx.viewer.require("calendar", "edit", "import events")
    ctx.viewer.require_sees("calendar")
    file = Path(args.file).expanduser()
    if not file.is_file():
        raise ToolError(f"There's no file at {args.file}.", hint="Save the .ics file first, then pass its path.",
                        code="no_file")  # fmt: skip
    if file.stat().st_size > MAX_BYTES:
        raise ToolError("That calendar file is too big (over 5 MB).", code="too_big")
    text = file.read_text(encoding="utf-8", errors="replace")
    if "BEGIN:VCALENDAR" not in text.upper():
        raise ToolError("That isn't a calendar (.ics) file.", code="bad_file")
    members = []
    if args.who:
        members = events._members(ctx, args.who)
    result = import_events(ctx, text, members=members, private=args.private, dry_run=args.dry_run)
    verb = "Would import" if args.dry_run else "Imported"
    summary = f"{verb} {plural(len(result['added']), 'new event')}"
    if result["updated"]:
        summary += f", {'would update' if args.dry_run else 'updated'} {len(result['updated'])}"
    if result["removed"]:
        summary += f", {'would remove' if args.dry_run else 'removed'} {len(result['removed'])} cancelled at the source"
    if result["unchanged"]:
        summary += f", {len(result['unchanged'])} unchanged"
    if result["already"]:
        summary += f", {len(result['already'])} already in the calendar"
    if result["skipped"]:
        summary += f", skipped {len(result['skipped'])} cancelled"
    return dict(result, dry_run=args.dry_run, summary=summary + ".")


def register(cli) -> None:
    grp = cli.group("ics", "Calendar files (.ics): export to Google, Apple or Outlook, or import from them.")
    p = grp.add("export", "Save the calendar (what you may see) as an .ics file.",
                ["fridge ics export", "fridge ics export --for Lily --file lily"], cmd_export)  # fmt: skip
    p.add_argument("--for", dest="who", help="Only events involving this member")
    p.add_argument("--file", help="File name (saved in the household's output folder)")
    p = grp.add(
        "import",
        "Import events from an .ics file. Re-importing the same file updates its events instead of duplicating.",
        ["fridge ics import /workspace/downloads/school-term.ics --for \"Theo, Lily\"",
         "fridge ics import work.ics --private --dry-run"],
        cmd_import,
    )  # fmt: skip
    p.add_argument("file")
    p.add_argument("--for", dest="who", help="Who the events are for")
    p.add_argument("--private", action="store_true", help="Import them as your private events")
    p.add_argument("--dry-run", action="store_true")
