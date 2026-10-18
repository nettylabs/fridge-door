"""Repeat rules: a standard-library subset of the iCalendar RRULE format, shared by chores, events and bills.

Supported: FREQ=DAILY|WEEKLY|MONTHLY|YEARLY, INTERVAL, BYDAY (with ordinals such as 2TU or -1FR for monthly and
yearly rules), BYMONTHDAY (negative counts from the month's end), BYMONTH, BYSETPOS, COUNT, UNTIL and WKST.
Rules are stored as RRULE text, so calendar files (.ics) carry them to Google, Apple or Outlook unchanged.

Dates are whole local days: a daylight-saving change never moves a chore or a birthday.
"""

from __future__ import annotations

import calendar
import datetime as _dt
import re

from .util import ToolError, fold

FREQS = ("DAILY", "WEEKLY", "MONTHLY", "YEARLY")
DAY_CODES = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")  # index = date.weekday()
DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
MONTH_NAMES = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_FULL_DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_ORDINAL_WORDS = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4,
                  "fifth": 5, "5th": 5, "sixth": 6, "6th": 6, "last": -1, "second last": -2,
                  "second-last": -2}  # fmt: skip
_NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
                 "ten": 10, "eleven": 11, "twelve": 12}  # fmt: skip
MAX_PERIODS = 20000  # a safety stop for rules that never match


def _bad(message: str, hint: str | None = None) -> ToolError:
    return ToolError(
        message,
        hint=hint or 'Try words like "weekly on mon,thu", "every 2 weeks", "monthly on the last friday", '
        '"yearly", or an RRULE such as FREQ=WEEKLY;BYDAY=MO.',
        code="bad_repeat",
    )


def _ints(text: str, low: int, high: int, name: str, allow_zero: bool = False) -> list:
    values = []
    for part in text.split(","):
        if not re.fullmatch(r"[+-]?\d{1,4}", part):
            raise _bad(f"{name}={text} isn't a list of numbers.")
        value = int(part)
        if not (low <= value <= high) or (value == 0 and not allow_zero):
            raise _bad(f"{name}={text} is out of range.")
        values.append(value)
    return values


def parse(text: str) -> dict:
    """Parse and check RRULE text such as "FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,TH". Raises bad_repeat."""
    raw = str(text or "").strip()
    if raw.upper().startswith("RRULE:"):
        raw = raw[6:]
    rule = {"freq": None, "interval": 1, "byday": [], "bymonthday": [], "bymonth": [], "bysetpos": [],
            "count": None, "until": None, "wkst": 0}  # fmt: skip
    if not raw:
        raise _bad("The repeat rule is empty.")
    for part in raw.split(";"):
        if not part:
            continue
        if "=" not in part:
            raise _bad(f"{part!r} in the repeat rule should look like KEY=VALUE.")
        key, value = (x.strip().upper() for x in part.split("=", 1))
        if key == "FREQ":
            if value not in FREQS:
                raise _bad(f"FREQ={value} isn't supported.", hint="Use DAILY, WEEKLY, MONTHLY or YEARLY.")
            rule["freq"] = value
        elif key == "INTERVAL":
            rule["interval"] = _ints(value, 1, 999, "INTERVAL")[0]
        elif key == "BYDAY":
            days = []
            for item in value.split(","):
                match = re.fullmatch(r"([+-]?\d{1,2})?(MO|TU|WE|TH|FR|SA|SU)", item)
                if not match:
                    raise _bad(f"BYDAY={value} isn't valid.")
                nth = int(match.group(1)) if match.group(1) else None
                if nth is not None and (nth == 0 or abs(nth) > 53):
                    raise _bad(f"BYDAY={value} has an ordinal out of range.")
                days.append((nth, DAY_CODES.index(match.group(2))))
            rule["byday"] = days
        elif key == "BYMONTHDAY":
            rule["bymonthday"] = _ints(value, -31, 31, "BYMONTHDAY")
        elif key == "BYMONTH":
            rule["bymonth"] = _ints(value, 1, 12, "BYMONTH")
        elif key == "BYSETPOS":
            rule["bysetpos"] = _ints(value, -366, 366, "BYSETPOS")
        elif key == "COUNT":
            rule["count"] = _ints(value, 1, 9999, "COUNT")[0]
        elif key == "UNTIL":
            match = re.fullmatch(r"(\d{4})(\d{2})(\d{2})(T\d{6}Z?)?", value)
            if not match:
                raise _bad(f"UNTIL={value} isn't a date.", hint="Use YYYYMMDD, e.g. UNTIL=20261231.")
            try:
                rule["until"] = _dt.date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            except ValueError as exc:
                raise _bad(f"UNTIL={value} isn't a real date.") from exc
        elif key == "WKST":
            if value not in DAY_CODES:
                raise _bad(f"WKST={value} isn't a weekday code.")
            rule["wkst"] = DAY_CODES.index(value)
        else:
            raise ToolError(
                f"The repeat rule uses {key}, which Fridge Door doesn't support.",
                hint="Supported: FREQ, INTERVAL, BYDAY, BYMONTHDAY, BYMONTH, BYSETPOS, COUNT, UNTIL, WKST.",
                code="unsupported_repeat",
            )
    if rule["freq"] is None:
        raise _bad("The repeat rule has no FREQ.")
    if rule["count"] and rule["until"]:
        raise _bad("A repeat rule can end on a date or after a number of times, not both.")
    if rule["freq"] in ("DAILY", "WEEKLY") and any(n is not None for n, _ in rule["byday"]):
        raise _bad("Numbered weekdays (like 2TU) only work with monthly or yearly repeats.")
    if rule["bysetpos"] and rule["freq"] == "DAILY":
        raise _bad("BYSETPOS doesn't work with daily repeats.")
    return rule


