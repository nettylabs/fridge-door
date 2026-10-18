"""Where records live: plain JSON files in one data folder, one sub-folder per household.

    <home>/hub.json                       households, the active one, who's talking in direct chats, chat -> household
    <home>/households/<id>/household.json settings, members and their access, linked chats, id counters
    <home>/households/<id>/todos.json     to-do lists and tasks
    <home>/households/<id>/shopping.json  shopping and grocery lists, items, aisles, purchase memory, pantry
    <home>/households/<id>/calendar.json, recipes.json, mealplan.json, notes.json, budget.json, notices.json
    <home>/households/<id>/activity.jsonl audit trail (prunes itself after the retention period)
    <home>/households/<id>/output/        printables (PDF and HTML)
    <home>/exports/                       zip exports made with `fridge export`

Every change runs inside Household.transaction(): one lock, a fresh read, and an atomic save of each changed file
at the end. An error (or --dry-run) saves nothing.
"""

from __future__ import annotations

import contextlib
import copy
import datetime as _dt
import json
import shutil
import zipfile
from pathlib import Path

from .util import (WEEKDAYS, ToolError, day_text, file_lock, fold, now, now_stamp, parse_date, parse_stamp,
                   read_json, today, write_json)

SCHEMA = 1

# Module files and their empty shape.
MODULE_FILES = {
    "todos": {"lists": [], "tasks": []},
    "shopping": {"lists": [], "items": [], "history": {}, "overrides": {}, "pantry": {}},
    "calendar": {"events": []},
    "recipes": {"recipes": []},
    "mealplan": {"plan": {}, "weeks": {}},
    "notes": {"notes": []},
    "budget": {"categories": [], "expenses": [], "bills": [], "goals": []},
    "notices": {"notices": [], "sent": {}},
}

# Readable ids: M1, L2, T14...
ID_PREFIX = {
    "member": "M",
    "list": "L",
    "task": "T",
    "item": "I",
    "aisle": "A",
    "event": "E",
    "recipe": "R",
    "note": "N",
    "category": "C",
    "expense": "X",
    "bill": "B",
    "goal": "G",
    "notice": "Q",
    "meal": "P",
}

DEFAULT_RETENTION_DAYS = 90


class Hub:
    """The data folder: which households exist, which one is active, and which chat belongs to which household."""

    def __init__(self, home):
        self.home = Path(home).expanduser().resolve()
        self.path = self.home / "hub.json"
        self.data = read_json(self.path)

    def exists(self) -> bool:
        return bool(self.data and self.data.get("households"))

    def require(self) -> None:
        if not self.exists():
            raise ToolError(
                f"No Fridge Door household in {self.home} yet.",
                hint='Set one up: fridge setup --name "Our home" --members "Alex, Sam" --country GB '
                "(or try the demo: fridge --home /tmp/fridge-demo demo).",
                code="not_initialized",
            )

    @contextlib.contextmanager
    def transaction(self):
        """Lock hub.json, re-read it, and save it at the end (not on an error)."""
        with file_lock(self.home / ".hub.lock"):
            self.data = read_json(self.path) or {
                "schema": SCHEMA,
                "households": [],
                "active": None,
                "speakers": {},
                "chats": {},
                "next_household": 1,
            }
            yield self.data
            write_json(self.path, self.data)

    # ------------------------------------------------------------------ households

    def households(self) -> list:
        return list((self.data or {}).get("households", []))

    def household(self, query=None) -> "Household":
        """A household by id or name, else the active one."""
        self.require()
        entries = self.households()
        if query:
            q = fold(query)
            for entry in entries:
                if fold(entry["id"]) == q or fold(entry["name"]) == q:
                    return Household(self, entry)
            matches = [e for e in entries if fold(e["name"]).startswith(q)]
            if len(matches) == 1:
                return Household(self, matches[0])
            raise ToolError(
                f"No household called {query!r}." if not matches else f"{query!r} matches more than one household.",
                hint="See them with: fridge household list",
                code="not_found" if not matches else "ambiguous",
            )
        active = self.data.get("active")
        for entry in entries:
            if entry["id"] == active:
                return Household(self, entry)
        return Household(self, entries[0])

    def speaker(self, household_id: str) -> str | None:
        return (self.data or {}).get("speakers", {}).get(household_id)

    def chat_household(self, chat_id: str) -> str | None:
        return (self.data or {}).get("chats", {}).get(chat_id)


