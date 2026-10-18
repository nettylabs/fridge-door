"""Built-in checks the agent runs with `fridge selftest`. Each one guards a rule that must never break."""

from __future__ import annotations

import datetime as _dt
import tempfile
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from . import access, members, money, regions
from .access import Viewer
from .util import ToolError, in_window, parse_date, read_json, write_json


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _raises(code: str, func, *args, **kwargs) -> None:
    try:
        func(*args, **kwargs)
    except ToolError as exc:
        _expect(exc.code == code, f"expected {code}, got {exc.code}")
        return
    raise AssertionError(f"expected the error {code}")


def _files_round_trip() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "records.json"
        write_json(path, {"amount": "12.50", "name": "Zoë"})
        _expect(read_json(path) == {"amount": "12.50", "name": "Zoë"}, "a saved file reads back differently")


def _splits_add_up() -> None:
    _expect(money.allocate("100.00", [1, 1, 1], "USD") == [Decimal("33.34"), Decimal("33.33"), Decimal("33.33")],
            "100.00 USD split three ways")  # fmt: skip
    _expect(money.allocate(1000, [1, 1, 1], "JPY") == [334, 333, 333], "1000 JPY split three ways")
    for cents in range(0, 101):
        total = Decimal(cents) / 100
        _expect(sum(money.allocate(total, [5, 3, 2], "EUR")) == total, f"a split of {total} doesn't add up")
    for text in ("1,500", "1.234,50"):
        _raises("bad_number", money.to_decimal, text)


def _presets_and_kid_lists() -> None:
    for role in access.ROLES:
        access.validate_access(access.preset(role))
    kid = {"id": "k", "name": "Kid", "role": "kid", "access": access.preset("kid")}
    _expect(access.can(kid, "grocery", "view") and not access.can(kid, "grocery", "edit"), "kid grocery = view")
    _expect(not access.can(kid, "shopping_lists", "view"), "a kid must not see shopping lists")
    _expect(not access.can(kid, "budget", "view"), "a kid must not see the budget")
    teen = {"id": "t", "name": "Teen", "role": "teen", "access": access.preset("teen")}
    _expect(not access.can(teen, "budget", "view") and access.can(teen, "calendar", "view"), "teen preset")
    _raises("bad_permissions", access.validate_access, {"calendar": "edit"})


def _group_chats_show_only_what_all_may_see() -> None:
    owner = {"id": "M1", "name": "Ana", "role": "owner", "access": access.preset("owner")}
    adult = {"id": "M2", "name": "Luis", "role": "adult", "access": dict(access.preset("adult"), budget="none")}
    direct = Viewer(owner)
    _expect(direct.sees("budget") and direct.sees_private_of("M1"), "the owner alone sees their own things")
    group = Viewer(owner, [owner, adult], group=True)
    _expect(not group.sees("budget"), "the budget must not show to a group with someone who can't see it")
    _expect(not group.sees_private_of("M1"), "private things must not show in a group")
    kids_there = Viewer(owner, [owner], group=True, minors_present=True)
    _expect(not kids_there.sees("budget") and not kids_there.sees("calendar"), "kid-level view when minors present")
    _expect(kids_there.sees("grocery") and not kids_there.sees("shopping_lists"), "kid-level lists")


def _only_adults_chat_and_owners_stay() -> None:
    from .context import refuse_minor

    _raises("minor_cannot_chat", refuse_minor, {"name": "Mia", "role": "kid"})
    _raises("minor_cannot_chat", refuse_minor, {"name": "Leo", "role": "teen"})
    roster = [{"id": "M1", "name": "Ana", "role": "owner"}, {"id": "M2", "name": "Luis", "role": "adult"}]
    _raises("last_owner", members.guard_last_owner, roster, roster[0], "adult")
    _raises("last_owner", members.guard_last_owner, roster, roster[0], None)
    _raises("minor_details", members.check_name, [], "Mia Garcia Lopez", "kid")
    _raises("minor_details", members.check_name, [], "Mia 9", "kid")
    people = members.parse_member_list("Ana, Luis, Sofia (9), Mateo (15)")
    _expect([r for _, r in people] == ["owner", "adult", "kid", "teen"], "ages pick roles and aren't stored")


