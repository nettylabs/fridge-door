"""Shared helpers: errors the agent can act on, JSON output, dates and time zones, names, and safe file writes."""

from __future__ import annotations

import contextlib
import datetime as _dt
import json
import os
import re
import sys
import tempfile
import time
import unicodedata
from decimal import Decimal
from pathlib import Path

ENV_HOME = "FRIDGE_HOME"
APP_DIR = "fridge-door"


class ToolError(Exception):
    """An error the user or agent can act on. `hint` says what to do next."""

    def __init__(
        self,
        message: str,
        hint: str | None = None,
        code: str = "error",
        ask_owner: str | None = None,
        **extra,
    ):
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.code = code
        self.ask_owner = ask_owner  # a question only the owner can answer: the agent asks it, never answers it
        self.extra = extra  # more fields for the JSON reply, e.g. candidates for an ambiguous name


def emit(payload: dict, code: int = 0) -> None:
    sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False, default=_json_default) + "\n")
    sys.exit(code)


def _json_default(value):
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (_dt.date, _dt.datetime, _dt.time)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, set):
        return sorted(value)
    return str(value)


def default_home() -> Path:
    """$FRIDGE_HOME, else /workspace/fridge-door when /workspace exists (agent cloud computers), else ~/fridge-door."""
    env = os.environ.get(ENV_HOME)
    if env:
        return Path(env).expanduser()
    if Path("/workspace").is_dir():
        return Path("/workspace") / APP_DIR
    return Path.home() / APP_DIR


# --------------------------------------------------------------------------- files


def read_json(path: Path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh, parse_float=Decimal)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError as exc:
        raise ToolError(
            f"{path.name} is damaged: {exc}",
            hint="Restore it from an export, or move it aside to start over.",
            code="bad_file",
        ) from exc


def write_json(path: Path, data) -> None:
    """Write atomically, so a crash mid-write never leaves a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False, default=_json_default)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise


@contextlib.contextmanager
def file_lock(path: Path, timeout: float = 20.0, stale_after: float = 120.0):
    """A lock file, so a scheduled routine and a chat (or two shoppers) never write at the same moment."""
    start = time.time()
    path.parent.mkdir(parents=True, exist_ok=True)
    while True:
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            break
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(path) > stale_after:
                    os.unlink(path)
                    continue
            except FileNotFoundError:
                continue
            if time.time() - start > timeout:
                raise ToolError(
                    "The data folder is busy: another Fridge Door command is still running.",
                    hint=f"Wait a few seconds and try again. If nothing else is running, delete {path}.",
                    code="busy",
                ) from None
            time.sleep(0.05)
    try:
        yield
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(path)


def load_spec(value: str):
    """A JSON spec from inline text, a file path, or "-" for stdin. Decimal numbers stay exact (Decimal)."""
    if value == "-":
        text = sys.stdin.read()
    elif value.lstrip().startswith(("{", "[")):
        text = value
    else:
        path = Path(value).expanduser()
        if not path.is_file():
            raise ToolError(
                f"No spec file at {value}.",
                hint="Pass the JSON inline, a file path, or - to read stdin.",
                code="bad_spec",
            )
        text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text, parse_float=Decimal)
    except json.JSONDecodeError as exc:
        raise ToolError(
            f"The spec isn't valid JSON: {exc}",
            hint="Check the quotes and commas; numbers need no quotes.",
            code="bad_spec",
        ) from exc


# --------------------------------------------------------------------------- time


NO_TZ_DATA_HINT = ("Install it once with: pip install tzdata (Python on Windows doesn't come with one; Macs and Linux "
                   "do). Without it, dates, reminders and quiet hours would be hours off, so nothing runs.")


def tz_database_ok() -> bool:
    """Whether this computer has a time zone database at all (Python on Windows has none without tzdata)."""
    try:
        from zoneinfo import ZoneInfo

        ZoneInfo("Europe/London")
        return True
    except Exception:
        return False


def no_tz_data() -> ToolError:
    return ToolError("This computer has no time zone list, so Fridge Door can't tell the household's time.",
                     hint=NO_TZ_DATA_HINT, code="no_tz_data")  # fmt: skip


def get_tz(name: str | None):
    """A tzinfo for an IANA name such as "Europe/London". On a computer with no time zone database it refuses
    (no_tz_data) rather than quietly running every household on UTC."""
    if not name or name.upper() == "UTC":
        return _dt.timezone.utc
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(name)
    except Exception:
        if not tz_database_ok():
            raise no_tz_data() from None
        return _dt.timezone.utc  # an unknown name: setup and settings never store one


def tz_known(name: str) -> bool:
    if not name:
        return False
    if name.upper() == "UTC":
        return True
    try:
        from zoneinfo import ZoneInfo

        ZoneInfo(name)
        return True
    except Exception:
        return False


def now(tz_name: str | None = None) -> _dt.datetime:
    """The current time in the household's time zone. FRIDGE_NOW (ISO date-time) overrides it, for tests and demos."""
    tz = get_tz(tz_name)
    override = os.environ.get("FRIDGE_NOW")
    if override:
        try:
            moment = _dt.datetime.fromisoformat(override.strip())
        except ValueError as exc:
            raise ToolError(f"FRIDGE_NOW={override!r} is not an ISO date and time.", code="bad_env") from exc
        if moment.tzinfo is None:
            return moment.replace(tzinfo=tz)
        return moment.astimezone(tz)
    return _dt.datetime.now(tz)