class Household:
    """One household's folder. Read with .meta() and .data(name); change things inside .transaction()."""

    def __init__(self, hub: Hub, entry: dict):
        self.hub = hub
        self.id = entry["id"]
        self.path = hub.home / "households" / entry["folder"]
        self._cache: dict = {}
        self._dirty: set = set()
        self._log: list = []
        self._in_tx = False
        self.dropped_chats: list = []  # direct chats deleted during this command, for hub.json clean-up

    # ------------------------------------------------------------------ reading

    def meta(self) -> dict:
        if "household" not in self._cache:
            data = read_json(self.path / "household.json")
            if data is None:
                raise ToolError(
                    f"The household folder {self.path} is missing household.json.",
                    hint="Restore it from an export, or remove the household and set it up again.",
                    code="bad_file",
                )
            self._cache["household"] = data
        return self._cache["household"]

    def data(self, name: str) -> dict:
        if name not in MODULE_FILES:
            raise KeyError(name)
        if name not in self._cache:
            data = read_json(self.path / f"{name}.json") or {}
            for key, empty in MODULE_FILES[name].items():
                data.setdefault(key, copy.deepcopy(empty))
            self._cache[name] = data
        return self._cache[name]

    def fresh(self, name: str) -> dict:
        """Re-read a file from disk (after a command has saved it)."""
        self._cache.pop(name, None)
        return self.meta() if name == "household" else self.data(name)

    @property
    def name(self) -> str:
        return self.meta()["name"]

    @property
    def settings(self) -> dict:
        return self.meta()["settings"]

    @property
    def members(self) -> list:
        return self.meta()["members"]

    def member(self, member_id: str) -> dict | None:
        for member in self.members:
            if member["id"] == member_id:
                return member
        return None

    def member_name(self, member_id: str | None) -> str | None:
        if not member_id:
            return None
        member = self.member(member_id)
        return member["name"] if member else "Former member"

    def tz(self) -> str:
        return self.settings.get("timezone") or "UTC"

    def today(self) -> _dt.date:
        return today(self.tz())

    def week_start(self) -> int:
        """The first day of the household's week as a weekday number (Monday = 0)."""
        start = str(self.settings.get("week_start", "monday")).lower()
        return WEEKDAYS.index(start) if start in WEEKDAYS else 0

    def date(self, value, prefer: str = "future") -> _dt.date:
        """A date the person typed, read with the household's week start and date order (see util.parse_date)."""
        return parse_date(value, self.today(), week_start=self.week_start(),
                          date_format=self.settings.get("date_format"), prefer=prefer)  # fmt: skip

    def day(self, day: _dt.date, weekday: bool = True) -> str:
        """A date written the household's way ("Mon 26 Oct", "Mon Oct 26"), with the year only if it isn't this one."""
        return day_text(day, self.settings, self.today(), weekday=weekday)

    def now(self) -> _dt.datetime:
        return now(self.tz())

    # ------------------------------------------------------------------ writing

    @contextlib.contextmanager
    def transaction(self, dry_run: bool = False):
        """Lock the household, start from a fresh read, and save every changed file at the end.

        Nothing is saved when the block raises, or when dry_run is set (the caller reports what would happen).
        """
        if self._in_tx:  # nested: the outer transaction saves
            yield self
            return
        with file_lock(self.path / ".lock"):
            self._cache.clear()
            self._dirty.clear()
            self._log.clear()
            self._in_tx = True
            try:
                yield self
                if not dry_run:
                    for name in sorted(self._dirty):
                        filename = "household.json" if name == "household" else f"{name}.json"
                        write_json(self.path / filename, self._cache[name])
                    self._flush_log()
            finally:
                self._in_tx = False
                self._dirty.clear()
                self._log.clear()
                if dry_run:
                    self._cache.clear()  # forget the unsaved changes

    def touch(self, name: str = "household") -> None:
        """Mark a file as changed, so the transaction saves it."""
        if not self._in_tx:
            raise RuntimeError("touch() outside a transaction")  # a programming error, not a user one
        if name == "household":
            self.meta()
        else:
            self.data(name)
        self._dirty.add(name)

    def next_id(self, kind: str) -> str:
        meta = self.meta()
        counters = meta.setdefault("counters", {})
        number = int(counters.get(kind, 1))
        counters[kind] = number + 1
        self.touch("household")
        return f"{ID_PREFIX[kind]}{number}"

    def log(self, action: str, actor: str | None = None, **details) -> None:
        """Record what happened (member ids only, never names, so erasing a member leaves no name behind)."""
        entry = {"ts": now_stamp(), "action": action}
        if actor:
            entry["by"] = actor
        entry.update({k: v for k, v in details.items() if v is not None})
        self._log.append(entry)

    def _flush_log(self) -> None:
        if not self._log:
            return
        path = self.path / "activity.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            for entry in self._log:
                fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        self.prune_log()

    def prune_log(self) -> int:
        """Drop activity entries older than the retention period. Returns how many were dropped."""
        path = self.path / "activity.jsonl"
        if not path.is_file():
            return 0
        days = int(self.settings.get("retention_days") or DEFAULT_RETENTION_DAYS)
        cutoff = now("UTC") - _dt.timedelta(days=days)
        with open(path, encoding="utf-8") as fh:
            first = fh.readline()
        try:
            if not first or parse_stamp(json.loads(first)["ts"]) >= cutoff:
                return 0  # the oldest entry is still inside the window: nothing to prune
        except (ValueError, KeyError):
            pass
        kept, dropped = [], 0
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    if parse_stamp(json.loads(line)["ts"]) < cutoff:
                        dropped += 1
                        continue
                except (ValueError, KeyError):
                    pass
                kept.append(line)
        tmp = path.with_suffix(".tmp")
        tmp.write_text("".join(kept), encoding="utf-8")
        tmp.replace(path)
        return dropped

    def activity(self, limit: int = 50) -> list:
        path = self.path / "activity.jsonl"
        if not path.is_file():
            return []
        lines = path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines[-limit:] if line.strip()]

    # ------------------------------------------------------------------ files

    def output_dir(self) -> Path:
        folder = self.path / "output"
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def export_zip(self, filters: dict | None = None) -> Path:
        """Zip the household's folder into <home>/exports/ (printables and the lock file left out). filters maps a
        file name to a function that returns the data to write for it (to leave out other people's private
        things)."""
        folder = self.hub.home / "exports"
        folder.mkdir(parents=True, exist_ok=True)
        stamp = now(self.tz()).strftime("%Y%m%d-%H%M%S")
        target = folder / f"{self.id}-{stamp}.zip"
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(self.path.rglob("*")):
                rel = path.relative_to(self.path)
                if path.is_dir() or rel.parts[0] == "output" or path.name.startswith("."):
                    continue
                arcname = str(Path(self.id) / rel)
                if filters and len(rel.parts) == 1 and rel.name in filters:
                    data = read_json(path) or {}
                    zf.writestr(arcname, json.dumps(filters[rel.name](data), indent=2, ensure_ascii=False,
                                                    default=str) + "\n")  # fmt: skip
                else:
                    zf.write(path, arcname=arcname)
        return target


def create_household(hub: Hub, name: str, settings: dict, members: list, chats: dict | None = None) -> Household:
    """Write a new household folder and register it in hub.json (which the caller holds in a transaction)."""
    data = hub.data
    number = int(data.get("next_household", 1))
    data["next_household"] = number + 1
    hid = f"H{number}"
    entry = {"id": hid, "name": name, "folder": hid}
    folder = hub.home / "households" / hid
    if folder.exists():
        raise ToolError(f"{folder} already exists.", hint="Move it aside and try again.", code="exists")
    meta = {
        "schema": SCHEMA,
        "id": hid,
        "name": name,
        "created_at": now_stamp(),
        "settings": settings,
        "members": members,
        "chats": chats or {},
        "counters": {"member": len(members) + 1},
    }
    folder.mkdir(parents=True)
    write_json(folder / "household.json", meta)
    data["households"].append(entry)
    return Household(hub, entry)


def remove_household_folder(hub: Hub, household: Household) -> None:
    shutil.rmtree(household.path, ignore_errors=False)