def _transactions_save_all_or_nothing() -> None:
    from .onboarding import _create
    from .store import Hub

    with tempfile.TemporaryDirectory() as tmp:
        hub = Hub(tmp)
        args = SimpleNamespace(name="Test home", members="Ana, Luis", country="GB", currency=None, timezone=None,
                               week_start=None, date_format=None, time_format=None, units=None, paper=None,
                               dry_run=False)  # fmt: skip
        _create(hub, args)
        hh = Hub(tmp).household()
        with hh.transaction(dry_run=True):
            hh.meta()["name"] = "Changed"
            hh.touch("household")
        _expect(Hub(tmp).household().name == "Test home", "a dry run saved its change")
        try:
            with hh.transaction():
                hh.meta()["name"] = "Changed"
                hh.touch("household")
                raise ToolError("stop")
        except ToolError:
            pass
        _expect(Hub(tmp).household().name == "Test home", "a failed command saved part of its change")
        lists = Hub(tmp).household().data("todos")["lists"]
        _expect({lst["name"] for lst in lists} == {"Household Tasks", "My Tasks"}, "default to-do lists")


def _dates_and_quiet_hours() -> None:
    monday = _dt.date(2026, 10, 19)
    _expect(parse_date("friday", monday) == _dt.date(2026, 10, 23), "the coming Friday")
    _expect(parse_date("next friday", monday) == _dt.date(2026, 10, 30), "next week's Friday")
    _expect(parse_date("this weekend", monday) == _dt.date(2026, 10, 24), "this weekend = Saturday")
    _expect(parse_date("next week", monday, week_start=0) == _dt.date(2026, 10, 26), "next week (Monday start)")
    _expect(in_window(_dt.time(23, 30), "22:00", "07:00") and not in_window(_dt.time(12, 0), "22:00", "07:00"),
            "quiet hours across midnight")  # fmt: skip


def _country_defaults() -> None:
    for code in regions.all_codes():
        d = regions.defaults(code)
        _expect(len(d["currency"]) == 3 and d["week_start"] in regions.WEEK_STARTS, f"{code} defaults")
        _expect(d["date_format"] in regions.DATE_FORMATS and d["paper"] in regions.PAPERS, f"{code} formats")
    _expect(regions.country_code("UK") == "GB" and regions.country_code("canada") == "CA", "country names")
    _expect(regions.defaults("US")["units"] == "us" and regions.defaults("DE")["units"] == "metric", "units")


def _repeating_chores() -> None:
    from . import recur

    sat, thu = _dt.date(2026, 10, 24), _dt.date(2026, 10, 22)
    _expect(recur.next_due("FREQ=WEEKLY;BYDAY=SA", sat, thu) == _dt.date(2026, 10, 31), "early completion")
    _expect(recur.next_due("FREQ=DAILY", _dt.date(2026, 10, 15), _dt.date(2026, 10, 19)) == _dt.date(2026, 10, 19),
            "an overdue daily task leaves today's to do")  # fmt: skip
    _expect(recur.next_due("garbage", sat, thu) is None, "a broken rule must never block finishing a task")
    rule = recur.from_words("monthly on the 31st", _dt.date(2026, 1, 31))
    days = recur.between(recur.parse(rule), _dt.date(2026, 1, 31), _dt.date(2026, 2, 1), _dt.date(2026, 2, 28))
    _expect(days == [_dt.date(2026, 2, 28)], "the 31st falls back to the end of short months")