def today(tz_name: str | None = None) -> _dt.date:
    return now(tz_name).date()


_LOCAL_TZ = {"name": None}


def set_local_tz(name: str | None) -> None:
    """The time zone of the household a command runs in, so a FRIDGE_NOW without an offset means the same moment
    to now() and to now_stamp()."""
    _LOCAL_TZ["name"] = name


def now_stamp() -> str:
    """UTC time stamp for records and the activity log."""
    override = os.environ.get("FRIDGE_NOW")
    if override:
        return now(_LOCAL_TZ["name"] or "UTC").astimezone(_dt.timezone.utc).replace(microsecond=0).isoformat()
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def parse_stamp(text: str | None) -> _dt.datetime | None:
    if not text:
        return None
    moment = _dt.datetime.fromisoformat(text)
    return moment if moment.tzinfo else moment.replace(tzinfo=_dt.timezone.utc)


WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
MONTH_WORDS = {"jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4,
               "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9,
               "september": 9, "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12,
               "december": 12}  # fmt: skip
MONTH_ABBR = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
MONTH_NAMES = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
               "November", "December")  # fmt: skip
DAY_ABBR = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _day_month(text: str):
    """(day, month, year or None) from "3 nov", "3rd of november 2026", "nov 3" or "november 3rd, 2026"."""
    match = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?(?: of)? ([a-z]+)\.?,?(?: (\d{4}))?", text)
    if match and match.group(2) in MONTH_WORDS:
        return int(match.group(1)), MONTH_WORDS[match.group(2)], int(match.group(3)) if match.group(3) else None
    match = re.fullmatch(r"([a-z]+)\.? (\d{1,2})(?:st|nd|rd|th)?,?(?: (\d{4}))?", text)
    if match and match.group(1) in MONTH_WORDS:
        return int(match.group(2)), MONTH_WORDS[match.group(1)], int(match.group(3)) if match.group(3) else None
    return None


def _numeric_date(text: str, date_format: str | None):
    """(day, month, year or None) from 03/11/2026, 3/11/26 or 3.11, in the household's order (day or month first).
    Households that write YYYY-MM-DD use that, since 3/11 means different things in different countries."""
    match = re.fullmatch(r"(\d{1,2})[/.](\d{1,2})(?:[/.](\d{2}|\d{4}))?", text)
    if not match:
        return None
    order = str(date_format or "DD/MM/YYYY").upper()
    if order.startswith("YYYY"):
        raise ToolError(f"{text!r} could be read two ways.", hint="Use YYYY-MM-DD, e.g. 2026-11-03.", code="bad_date")
    first, second = int(match.group(1)), int(match.group(2))
    year = match.group(3)
    year = (int(year) + (2000 if len(year) == 2 else 0)) if year else None
    return (second, first, year) if order.startswith("MM") else (first, second, year)