def to_text(rule: dict) -> str:
    """The canonical RRULE text for a parsed rule (stable, so equal rules compare equal)."""
    parts = [f"FREQ={rule['freq']}"]
    if rule.get("interval", 1) != 1:
        parts.append(f"INTERVAL={rule['interval']}")
    if rule.get("bymonth"):
        parts.append("BYMONTH=" + ",".join(str(m) for m in rule["bymonth"]))
    if rule.get("bymonthday"):
        parts.append("BYMONTHDAY=" + ",".join(str(d) for d in rule["bymonthday"]))
    if rule.get("byday"):
        days = sorted(rule["byday"], key=lambda item: (item[1], item[0] or 0))
        parts.append("BYDAY=" + ",".join(f"{n if n else ''}{DAY_CODES[d]}" for n, d in days))
    if rule.get("bysetpos"):
        parts.append("BYSETPOS=" + ",".join(str(p) for p in rule["bysetpos"]))
    if rule.get("wkst", 0) != 0:
        parts.append(f"WKST={DAY_CODES[rule['wkst']]}")
    if rule.get("count"):
        parts.append(f"COUNT={rule['count']}")
    if rule.get("until"):
        parts.append("UNTIL=" + rule["until"].strftime("%Y%m%d"))
    return ";".join(parts)


def normalize(text: str) -> str:
    return to_text(parse(text))


# --------------------------------------------------------------------------- expansion