def _chores_rotate_once_with_stars() -> None:
    from . import todos
    from .onboarding import _create
    from .store import Hub

    with tempfile.TemporaryDirectory() as tmp:
        hub = Hub(tmp)
        _create(hub, SimpleNamespace(name="Check", members="Ana, Theo (kid), Lily (kid)", country="GB", currency=None,
                                     timezone=None, week_start=None, date_format=None, time_format=None, units=None,
                                     paper=None, dry_run=False))  # fmt: skip
        hh = Hub(tmp).household()
        with hh.transaction():
            data = hh.data("todos")
            lst = next(x for x in data["lists"] if x.get("default") == "household")
            rotation = {"members": ["M2", "M3"], "index": 0}
            task = todos.new_task(hh, lst, "Bins", "M1", assignee="M2", due=hh.today().isoformat(),
                                  rrule="FREQ=WEEKLY", rotation=rotation)  # fmt: skip
            data["tasks"].append(task)
            hh.touch("todos")
            task["completed_at"] = "done"
            todos._award(hh, task, hh.member("M2"))
            first = todos._materialize_next(hh, data, task, hh.today())
            again = todos._materialize_next(hh, data, task, hh.today())
            _expect(first is again, "the next occurrence must be created only once")
            _expect(first["assignee"] == "M3", "the rotation moves to the next person")
            _expect(hh.member("M2")["stars"] == 1, "the kid who did it gets a star")


def _aisles_and_suggestions() -> None:
    from . import shopping

    _expect(shopping.categorize("Eggs", {}) == "Dairy", "eggs are dairy")
    _expect(shopping.categorize("eggs", {"egg": "Fridge"}) == "Fridge", "the household's correction wins")
    now = _dt.datetime(2026, 10, 19, tzinfo=_dt.timezone.utc)
    history = {"bread": {"times": 3, "last_at": "2026-09-01T00:00:00+00:00"},
               "bagel": {"times": 2, "last_at": "2026-10-17T00:00:00+00:00"}}  # fmt: skip
    names = [s["name"] for s in shopping.suggest("b", history, now=now, seed={})]
    _expect(names == ["bagel", "bread"], "times bought x1.5 for the last 14 days, then prefix and name")
    _expect(shopping.parse_quick("milk x2") == ("milk", "2") and shopping.parse_quick("7up") == ("7up", None),
            "quick-add quantities")  # fmt: skip


def _ingredients_exact() -> None:
    from fractions import Fraction

    from . import ingredients as ing

    parsed = ing.parse("1½ cups flour, sifted")
    _expect((parsed["amount"], parsed["unit"], parsed["item"]) == (Fraction(3, 2), "cup", "flour"), "1½ cups flour")
    _expect(ing.parse("2-3 cloves garlic")["max"] == 3 and ing.parse("salt to taste")["to_taste"], "ranges, to taste")
    merged = {g["item"]: g["quantity"] for g in ing.merge([ing.parse(x) for x in ("2 cups flour", "1 cup flour",
                                                                                 "200 g flour")])}  # fmt: skip
    _expect(merged == {"flour": "3 cups + 200 g"}, "merge within a system, never metric with US")
    _expect(ing.describe(ing.scale(ing.parse("1/3 cup oil"), Fraction(3))) == "1 cup oil", "exact scaling")


def _recipe_import() -> None:
    from . import importer

    page = ('<script type="application/ld+json">{"@graph": [{"@type": "Recipe", "name": "Soup", "recipeYield": '
            '"4 servings", "totalTime": "PT1H5M", "recipeIngredient": ["1 l stock"], "recipeInstructions": '
            '[{"@type": "HowToStep", "text": "Simmer."}]}]}</script>')  # fmt: skip
    found = importer.from_html(page)
    _expect((found["title"], found["servings"], found["total_min"], found["steps"]) == ("Soup", 4, 65, ["Simmer."]),
            "schema.org Recipe import")  # fmt: skip