def _pick_year(day: int, month: int, year, base: _dt.date, prefer: str) -> _dt.date:
    """The date for a day and month: in the given year, else the next one (prefer="future"), the last one
    ("past") or whichever is closer ("nearest")."""
    def make(y):
        try:
            return _dt.date(y, month, day)
        except ValueError:
            return None

    if year:
        found = make(year)
        if not found:
            raise ToolError(f"There's no {day}/{month} in {year}.", code="bad_date")
        return found
    options = [d for d in (make(y) for y in range(base.year - 4, base.year + 5)) if d]  # 29 Feb: every 4 years
    if not options:
        raise ToolError(f"There's no day {day} in month {month}.", code="bad_date")
    future = [d for d in options if d >= base]
    past = [d for d in options if d <= base]
    if prefer == "past" and past:
        return max(past)
    if prefer == "nearest" and past and future:
        return min(max(past), min(future), key=lambda d: abs((d - base).days))
    return min(future) if future else max(past)


def parse_date(value, base: _dt.date, week_start: int = 0, date_format: str | None = None,
               prefer: str = "future") -> _dt.date:  # fmt: skip
    """Parse YYYY-MM-DD, today, tomorrow, yesterday, +N / -N days, a weekday name, "next <weekday>" (the one in
    next week), "last <weekday>", "this weekend", "next week" (its first day), "3 Nov" or "Nov 3rd" (with or
    without a year), or 03/11/2026 in the household's date order.

    prefer="future" (the default): a weekday name is the coming one, today included, and a day and month
    without a year is the next one. prefer="past" (for things that happened, like spending): the last one, today
    included. prefer="nearest": a day and month is whichever is closer."""
    if isinstance(value, _dt.date):
        return value
    text = re.sub(r"\s+", " ", str(value or "").strip().lower())
    if text in ("", "today", "now", "tonight"):
        return base
    if text == "yesterday":
        return base - _dt.timedelta(days=1)
    if text == "tomorrow":
        return base + _dt.timedelta(days=1)
    match = re.fullmatch(r"([+-]\d+)\s*d(?:ays?)?|([+-]\d+)", text)
    if match:
        return base + _dt.timedelta(days=int(match.group(1) or match.group(2)))
    match = re.fullmatch(r"([+-]?\d+)\s*w(?:eeks?)?", text)
    if match:
        return base + _dt.timedelta(weeks=int(match.group(1)))
    if text in ("this weekend", "weekend"):
        # The coming Saturday; on Sunday it means today (ported from the due-date presets).
        return base if base.weekday() == 6 else base + _dt.timedelta(days=(5 - base.weekday()) % 7)
    if text == "next week":
        return base + _dt.timedelta(days=((week_start - base.weekday()) % 7) or 7)
    nxt, last = text.startswith("next "), text.startswith("last ")
    name = text[5:] if nxt or last or text.startswith("this ") else text
    for index, day_name in enumerate(WEEKDAYS):
        if name in (day_name, day_name[:3], day_name + "s"):
            if nxt:  # "next friday" = the Friday of next week (weeks start on the household's week_start)
                next_week = base + _dt.timedelta(days=((week_start - base.weekday()) % 7) or 7)
                return next_week + _dt.timedelta(days=(index - week_start) % 7)
            if last:  # "last monday" = the most recent Monday before today
                return base - _dt.timedelta(days=((base.weekday() - index) % 7) or 7)
            if prefer == "past":  # the most recent one, today included
                return base - _dt.timedelta(days=(base.weekday() - index) % 7)
            return base + _dt.timedelta(days=(index - base.weekday()) % 7)  # the coming one, today included
    parts = _day_month(text.replace(",", ", ").replace("  ", " ").strip()) or _numeric_date(text, date_format)
    if parts:
        return _pick_year(*parts, base, prefer)
    try:
        return _dt.date.fromisoformat(text[:10].replace("/", "-"))
    except ValueError as exc:
        raise ToolError(
            f"{value!r} is not a date I can read.",
            hint="Use YYYY-MM-DD (e.g. 2026-10-24), a day and month (24 Oct), today, tomorrow, a weekday name, "
            "+3 for three days from now, this weekend or next week.",
            code="bad_date",
        ) from exc