def _month_days(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _weekdays_in(year: int, month: int, weekday: int) -> list:
    first = _dt.date(year, month, 1)
    day = first + _dt.timedelta(days=(weekday - first.weekday()) % 7)
    out = []
    while day.month == month:
        out.append(day)
        day += _dt.timedelta(days=7)
    return out


def _weekdays_in_year(year: int, weekday: int) -> list:
    day = _dt.date(year, 1, 1)
    day += _dt.timedelta(days=(weekday - day.weekday()) % 7)
    out = []
    while day.year == year:
        out.append(day)
        day += _dt.timedelta(days=7)
    return out


def _pick(items: list, nth: int | None) -> list:
    if nth is None:
        return items
    index = nth - 1 if nth > 0 else nth
    try:
        return [items[index]]
    except IndexError:
        return []


def _monthdays(year: int, month: int, wanted: list) -> list:
    size = _month_days(year, month)
    out = []
    for value in wanted:
        day = value if value > 0 else size + value + 1
        if 1 <= day <= size:
            out.append(_dt.date(year, month, day))
    return out


def _month_candidates(rule: dict, year: int, month: int, start: _dt.date) -> list:
    if rule["bymonthday"] and rule["byday"]:
        days = set(_monthdays(year, month, rule["bymonthday"]))
        return sorted(d for d in days if any(d.weekday() == wd for _, wd in rule["byday"]))
    if rule["bymonthday"]:
        return _monthdays(year, month, rule["bymonthday"])
    if rule["byday"]:
        out = []
        for nth, weekday in rule["byday"]:
            out += _pick(_weekdays_in(year, month, weekday), nth)
        return sorted(set(out))
    return _monthdays(year, month, [start.day])  # same day of the month; months without it are skipped


def _setpos(rule: dict, candidates: list) -> list:
    if not rule["bysetpos"]:
        return candidates
    out = []
    for pos in rule["bysetpos"]:
        out += _pick(candidates, pos)
    return sorted(set(out))


def _period_candidates(rule: dict, start: _dt.date, k: int) -> list:
    """Every date the rule produces in its k-th period (day, week, month or year) after start's period."""
    freq, step = rule["freq"], rule["interval"]
    if freq == "DAILY":
        day = start + _dt.timedelta(days=k * step)
        if rule["bymonth"] and day.month not in rule["bymonth"]:
            return []
        if rule["bymonthday"] and day not in _monthdays(day.year, day.month, rule["bymonthday"]):
            return []
        if rule["byday"] and day.weekday() not in [wd for _, wd in rule["byday"]]:
            return []
        return [day]
    if freq == "WEEKLY":
        week_start = start - _dt.timedelta(days=(start.weekday() - rule["wkst"]) % 7)
        week_start += _dt.timedelta(weeks=k * step)
        weekdays = [wd for _, wd in rule["byday"]] or [start.weekday()]
        days = sorted(week_start + _dt.timedelta(days=(wd - rule["wkst"]) % 7) for wd in set(weekdays))
        if rule["bymonth"]:
            days = [d for d in days if d.month in rule["bymonth"]]
        return _setpos(rule, days)
    if freq == "MONTHLY":
        index = start.month - 1 + k * step
        year, month = start.year + index // 12, index % 12 + 1
        if rule["bymonth"] and month not in rule["bymonth"]:
            return []
        return _setpos(rule, _month_candidates(rule, year, month, start))
    year = start.year + k * step  # YEARLY
    months = rule["bymonth"] or [start.month]
    days = []
    if rule["byday"] and not rule["bymonth"] and not rule["bymonthday"]:
        for nth, weekday in rule["byday"]:
            days += _pick(_weekdays_in_year(year, weekday), nth)
    else:
        for month in months:
            if not rule["bymonthday"] and not rule["byday"]:
                days += _monthdays(year, month, [start.day])
            else:
                days += _month_candidates(rule, year, month, start)
    return _setpos(rule, sorted(set(days)))


def iterate(rule: dict, start: _dt.date, include_start: bool = False):
    """Yield the rule's dates in order from start (start itself first when include_start, as calendars do)."""
    produced = 0
    if include_start:
        produced = 1
        yield start
        if rule["count"] and produced >= rule["count"]:
            return
    empty_run = 0
    for k in range(MAX_PERIODS):
        found = False
        for day in _period_candidates(rule, start, k):
            if day < start or (include_start and day == start):
                continue
            if rule["until"] and day > rule["until"]:
                return
            found = True
            produced += 1
            yield day
            if rule["count"] and produced >= rule["count"]:
                return
        empty_run = 0 if found else empty_run + 1
        if empty_run > 400 * (12 if rule["freq"] == "DAILY" else 1):
            return  # nothing for a very long time: the rule can never match again


def between(rule: dict, start: _dt.date, first: _dt.date, last: _dt.date, include_start: bool = False,
            skip=()) -> list:  # fmt: skip
    """The rule's dates from first to last (inclusive), leaving out any dates in skip."""
    skip = set(skip)
    out = []
    for day in iterate(rule, start, include_start):
        if day > last:
            break
        if day >= first and day not in skip:
            out.append(day)
    return out


def next_after(rule: dict, start: _dt.date, after: _dt.date, include_start: bool = False, skip=()):
    """The first date strictly after `after`, or None when the rule has ended."""
    skip = set(skip)
    for day in iterate(rule, start, include_start):
        if day > after and day not in skip:
            return day
    return None


def next_due(text: str | None, due: _dt.date | None, completed: _dt.date, occurrence: int = 1):
    """When a repeating task is done: the next due date after the current due day (so finishing Saturday's chore
    on Thursday gives next Saturday, not this one), but not before the completion day: catching up yesterday's
    daily chore today leaves today's still to do, and turns missed while it sat undone are skipped. Anchored on
    the due day (else the completion day). None for no rule, a broken rule, or a rule that has ended; never an
    error, so a bad rule can't block finishing a task. `occurrence` is this task's place in the series, for
    COUNT."""
    if not text:
        return None
    try:
        rule = parse(text)
    except ToolError:
        return None
    anchor = due or completed
    if rule["count"]:
        if rule["count"] - occurrence <= 0:
            return None
        rule = dict(rule, count=None)
    found = next_after(rule, anchor, due or completed)
    if found and found < completed:  # missed turns: the next one from today on
        found = next_after(rule, anchor, completed - _dt.timedelta(days=1))
    return found


# --------------------------------------------------------------------------- words


def _ordinal(n: int) -> str:
    if n == -1:
        return "last"
    if n < 0:
        return f"{_ordinal(-n)} last"
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _days_from_words(text: str) -> list:
    found = []
    for word in re.split(r"[\s,/&]+|\band\b", text):
        word = word.strip().rstrip("s") if len(word.strip()) > 3 else word.strip()
        if not word:
            continue
        for index, name in enumerate(_FULL_DAYS):
            if word in (name, name[:3], name[:2], name.rstrip("s")) or (len(word) >= 3 and name.startswith(word)):
                found.append(index)
                break
    return sorted(set(found))


def _monthday_rule(day: int) -> dict:
    """Day of the month; 29-31 fall back to the month's last day in shorter months (never skipped)."""
    if day <= 28:
        return {"bymonthday": [day]}
    return {"bymonthday": list(range(28, day + 1)), "bysetpos": [-1]}


def from_words(text: str, start: _dt.date, until: _dt.date | None = None, count: int | None = None) -> str:
    """Turn friendly words (or RRULE text) into a canonical RRULE, using start for the defaults."""
    raw = str(text or "").strip()
    if not raw:
        raise _bad("How often should it repeat?")
    if "FREQ=" in raw.upper():
        rule = parse(raw)
    else:
        rule = parse("FREQ=DAILY")
        t = fold(raw).replace("every other", "every 2").replace("each", "every")
        t = re.sub(r"\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b",
                   lambda m: str(_NUMBER_WORDS[m.group(1)]), t)  # fmt: skip
        t = re.sub(r"\b(?:a )?couple of\b", "2", t)
        t = re.sub(r"\bevery (?:2|second|2nd) fortnights?\b|\bevery fortnight\b", "every 2 weeks", t)
        t = re.sub(r"\bevery (second|2nd|third|3rd|fourth|4th|fifth|5th|sixth|6th) (day|week|month|year)s?\b",
                   lambda m: f"every {_ORDINAL_WORDS[m.group(1)]} {m.group(2)}s", t)  # "every second week"
        if re.search(r"\b(twice|thrice|times (a|per|each|every)|few|several|some)\b", t):
            raise _bad(f"{raw!r} doesn't say which days.",
                       hint='Ask which, then name them: "weekly on mon,thu", "monthly on the 1st and 15th" or '
                       '"every 3 days".')  # fmt: skip
        t = re.sub(r"\b(fortnightly|biweekly|bi-weekly)\b", "every 2 weeks", t)
        t = re.sub(r"\bquarterly\b", "every 3 months", t)
        t = re.sub(r"\b(annually|every year|yearly)\b", "yearly", t)
        interval = 1
        match = re.search(r"every (\d{1,3}) (day|week|month|year)s?", t)
        if match:
            interval = int(match.group(1))
            t = t.replace(match.group(0), f"every {match.group(2)}")
        else:
            weekday = re.search(r"every (\d{1,3}) ((?:mon|tue|wed|thu|fri|sat|sun)[a-z]*)", t)
            if weekday:  # "every other tuesday", "every 2 tuesdays": every N weeks on that day
                interval = int(weekday.group(1))
                t = t.replace(weekday.group(0), f"every week on {weekday.group(2)}")
        if not re.search(r"\bmonth", t):
            nth = re.search(r"every (first|1st|second|2nd|third|3rd|fourth|4th|fifth|5th|last) "
                            r"((?:mon|tue|wed|thu|fri|sat|sun)[a-z]*)", t)  # fmt: skip
            if nth and nth.group(1) in ("second", "2nd"):
                day = nth.group(2)
                raise _bad(f"{raw!r} could mean every 2 weeks or the 2nd {day} of each month.",
                           hint=f'Ask which, then say "every 2 weeks on {day}" or "monthly on the 2nd {day}".')
            if nth:  # "every first monday", "every third thursday": that day of each month
                t = f"monthly on the {nth.group(1)} {nth.group(2)}"
        days = _days_from_words(re.sub(r".*\bon\b", "", t)) if re.search(r"\bon\b", t) else []
        named_days = _days_from_words(t)
        if re.fullmatch(r"(every )?(day|daily)", t):
            rule = {"freq": "DAILY"}
        elif t in ("weekdays", "every weekday", "on weekdays", "weekday"):
            rule = {"freq": "WEEKLY", "byday": [(None, d) for d in range(5)]}
        elif t in ("weekends", "every weekend", "on weekends", "weekend"):
            rule = {"freq": "WEEKLY", "byday": [(None, 5), (None, 6)]}
        elif re.search(r"\bmonth(ly|s)?\b", t):
            nth_match = re.search(
                r"(first|1st|second last|second-last|second|2nd|third|3rd|fourth|4th|fifth|5th|last)\s+"
                r"(mon|tue|wed|thu|fri|sat|sun)[a-z]*",
                t,
            )
            day_match = re.search(r"\b(\d{1,2})(st|nd|rd|th)?\b", t)
            days_of_month = sorted({int(d) for d in re.findall(r"\b(\d{1,2})(?:st|nd|rd|th)?\b", t)
                                    if 1 <= int(d) <= 31})  # fmt: skip
            if not nth_match and len(days_of_month) > 1:
                if days_of_month[-1] > 28:
                    raise _bad("Days after the 28th don't come every month.",
                               hint='Pick days up to the 28th, or say "monthly on the last day".')  # fmt: skip
                rule = {"freq": "MONTHLY", "bymonthday": days_of_month}
            elif nth_match:
                nth = _ORDINAL_WORDS[nth_match.group(1)]
                rule = {"freq": "MONTHLY", "byday": [(nth, _days_from_words(nth_match.group(2))[0])]}
            elif "last day" in t or "end of the month" in t:
                rule = {"freq": "MONTHLY", "bymonthday": [-1]}
            elif day_match and 1 <= int(day_match.group(1)) <= 31:
                rule = dict({"freq": "MONTHLY"}, **_monthday_rule(int(day_match.group(1))))
            else:
                rule = dict({"freq": "MONTHLY"}, **_monthday_rule(start.day))
        elif re.search(r"\byear(ly|s)?\b", t):
            if start.month == 2 and start.day == 29:
                rule = {"freq": "YEARLY", "bymonth": [2], "bymonthday": [-1]}  # Feb 28 in other years
            else:
                rule = {"freq": "YEARLY", "bymonth": [start.month], "bymonthday": [start.day]}
        elif re.search(r"\bweek(ly|s)?\b", t) or named_days:
            chosen = days or named_days or [start.weekday()]
            rule = {"freq": "WEEKLY", "byday": [(None, d) for d in chosen]}
        elif re.search(r"\bdays?\b", t):
            rule = {"freq": "DAILY"}
        else:
            raise _bad(f"I can't read the repeat {raw!r}.")
        rule = dict({"interval": interval, "byday": [], "bymonthday": [], "bymonth": [], "bysetpos": [],
                     "count": None, "until": None, "wkst": 0}, **rule)  # fmt: skip
        rule["interval"] = interval
    if until:
        rule["until"], rule["count"] = until, None
    if count:
        rule["count"], rule["until"] = int(count), None
    return normalize(to_text(rule))


def reanchor(text: str, start: _dt.date) -> str:
    """The same kind of repeat (every N days, weeks, months or years, with its end) starting from a new first date:
    "monthly on the 26th" moved to 28 Nov becomes "monthly on the 28th"."""
    rule = parse(text)
    freq = rule["freq"]
    if freq == "WEEKLY":
        days = [d for _, d in rule["byday"]]
        words = "weekly" if start.weekday() not in days else None  # still on one of its days: keep the days
    elif freq == "MONTHLY":
        if rule["byday"]:
            nth = -1 if (start + _dt.timedelta(days=7)).month != start.month else (start.day - 1) // 7 + 1
            order = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", -1: "last"}[nth]
            words = f"monthly on the {order} {start.strftime('%a').lower()}"
        else:
            words = "monthly"
    else:
        words = {"DAILY": "daily", "YEARLY": "yearly"}[freq]
    fresh = parse(from_words(words, start)) if words else dict(rule)
    fresh["interval"], fresh["until"], fresh["count"] = rule["interval"], rule["until"], rule["count"]
    return normalize(to_text(fresh))


def describe(text: str | None) -> str:
    """Plain English for a rule: "every 2 weeks on Sat", "monthly on the last Fri", "every year on 14 Mar"."""
    if not text:
        return "doesn't repeat"
    try:
        rule = parse(text)
    except ToolError:
        return "custom schedule"
    n, freq = rule["interval"], rule["freq"]
    days = [d for _, d in rule["byday"]]
    if freq == "DAILY":
        out = "every day" if n == 1 else f"every {n} days"
    elif freq == "WEEKLY":
        if sorted(days) == [0, 1, 2, 3, 4] and n == 1:
            out = "every weekday"
        elif sorted(days) == [5, 6] and n == 1:
            out = "every weekend"
        else:
            names = ", ".join(DAY_NAMES[d] for d in sorted(days)) if days else ""
            out = ("weekly" if n == 1 else f"every {n} weeks") + (f" on {names}" if names else "")
    elif freq == "MONTHLY":
        base = "monthly" if n == 1 else f"every {n} months"
        if rule["byday"]:
            parts = [f"{_ordinal(nth)} {DAY_NAMES[d]}" if nth else DAY_NAMES[d] for nth, d in rule["byday"]]
            out = f"{base} on the {', '.join(parts)}"
        elif rule["bymonthday"] == [-1]:
            out = f"{base} on the last day"
        elif rule["bysetpos"] == [-1] and len(rule["bymonthday"]) > 1 and rule["bymonthday"][0] == 28:
            out = f"{base} on the {_ordinal(max(rule['bymonthday']))} (or the last day of shorter months)"
        elif rule["bymonthday"]:
            out = f"{base} on the " + ", ".join(_ordinal(d) for d in rule["bymonthday"])
        else:
            out = base
    else:
        base = "every year" if n == 1 else f"every {n} years"
        if rule["bymonth"] and rule["bymonthday"]:
            if rule["bymonth"] == [2] and rule["bymonthday"] == [-1]:
                out = f"{base} on the last day of Feb"
            else:
                out = f"{base} on " + ", ".join(
                    f"{d} {MONTH_NAMES[m - 1]}" for m in rule["bymonth"] for d in rule["bymonthday"]
                )
        elif rule["bymonth"] and rule["byday"]:
            parts = [f"{_ordinal(nth)} {DAY_NAMES[d]}" if nth else DAY_NAMES[d] for nth, d in rule["byday"]]
            out = f"{base} on the {', '.join(parts)} of " + ", ".join(MONTH_NAMES[m - 1] for m in rule["bymonth"])
        else:
            out = base
    if rule["until"]:
        out += f" until {rule['until'].day} {MONTH_NAMES[rule['until'].month - 1]} {rule['until'].year}"
    if rule["count"]:
        out += f", {rule['count']} times"
    return out