def _meal_list_follows_changes() -> None:
    from types import SimpleNamespace as NS

    from . import mealplan, recipes, shopping
    from .access import Viewer
    from .context import Ctx
    from .onboarding import _create
    from .store import Hub

    with tempfile.TemporaryDirectory() as tmp:
        hub = Hub(tmp)
        _create(hub, NS(name="Check", members="Ana", country="GB", currency=None, timezone=None, week_start=None,
                        date_format=None, time_format=None, units=None, paper=None, dry_run=False))  # fmt: skip
        hh = Hub(tmp).household()
        ctx = Ctx(hub, hh, Viewer(hh.member("M1")))
        with hh.transaction():
            data = hh.data("recipes")
            a = recipes.build_recipe(hh, {"title": "A", "servings": 2, "ingredients": ["1 onion", "200 g rice"]}, "M1")
            b = recipes.build_recipe(hh, {"title": "B", "servings": 2, "ingredients": ["1 onion", "2 eggs"]}, "M1")
            data["recipes"] += [a, b]
            day = mealplan.week_of(hh, hh.today())
            plan = hh.data("mealplan")["plan"]
            plan[day.isoformat()] = {"dinner": [{"id": "P1", "recipe": a["id"]}]}
            plan[(day + _dt.timedelta(days=1)).isoformat()] = {"dinner": [{"id": "P2", "recipe": b["id"]}]}
            shop = hh.data("shopping")
            lst = shop["lists"][0]
            mealplan.sync_week(hh, ctx, day, lst)
            qty = {i["name"]: i["qty"] for i in shop["items"]}
            _expect(qty == {"onion": "2", "rice": "200 g", "eggs": "2"}, f"week list merges meals: {qty}")
            rice = next(i for i in shop["items"] if i["name"] == "rice")
            rice["crossed_at"] = "bought"
            plan[day.isoformat()]["dinner"] = []  # meal A removed
            mealplan.sync_week(hh, ctx, day, lst)
            qty = {i["name"]: (i["qty"], bool(i.get("crossed_at"))) for i in shop["items"]}
            _expect(qty == {"onion": ("1", False), "rice": ("200 g", True), "eggs": ("2", False)},
                    f"only meal A's share comes off, and the crossed-off rice stays: {qty}")  # fmt: skip
            _expect(shopping.items_of(shop, lst["id"], crossed=True)[0]["name"] == "rice", "crossed item kept")


def _run(home, *args, now: str = "2026-10-19T08:00:00") -> dict:
    """Run a command in-process (the same code the agent calls) and return its JSON."""
    import contextlib
    import io
    import json
    import os

    from .cli import main

    out = io.StringIO()
    old = os.environ.get("FRIDGE_NOW")
    os.environ["FRIDGE_NOW"] = now
    try:
        with contextlib.redirect_stdout(out):
            try:
                main(["--home", str(home)] + [str(a) for a in args])
            except SystemExit:
                pass
    finally:
        if old is None:
            os.environ.pop("FRIDGE_NOW", None)
        else:
            os.environ["FRIDGE_NOW"] = old
    return json.loads(out.getvalue())