def day_text(day: _dt.date, settings: dict | None = None, today: _dt.date | None = None, weekday: bool = True,
             year: bool | None = None) -> str:  # fmt: skip
    """A date as people in the household write it: "Mon 26 Oct", "Mon Oct 26" or "Mon 2026-10-26". The year is
    added when it isn't the current one (or with year=True)."""
    order = str((settings or {}).get("date_format", "DD/MM/YYYY")).upper()
    show_year = year if year is not None else bool(today and day.year != today.year)
    head = f"{DAY_ABBR[day.weekday()]} " if weekday else ""
    if order.startswith("YYYY"):
        return head + day.isoformat()
    if order.startswith("MM"):
        return f"{head}{MONTH_ABBR[day.month - 1]} {day.day}" + (f", {day.year}" if show_year else "")
    return f"{head}{day.day} {MONTH_ABBR[day.month - 1]}" + (f" {day.year}" if show_year else "")


def parse_time(value) -> _dt.time:
    """Parse 18:30, 6:30pm, 6pm, 0630, noon or midnight."""
    if isinstance(value, _dt.time):
        return value
    text = str(value or "").strip().lower().replace(" ", "").replace(".", "")
    if text in ("noon", "midday"):
        return _dt.time(12, 0)
    if text == "midnight":
        return _dt.time(0, 0)
    match = re.fullmatch(r"(\d{1,2})(?::?(\d{2}))?(am|pm|a|p)?", text)
    if match:
        hour, minute, half = int(match.group(1)), int(match.group(2) or 0), match.group(3)
        if half:
            if not 1 <= hour <= 12:
                hour = 99
            elif half.startswith("p") and hour != 12:
                hour += 12
            elif half.startswith("a") and hour == 12:
                hour = 0
        if hour <= 23 and minute <= 59:
            return _dt.time(hour, minute)
    raise ToolError(
        f"{value!r} is not a time I can read.", hint="Use 24-hour HH:MM (e.g. 18:30) or 6:30pm.", code="bad_time"
    )


def parse_hours_range(value: str):
    """Parse "21:00-07:00" (quiet hours may cross midnight) into two HH:MM strings."""
    parts = re.split(r"\s*(?:-|–|to)\s*", str(value or "").strip())
    if len(parts) != 2:
        raise ToolError(
            f"{value!r} is not a time range.", hint='Use two times, e.g. "21:00-07:00".', code="bad_time"
        )
    start, end = (parse_time(p) for p in parts)
    if start == end:
        raise ToolError("The start and end times are the same.", hint='Use e.g. "21:00-07:00".', code="bad_time")
    return start.strftime("%H:%M"), end.strftime("%H:%M")


def in_window(moment: _dt.time, start: str, end: str) -> bool:
    """True when moment falls inside start-end, where the window may cross midnight (22:00-07:00)."""
    begin, finish = parse_time(start), parse_time(end)
    if begin < finish:
        return begin <= moment < finish
    return moment >= begin or moment < finish


def add_months(day: _dt.date, months: int) -> _dt.date:
    """Same day of the month, months later, clamped to the month's last day (Jan 31 + 1 month = Feb 28/29)."""
    index = day.month - 1 + months
    year, month = day.year + index // 12, index % 12 + 1
    last = (_dt.date(year + (month == 12), month % 12 + 1, 1) - _dt.timedelta(days=1)).day
    return _dt.date(year, month, min(day.day, last))


# --------------------------------------------------------------------------- names


def clean_text(value, field: str = "text", max_len: int = 200, required: bool = True) -> str | None:
    """Trim and collapse spaces; refuse empty (when required) or overlong text."""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        if required:
            raise ToolError(f"The {field} is empty.", hint=f"Give a {field}.", code="missing")
        return None
    if len(text) > max_len:
        raise ToolError(
            f"The {field} is {len(text)} characters long; the limit is {max_len}.",
            hint=f"Shorten the {field}.",
            code="too_long",
        )
    return text


def fold(text) -> str:
    """Matching key: lower case, accents removed, spaces collapsed ("Zoë " matches "zoe")."""
    decomposed = unicodedata.normalize("NFKD", str(text or ""))
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", stripped.casefold()).strip()


_SMALL_WORDS = {"the", "a", "an", "my", "our", "your", "his", "her", "their", "to", "for", "of", "on", "at", "and",
                "&", "please", "this", "that"}  # fmt: skip
_SPELLINGS = {"tyre": "tire", "tyres": "tires", "colour": "color", "grey": "gray", "mum": "mom", "practise": "practice",
              "centre": "center", "theatre": "theater", "litre": "liter", "metre": "meter", "favourite": "favorite",
              "neighbour": "neighbor", "organise": "organize", "jewellery": "jewelry", "aluminium": "aluminum",
              "programme": "program", "pyjamas": "pajamas", "yoghurt": "yogurt", "cheque": "check"}  # fmt: skip


def name_words(text) -> list:
    """The words of a name for matching, with British and American spellings made the same."""
    return [_SPELLINGS.get(word, word) for word in re.findall(r"[\w']+", fold(text))]


def match_one(items: list, query, what: str, *, key="name", hint: str | None = None, label=None) -> dict:
    """Find one record by id or name: exact id, then exact name, then a unique name prefix or word start, then a
    name holding every word they said (in any order, small words and the kind of thing aside: "power bill" finds
    "Power and gas", "fried rice" finds "Veggie fried rice").

    Raises not_found or ambiguous (with the candidates, described by label(item) if given) instead of guessing.
    """
    q = fold(query)
    if not q:
        raise ToolError(f"Which {what}?", hint=hint, code="missing")
    for item in items:
        if fold(item.get("id")) == q:
            return item
    exact = [item for item in items if fold(item.get(key)) == q]
    if len(exact) == 1:
        return exact[0]
    pool = exact or [
        item
        for item in items
        if fold(item.get(key)).startswith(q) or any(word.startswith(q) for word in fold(item.get(key)).split())
    ]
    if not pool:
        skip = _SMALL_WORDS | set(name_words(what))
        said = [word for word in name_words(q) if word not in skip] or name_words(q)
        pool = [item for item in items
                if all(any(word.startswith(part) for word in name_words(item.get(key))) for part in said)]  # fmt: skip
    if len(pool) == 1:
        return pool[0]
    if not pool:
        raise ToolError(f"No {what} called {query!r}.", hint=hint, code="not_found")
    raise ToolError(
        f"{query!r} matches more than one {what}.",
        hint="Use the id, or the full name.",
        code="ambiguous",
        candidates=[dict({"id": item.get("id"), key: item.get(key)}, **({"label": label(item)} if label else {}))
                    for item in pool[:10]],  # fmt: skip
    )


def servings_arg(value) -> int:
    """For --servings options: a whole number from 1 to 100."""
    import argparse

    try:
        number = int(str(value).strip())
    except ValueError:
        number = 0
    if not 1 <= number <= 100:
        raise argparse.ArgumentTypeError(f"servings must be a whole number from 1 to 100 (got {value!r})")
    return number


def plural(count: int, word: str, many: str | None = None) -> str:
    return f"{count} {word if count == 1 else (many or word + 's')}"


def and_list(words) -> str:
    """"Theo", "Theo and Lily", "Theo, Lily and Max"."""
    words = list(words)
    return " and ".join(words) if len(words) < 3 else ", ".join(words[:-1]) + " and " + words[-1]