def _household_checks() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        _run(tmp, "setup", "--members", "Ana, Luis, Theo (kid)", "--country", "CA", "--timezone", "America/Toronto")
        # Money to the cent, and an ambiguous amount refused.
        _run(tmp, "budget", "category-defaults")
        for value in ("0.10", "0.10", "0.10", "254.20"):
            _run(tmp, "budget", "spend", value, "--category", "Groceries")
        month = _run(tmp, "budget", "month")
        _expect(Decimal(month["spent"]) == Decimal("254.50"), "budget totals to the cent")
        _expect(_run(tmp, "budget", "spend", "1,500", "--category", "Fun")["code"] == "bad_number", "1,500 refused")
        # Sensitive notes never show in a group chat.
        _run(tmp, "note", "add", "Wifi", "--body", "pw", "--sensitive")
        _run(tmp, "who", "chat", "pair", "--type", "group", "--minors", "no")
        _run(tmp, "who", "link", "pair", "--participant", "@ana", "--member", "Ana")
        group = _run(tmp, "note", "list", "--chat", "pair", "--from", "@ana")
        _expect(group["notes"] == [], "a sensitive note showed in a group chat")
        # Reminders wait for quiet hours and are never repeated.
        asked = _run(tmp, "who", "chat", "luis-dm", "--type", "direct", "--member", "Luis")
        _expect(bool(asked.get("ask_owner") and asked.get("confirm")), "an adult's chat was registered unasked")
        _expect(_run(tmp, "who", "chat", "luis-dm", "--type", "direct", "--member", "Luis", "--owner-confirmed",
                     "ok", "--confirm", asked["confirm"]).get("code") == "unclear_answer", "a vague ok counted as yes")
        _run(tmp, "who", "chat", "luis-dm", "--type", "direct", "--member", "Luis", "--owner-confirmed", "yes",
             "--confirm", asked["confirm"])
        _run(tmp, "member", "edit", "Luis", "--reminders", "on", "--chat", "luis-dm")  # reminders are his own yes
        _run(tmp, "member", "edit", "Luis", "--quiet-hours", "21:00-07:00", "--as", "Luis")
        _run(tmp, "cal", "add", "Flight", "--date", "2026-10-21", "--time", "09:00", "--for", "Luis", "--remind", "10h")
        held = _run(tmp, "remind", "due", now="2026-10-20T23:05:00")
        _expect(not held["send"] and held["held"], "a reminder went out during quiet hours")
        sent = _run(tmp, "remind", "due", now="2026-10-21T07:01:00")
        again = _run(tmp, "remind", "due", now="2026-10-21T07:02:00")
        _expect(len(sent["send"]) == 1 and not again["send"], "a reminder was sent twice")
        # Calendar files round-trip across time zones.
        _run(tmp, "cal", "add", "Swim", "--date", "tuesday", "--time", "17:30", "--repeat", "weekly")
        _run(tmp, "cal", "skip", "Swim", "--on", "2026-10-27")
        exported = _run(tmp, "ics", "export")
        with tempfile.TemporaryDirectory() as other:
            _run(other, "setup", "--members", "Bo", "--country", "GB")
            _run(other, "ics", "import", exported["file"])
            london = {(o["date"], o["time"]) for o in _run(other, "cal", "agenda", "--days", "14")["occurrences"]
                      if o["title"] == "Swim"}  # fmt: skip
            _expect(london == {("2026-10-20", "22:30")}, f"the .ics round trip moved the times: {london}")
        # Printables are real PDF files.
        week = _run(tmp, "print", "week")
        data = Path(week["files"][0]).read_bytes()
        _expect(data.startswith(b"%PDF-1.4") and data.rstrip().endswith(b"%%EOF"), "the fridge sheet isn't a PDF")


CHECKS = [
    ("files are saved atomically and read back exactly", _files_round_trip),
    ("money splits add up; ambiguous numbers are refused", _splits_add_up),
    ("role presets are valid; kids see grocery but not shopping lists or the budget", _presets_and_kid_lists),
    ("group chats show only what everyone present may see", _group_chats_show_only_what_all_may_see),
    ("only adults chat; kids keep a first name; the last owner stays", _only_adults_chat_and_owners_stay),
    ("changes save all or nothing; dry runs save nothing", _transactions_save_all_or_nothing),
    ("dates like 'next friday' and quiet hours across midnight", _dates_and_quiet_hours),
    ("every country's defaults are complete", _country_defaults),
    ("repeats: early completion, overdue tasks, broken rules, month ends", _repeating_chores),
    ("a repeating chore makes its next one once, rotates, and stars the kid", _chores_rotate_once_with_stars),
    ("aisles: corrections win; suggestions rank by recent buying", _aisles_and_suggestions),
    ("ingredients: fractions, ranges, merging within a system, exact scaling", _ingredients_exact),
    ("recipes import from schema.org data in a saved page", _recipe_import),
    ("the week's list changes by a meal's share only; crossed-off items stay", _meal_list_follows_changes),
    ("budget to the cent, sensitive notes, quiet hours, .ics time zones, printable PDFs", _household_checks),
]


def run_selftest() -> dict:
    results = []
    for name, check in CHECKS:
        try:
            check()
            results.append({"check": name, "ok": True})
        except Exception as exc:  # noqa: BLE001 - report every failure instead of stopping at the first
            results.append({"check": name, "ok": False, "error": f"{type(exc).__name__}: {exc}"})
    failed = sum(1 for item in results if not item["ok"])
    return {
        "ok": failed == 0,
        "checks": results,
        "summary": f"{len(results) - failed}/{len(results)} checks passed",
    }
