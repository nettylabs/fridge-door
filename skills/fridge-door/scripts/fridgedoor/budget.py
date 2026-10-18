"""The household budget: manual (no bank connections), adults only by default, exact money in any currency.

- Monthly categories with an optional budget each; expenses with amount, category, who, note and receipt photo.
- Recurring bills with due dates: record when they're paid, see what's coming, remind before, show on the calendar.
- Shared savings goals with progress.
- Month summary (spent vs budget per category) and month-over-month trend. All sums are Decimal, rounded to the
  currency's own decimals (JPY 0, KWD 3), so totals always add up to the cent.
"""

from __future__ import annotations

import datetime as _dt
import re
from decimal import Decimal
from pathlib import Path

from . import money, recur, trash
from .util import (MONTH_NAMES, MONTH_WORDS, ToolError, add_months, clean_text, fold, match_one, now_stamp,
                   plural)

DEFAULT_CATEGORIES = (
    ("Groceries", "🛒"), ("Housing", "🏠"), ("Utilities", "💡"), ("Transport", "🚗"), ("Kids", "🧒"),
    ("Health", "🩺"), ("Eating out", "🍽️"), ("Fun", "🎉"), ("Gifts", "🎁"), ("Other", "📦"),
)  # fmt: skip
ZERO = Decimal(0)


def add_default_categories(hh) -> list:
    """The usual categories, with no budgets yet (a new household starts with them). Returns the names added."""
    data = hh.data("budget")
    made = []
    for name, icon in DEFAULT_CATEGORIES:
        if not any(fold(c["name"]) == fold(name) for c in data["categories"]):
            made.append(_new_category(hh, data, name, None, icon)["name"])
    if made:
        hh.touch("budget")
    return made


def disp(hh) -> dict:
    return money.currency_display(hh.settings)


def amount(hh, value, field: str = "amount", allow_zero: bool = False, allow_negative: bool = False) -> Decimal:
    currency = hh.settings["currency"]
    raw = money.to_decimal(value, field)
    places = money.places(currency)
    if raw.normalize().as_tuple().exponent < -places:  # 12.999 dollars or 0.5 yen: ask, don't round
        example = "1250" if places == 0 else "12.50" if places == 2 else "12.500"
        raise ToolError(f"{value} has more decimal places than {currency} uses ({places}).",
                        hint=f"Give the amount as it was paid, e.g. {example}.", code="bad_number")  # fmt: skip
    number = money.quantize(raw, currency)
    if number < 0 and not allow_negative:
        raise ToolError(f"The {field} can't be negative.", code="bad_number")
    if number == 0 and not allow_zero:
        raise ToolError(f"The {field} can't be zero.", code="bad_number")
    return number


def parse_month(hh, value) -> tuple:
    """YYYY-MM, "this month", "last month", a month's name ("september", "sep 2026") or a date -> (first day,
    last day). A month named without a year is the latest one, this month included."""
    today = hh.today()
    text = fold(value or "this month")
    words = text.split()
    if text in ("this month", "now", ""):
        first = today.replace(day=1)
    elif text in ("last month", "previous month"):
        first = add_months(today.replace(day=1), -1)
    elif re.fullmatch(r"\d{4}-\d{1,2}", text):
        year, month = (int(x) for x in text.split("-"))
        if not 1 <= month <= 12:
            raise ToolError(f"{value!r} isn't a month.", hint="Use YYYY-MM, e.g. 2026-10.", code="bad_date")
        first = _dt.date(year, month, 1)
    elif words and words[0].rstrip(".,") in MONTH_WORDS and (len(words) == 1 or re.fullmatch(r"\d{4}", words[-1])):
        month = MONTH_WORDS[words[0].rstrip(".,")]
        year = int(words[-1]) if len(words) > 1 else today.year - (month > today.month)
        first = _dt.date(year, month, 1)
    else:
        first = hh.date(value, prefer="past").replace(day=1)
    last = add_months(first, 1) - _dt.timedelta(days=1)
    return first, last


def _require(ctx, need: str = "view") -> None:
    ctx.viewer.require("budget", need, "see the budget" if need == "view" else "change the budget")
    ctx.viewer.require_sees("budget")


def find_category(data: dict, query) -> dict:
    return match_one(data["categories"], query, "budget category",
                     hint="See them with: fridge budget categories (or add one with budget category-add)")  # fmt: skip


def _member_id(ctx, query):
    if not query:
        return None
    from .context import find_member

    return find_member(ctx.household, query)["id"]


def spent_by_category(data: dict, first: _dt.date, last: _dt.date) -> dict:
    totals: dict = {}
    for exp in data["expenses"]:
        if first.isoformat() <= exp["date"] <= last.isoformat():
            totals[exp["category"]] = totals.get(exp["category"], ZERO) + Decimal(exp["amount"])
    return totals


def month_summary(hh, data: dict, first: _dt.date, last: _dt.date) -> dict:
    d = disp(hh)
    spent = spent_by_category(data, first, last)
    rows = []
    for cat in data["categories"]:
        budget = Decimal(cat["monthly"]) if cat.get("monthly") is not None else None
        used = spent.get(cat["id"], ZERO)
        row = {"category": cat["name"], "icon": cat.get("icon"), "spent": used, "budget": budget,
               "spent_text": money.fmt(used, d)}  # fmt: skip
        if budget is not None:
            row["left"] = budget - used
            row["left_text"] = money.fmt(budget - used, d)
            row["percent"] = int((used * 100 / budget).to_integral_value()) if budget else None
            row["over"] = used > budget
        rows.append(row)
    total_spent = sum((r["spent"] for r in rows), ZERO)
    budgeted = sum((r["budget"] for r in rows if r["budget"] is not None), ZERO)
    in_budgets = sum((r["spent"] for r in rows if r["budget"] is not None), ZERO)
    outside = total_spent - in_budgets  # spending in categories without a budget isn't "over" anything
    return {
        "month": first.strftime("%Y-%m"),
        "month_name": f"{MONTH_NAMES[first.month - 1]} {first.year}",
        "rows": rows,
        "spent": total_spent,
        "budgeted": budgeted,
        "spent_in_budgets": in_budgets,
        "spent_outside_budgets": outside,
        "spent_text": money.fmt(total_spent, d),
        "budgeted_text": money.fmt(budgeted, d),
        "spent_in_budgets_text": money.fmt(in_budgets, d),
        "outside_text": money.fmt(outside, d) if outside else None,
        "left_text": money.fmt(budgeted - in_budgets, d) if budgeted else None,
        "over_by_text": money.fmt(in_budgets - budgeted, d) if budgeted and in_budgets > budgeted else None,
    }


def bill_dues(bill: dict, first: _dt.date, last: _dt.date) -> list:
    start = _dt.date.fromisoformat(bill["start"])
    if not bill.get("rrule"):
        return [start] if first <= start <= last else []
    return recur.between(recur.parse(bill["rrule"]), start, first, last, include_start=True)


def upcoming_bills(hh, data: dict, first: _dt.date, last: _dt.date, include_overdue: bool = True) -> list:
    """Unpaid bill due dates (overdue ones from the last 60 days too), soonest first."""
    d = disp(hh)
    out = []
    begin = first - _dt.timedelta(days=60) if include_overdue else first
    for bill in data["bills"]:
        for due in bill_dues(bill, begin, last):
            paid = due.isoformat() in bill.get("paid", {})
            if paid or (due < first and not include_overdue):
                continue
            autopay = bool(bill.get("autopay"))
            row = {"bill": bill["id"], "name": bill["name"], "due": due.isoformat(), "due_text": hh.day(due),
                   "overdue": due < first and not autopay, "unrecorded": due < first and autopay,
                   "autopay": autopay}  # fmt: skip
            if bill.get("amount") is not None:
                row["amount"] = Decimal(bill["amount"])
                row["amount_text"] = money.fmt(Decimal(bill["amount"]), d)
            out.append(row)
    return sorted(out, key=lambda r: (r["due"], r["name"]))


def goal_view(hh, goal: dict) -> dict:
    d = disp(hh)
    saved = sum((Decimal(c["amount"]) for c in goal.get("contributions", [])), ZERO)
    target = Decimal(goal["target"])
    percent = int((saved * 100 / target).to_integral_value()) if target else 0
    out = {"id": goal["id"], "name": goal["name"], "saved": saved, "target": target, "percent": max(0, percent),
           "saved_text": money.fmt(saved, d), "target_text": money.fmt(target, d), "deadline": goal.get("deadline")}  # fmt: skip
    if goal.get("deadline"):
        days = (_dt.date.fromisoformat(goal["deadline"]) - hh.today()).days
        out["days_left"] = days
        months = max(1, round(days / 30.4)) if days > 0 else None
        if months and saved < target:
            per_month = money.quantize((target - saved) / months, hh.settings["currency"])
            out["per_month_text"] = money.fmt(per_month, d)
    return out


def bar(percent: int, width: int = 10) -> str:
    filled = max(0, min(width, round(percent * width / 100)))
    return "█" * filled + "░" * (width - filled)


# --------------------------------------------------------------------------- commands: categories


def cmd_categories(ctx, args) -> dict:
    _require(ctx)
    hh = ctx.household
    data = hh.data("budget")
    first, last = parse_month(hh, args.month)
    summary = month_summary(hh, data, first, last)
    lines = []
    for row in summary["rows"]:
        if row["budget"] is not None:
            flag = " ⚠️ over" if row["over"] else ""
            lines.append(f"{row['icon'] or ''} {row['category']}: {row['spent_text']} of "
                         f"{money.fmt(row['budget'], disp(hh))} {bar(row['percent'] or 0)}{flag}".strip())  # fmt: skip
        else:
            lines.append(f"{row['icon'] or ''} {row['category']}: {row['spent_text']} (no budget set)".strip())
    return {"month": summary["month"], "categories": summary["rows"], "text": "\n".join(lines) or "No categories yet.",
            "summary": f"{plural(len(summary['rows']), 'category', 'categories')}; spent {summary['spent_text']} "
                       f"in {summary['month_name']}."}  # fmt: skip


def _new_category(hh, data: dict, name: str, monthly=None, icon=None) -> dict:
    if any(fold(c["name"]) == fold(name) for c in data["categories"]):
        raise ToolError(f"There's already a category called {name}.", code="exists")
    cat = {"id": hh.next_id("category"), "name": name, "icon": icon,
           "monthly": str(amount(hh, monthly, "monthly budget", allow_zero=True)) if monthly is not None else None}  # fmt: skip
    data["categories"].append(cat)
    return cat


def cmd_category_add(ctx, args) -> dict:
    _require(ctx, "edit")
    hh = ctx.household
    with hh.transaction(dry_run=args.dry_run):
        data = hh.data("budget")
        cat = _new_category(hh, data, clean_text(args.name, "category name", max_len=40), args.monthly, args.icon)
        hh.touch("budget")
        hh.log("budget.category_add", ctx.member["id"], category=cat["id"])
    budget = f" with a monthly budget of {money.fmt(Decimal(cat['monthly']), disp(hh))}" if cat["monthly"] else ""
    return {"category": cat, "dry_run": args.dry_run, "summary": f"Added the category {cat['name']}{budget}."}


def cmd_category_defaults(ctx, args) -> dict:
    _require(ctx, "edit")
    hh = ctx.household
    with hh.transaction():
        made = add_default_categories(hh)
    names = ", ".join(made) or "none (they're all there)"
    summary = f"Added {plural(len(made), 'category', 'categories')}: {names}."
    summary += " Set budgets with: fridge budget category-edit Groceries --monthly 800"
    return {"added": made, "summary": summary}


def cmd_category_edit(ctx, args) -> dict:
    _require(ctx, "edit")
    hh = ctx.household
    with hh.transaction():
        data = hh.data("budget")
        cat = find_category(data, args.category)
        if args.name:
            cat["name"] = clean_text(args.name, "category name", max_len=40)
        if args.monthly is not None:
            cat["monthly"] = None if fold(args.monthly) in ("none", "off", "") else str(
                amount(hh, args.monthly, "monthly budget", allow_zero=True))  # fmt: skip
        if args.icon:
            cat["icon"] = args.icon
        hh.touch("budget")
        hh.log("budget.category_edit", ctx.member["id"], category=cat["id"])
    budget = money.fmt(Decimal(cat["monthly"]), disp(hh)) if cat.get("monthly") else "no budget"
    return {"category": cat, "summary": f"{cat['name']}: {budget} a month."}


def cmd_category_delete(ctx, args) -> dict:
    _require(ctx, "edit")
    hh = ctx.household
    with hh.transaction():
        data = hh.data("budget")
        cat = find_category(data, args.category)
        used = sum(1 for e in data["expenses"] if e["category"] == cat["id"])
        if used:
            target = find_category(data, args.move_to) if args.move_to else None
            if target is None or target["id"] == cat["id"]:
                raise ToolError(f"{cat['name']} has {plural(used, 'expense')}.",
                                hint="Move them first: add --move-to <another category>", code="in_use")  # fmt: skip
            for exp in data["expenses"]:
                if exp["category"] == cat["id"]:
                    exp["category"] = target["id"]
        linked = [bill["id"] for bill in data["bills"] if bill.get("category") == cat["id"]]
        for bill in data["bills"]:
            if bill.get("category") == cat["id"]:
                bill["category"] = None
        data["categories"] = [c for c in data["categories"] if c["id"] != cat["id"]]
        undo = trash.put(hh, "category", [cat], ctx.member["id"], bills=linked, moved=used,
                         moved_to=target["name"] if used else None)  # fmt: skip
        hh.touch("budget")
        hh.log("budget.category_delete", ctx.member["id"], category=cat["id"])
    return {"summary": f"Deleted the category {cat['name']}. {trash.kept_for(hh)}", "undo": undo}


# --------------------------------------------------------------------------- commands: expenses


def _expense_view(hh, data: dict, exp: dict) -> dict:
    cats = {c["id"]: c["name"] for c in data["categories"]}
    out = {"id": exp["id"], "date": exp["date"], "amount": Decimal(exp["amount"]),
           "amount_text": money.fmt(Decimal(exp["amount"]), disp(hh)), "category": cats.get(exp["category"], "?"),
           "by": hh.member_name(exp.get("spent_by")), "note": exp.get("note")}  # fmt: skip
    if exp.get("receipt"):
        out["receipt"] = exp["receipt"]
    if exp.get("bill"):
        out["bill"] = exp["bill"]
    return out


def _receipt(path):
    if not path:
        return None
    file = Path(path).expanduser()
    if not file.is_file():
        raise ToolError(f"There's no file at {path}.", hint="Save the receipt photo first, then pass its path.",
                        code="no_file")  # fmt: skip
    return str(file)


def cmd_spend(ctx, args) -> dict:
    _require(ctx, "edit")
    hh = ctx.household
    with hh.transaction(dry_run=args.dry_run):
        data = hh.data("budget")
        if not data["categories"]:
            raise ToolError("There are no budget categories yet.",
                            hint="Add the usual ones with: fridge budget category-defaults", code="no_categories")  # fmt: skip
        cat = find_category(data, args.category)
        day = _spent_on(hh, args.date)
        exp = {"id": hh.next_id("expense"), "date": day.isoformat(), "amount": str(amount(hh, args.amount)),
               "category": cat["id"], "spent_by": _member_id(ctx, args.by) or ctx.member["id"],
               "note": clean_text(args.note, "note", max_len=200, required=False), "receipt": _receipt(args.receipt),
               "created_by": ctx.member["id"], "created_at": now_stamp()}  # fmt: skip
        data["expenses"].append(exp)
        hh.touch("budget")
        hh.log("budget.spend", ctx.member["id"], expense=exp["id"])
        view = _expense_view(hh, data, exp)
        first, last = parse_month(hh, day.isoformat())
        row = next(r for r in month_summary(hh, data, first, last)["rows"] if r["category"] == cat["name"])
    where = f" ({exp['note']})" if exp.get("note") else ""
    summary = (f"{'Would log' if args.dry_run else 'Logged'} {view['amount_text']} for {cat['name']}{where} on "
               f"{hh.day(day)}")  # fmt: skip
    if row.get("budget") is not None:
        summary += f": {row['spent_text']} of {money.fmt(row['budget'], disp(hh))} used this month"
        if row["over"]:
            summary += " (over budget)"
    return {"expense": view, "category_month": row, "dry_run": args.dry_run, "summary": summary + "."}


def _spent_on(hh, value) -> _dt.date:
    """The day money was spent: "monday" is the last Monday, and a future date is refused."""
    day = hh.date(value, prefer="past") if value else hh.today()
    if day > hh.today():
        raise ToolError(f"{hh.day(day)} hasn't happened yet.",
                        hint="Log spending once it's happened, with the day it was paid (e.g. --date \"last monday\").",
                        code="future_date")  # fmt: skip
    return day


def cmd_expenses(ctx, args) -> dict:
    _require(ctx)
    hh = ctx.household
    data = hh.data("budget")
    first, last = parse_month(hh, args.month)
    rows = [e for e in data["expenses"] if first.isoformat() <= e["date"] <= last.isoformat()]
    if args.category:
        cat = find_category(data, args.category)
        rows = [e for e in rows if e["category"] == cat["id"]]
    if args.by:
        member_id = _member_id(ctx, args.by)
        rows = [e for e in rows if e.get("spent_by") == member_id]
    rows.sort(key=lambda e: (e["date"], e["id"]))
    views = [_expense_view(hh, data, e) for e in rows]
    total = sum((v["amount"] for v in views), ZERO)
    lines = [
        f"{hh.day(_dt.date.fromisoformat(v['date']))}  {v['amount_text']}  {v['category']}  ({v['by']})"
        + (f" — {v['note']}" if v["note"] else "") for v in views
    ]
    return {"expenses": views, "total": total, "total_text": money.fmt(total, disp(hh)),
            "text": "\n".join(lines) or "No expenses.",
            "summary": f"{plural(len(views), 'expense')} in {MONTH_NAMES[first.month - 1]} {first.year}, "
                       f"{money.fmt(total, disp(hh))}."}  # fmt: skip


def cmd_expense_edit(ctx, args) -> dict:
    _require(ctx, "edit")
    hh = ctx.household
    with hh.transaction():
        data = hh.data("budget")
        exp = match_one(data["expenses"], args.expense, "expense", key="id")
        if args.amount:
            exp["amount"] = str(amount(hh, args.amount))
        if args.category:
            exp["category"] = find_category(data, args.category)["id"]
        if args.date:
            exp["date"] = _spent_on(hh, args.date).isoformat()
        if args.note is not None:
            exp["note"] = clean_text(args.note, "note", max_len=200, required=False)
        if args.by:
            exp["spent_by"] = _member_id(ctx, args.by)
        hh.touch("budget")
        hh.log("budget.expense_edit", ctx.member["id"], expense=exp["id"])
        view = _expense_view(hh, data, exp)
    return {"expense": view, "summary": f"Updated {exp['id']}: {view['amount_text']} for {view['category']}."}


def cmd_expense_delete(ctx, args) -> dict:
    _require(ctx, "edit")
    hh = ctx.household
    with hh.transaction(dry_run=args.dry_run):
        data = hh.data("budget")
        exp = match_one(data["expenses"], args.expense, "expense", key="id")
        data["expenses"] = [e for e in data["expenses"] if e["id"] != exp["id"]]
        paid = [[bill["id"], due] for bill in data["bills"] for due, eid in bill.get("paid", {}).items()
                if eid == exp["id"]]  # fmt: skip
        for bill in data["bills"]:
            bill["paid"] = {due: eid for due, eid in bill.get("paid", {}).items() if eid != exp["id"]}
        undo = trash.put(hh, "expense", [exp], ctx.member["id"], paid=paid)
        hh.touch("budget")
        hh.log("budget.expense_delete", ctx.member["id"], expense=exp["id"])
    verb = "Would delete" if args.dry_run else "Deleted"
    return {"dry_run": args.dry_run, "undo": None if args.dry_run else undo,
            "summary": f"{verb} the expense {exp['id']} ({money.fmt(Decimal(exp['amount']), disp(hh))}). "
                       f"{trash.kept_for(hh)}"}  # fmt: skip


def cmd_month(ctx, args) -> dict:
    _require(ctx)
    hh = ctx.household
    data = hh.data("budget")
    first, last = parse_month(hh, args.month)
    summary = month_summary(hh, data, first, last)
    over = [r["category"] for r in summary["rows"] if r.get("over")]
    text = f"{summary['month_name']}: spent {summary['spent_text']}"
    if summary["budgeted"]:
        left = f"{summary['over_by_text']} over" if summary["over_by_text"] else f"{summary['left_text']} left"
        text += (f"; {summary['spent_in_budgets_text']} of {summary['budgeted_text']} in the categories with a "
                 f"budget ({left})")  # fmt: skip
        if summary["outside_text"]:
            text += f", and {summary['outside_text']} in categories without one"
    lines = [text]
    for row in summary["rows"]:
        if row["spent"] or row["budget"]:
            budget = f" / {money.fmt(row['budget'], disp(hh))}" if row["budget"] is not None else ""
            lines.append(f"  {row['icon'] or ''} {row['category']}: {row['spent_text']}{budget}"
                         + (" ⚠️" if row.get("over") else ""))  # fmt: skip
    return dict(summary, text="\n".join(lines), over=over,
                summary=text + (f". Over budget: {', '.join(over)}." if over else "."))  # fmt: skip


def cmd_trend(ctx, args) -> dict:
    _require(ctx)
    hh = ctx.household
    data = hh.data("budget")
    d = disp(hh)
    first_this = hh.today().replace(day=1)
    months = []
    for back in range(args.months - 1, -1, -1):
        first = add_months(first_this, -back)
        last = add_months(first, 1) - _dt.timedelta(days=1)
        spent = spent_by_category(data, first, last)
        cats = {c["id"]: c["name"] for c in data["categories"]}
        total = sum(spent.values(), ZERO)
        months.append({"month": first.strftime("%Y-%m"), "total": total, "total_text": money.fmt(total, d),
                       "by_category": {cats.get(k, "?"): v for k, v in spent.items()}})  # fmt: skip
    peak = max((m["total"] for m in months), default=ZERO) or Decimal(1)
    lines = [f"{m['month']}  {bar(int(m['total'] * 100 / peak), 16)}  {m['total_text']}" for m in months]
    return {"months": months, "text": "\n".join(lines),
            "summary": f"Spending over the last {plural(args.months, 'month')}."}  # fmt: skip


# --------------------------------------------------------------------------- commands: bills


def find_bill(data: dict, query) -> dict:
    return match_one(data["bills"], query, "bill", hint="See them with: fridge budget bills")


def cmd_bill_add(ctx, args) -> dict:
    _require(ctx, "edit")
    hh = ctx.household
    start = hh.date(args.due)
    until = hh.date(args.until) if args.until else None
    rrule = recur.from_words(args.repeat, start, until=until, count=args.times) if args.repeat else None
    if rrule:
        start = recur.next_after(recur.parse(rrule), start, start - _dt.timedelta(days=1)) or start
    from .events import parse_reminders

    with hh.transaction(dry_run=args.dry_run):
        data = hh.data("budget")
        bill = {"id": hh.next_id("bill"), "name": clean_text(args.name, "bill name", max_len=60),
                "amount": str(amount(hh, args.amount)) if args.amount else None,
                "category": find_category(data, args.category)["id"] if args.category else None,
                "rrule": rrule, "start": start.isoformat(),
                "remind_minutes": parse_reminders(args.remind or "3d"), "calendar": not args.no_calendar,
                "autopay": bool(args.autopay), "paid": {}, "created_by": ctx.member["id"], "created_at": now_stamp()}  # fmt: skip
        data["bills"].append(bill)
        hh.touch("budget")
        hh.log("budget.bill_add", ctx.member["id"], bill=bill["id"])
    amount_text = f" of {money.fmt(Decimal(bill['amount']), disp(hh))}" if bill["amount"] else ""
    repeats = f", {recur.describe(rrule)}" if rrule else ""
    return {"bill": bill, "dry_run": args.dry_run,
            "summary": f"{'Would add' if args.dry_run else 'Added'} the bill {bill['name']}{amount_text}, "
                       f"first due {hh.day(start)}{repeats}."}  # fmt: skip


def cmd_bills(ctx, args) -> dict:
    _require(ctx)
    hh = ctx.household
    data = hh.data("budget")
    today = hh.today()
    rows = upcoming_bills(hh, data, today, today + _dt.timedelta(days=args.days - 1))
    lines = [("⚠️ overdue " if r["overdue"] else "") + f"{r['due_text']}  {r['name']}"
             + (f"  {r['amount_text']}" if r.get("amount_text") else "")
             + (" (autopay: record it once it's gone out)" if r["unrecorded"] else " (autopay)" if r["autopay"] else "")
             for r in rows]  # fmt: skip
    total = sum((r.get("amount", ZERO) for r in rows), ZERO)
    total_text = money.fmt(total, disp(hh))
    summary = f"{plural(len(rows), 'bill')} due in the next {args.days} days, {total_text}."
    return {"bills": rows, "total_text": total_text, "text": "\n".join(lines) or "No bills due.", "summary": summary}


def cmd_bill_paid(ctx, args) -> dict:
    _require(ctx, "edit")
    hh = ctx.household
    with hh.transaction(dry_run=args.dry_run):
        data = hh.data("budget")
        bill = find_bill(data, args.bill)
        today = hh.today()
        if args.due:
            due = hh.date(args.due, prefer="nearest")
            if due not in bill_dues(bill, due, due):
                raise ToolError(f"{bill['name']} isn't due on {hh.day(due)}.", code="not_found")
        else:
            open_dues = [d for d in bill_dues(bill, today - _dt.timedelta(days=60), today + _dt.timedelta(days=45))
                         if d.isoformat() not in bill.get("paid", {})]  # fmt: skip
            if not open_dues:
                raise ToolError(f"Nothing is due for {bill['name']} soon.", hint="Pass --due DATE.", code="not_found")
            due = open_dues[0]
            if (due - today).days > 7:
                # Probably said twice (two people, or the same news again): the latest one is already paid.
                last = _last_paid(hh, data, bill)
                raise ToolError(
                    f"The next unpaid {bill['name']} isn't due until {hh.day(due)}." + (f" {last}" if last else ""),
                    hint=f"If it really has been paid early, run it again with --due {due.isoformat()}.",
                    code="not_due_yet",
                )
        if due.isoformat() in bill.get("paid", {}):
            last = _last_paid(hh, data, bill, due)
            return {"summary": f"{bill['name']} due {hh.day(due)} was already recorded as paid. {last}".strip()}
        value = args.amount or bill.get("amount")
        if value is None:
            raise ToolError(f"How much was {bill['name']}?", hint="Add --amount.", code="missing")
        category = bill.get("category")
        if category is None:
            if not data["categories"]:
                _new_category(hh, data, "Other", None, "📦")
            likely = [c["id"] for c in data["categories"] if fold(c["name"]) in ("utilities", "housing", "other")]
            category = likely[0] if likely else data["categories"][0]["id"]
        paid_on = _spent_on(hh, args.date)
        exp = {"id": hh.next_id("expense"), "date": paid_on.isoformat(), "amount": str(amount(hh, value)),
               "category": category, "spent_by": _member_id(ctx, args.by) or ctx.member["id"],
               "note": f"{bill['name']} (due {hh.day(due)})",
               "receipt": None, "bill": bill["id"], "due": due.isoformat(), "created_by": ctx.member["id"],
               "created_at": now_stamp()}  # fmt: skip
        data["expenses"].append(exp)
        bill.setdefault("paid", {})[due.isoformat()] = exp["id"]
        hh.touch("budget")
        hh.log("budget.bill_paid", ctx.member["id"], bill=bill["id"], due=due.isoformat())
    nxt = next((d for d in bill_dues(bill, due + _dt.timedelta(days=1), due + _dt.timedelta(days=400))), None)
    verb = "Would record" if args.dry_run else "Recorded"
    summary = f"{verb} {bill['name']} as paid: {money.fmt(Decimal(exp['amount']), disp(hh))} (due {hh.day(due)})."
    if nxt:
        summary += f" Next due {hh.day(nxt)}."
    return {"expense": exp["id"], "dry_run": args.dry_run, "summary": summary}


def _last_paid(hh, data: dict, bill: dict, due: _dt.date | None = None) -> str:
    """ "1 Nov was recorded as paid on Sun 1 Nov by Alex." for the latest (or the given) paid due date."""
    paid = bill.get("paid", {})
    key = due.isoformat() if due else max(paid, default=None)
    exp = next((e for e in data["expenses"] if e["id"] == paid.get(key)), None) if key else None
    if not exp:
        return ""
    who = hh.member_name(exp.get("spent_by")) or "someone"
    when = hh.day(_dt.date.fromisoformat(exp["date"]))
    return f"The one due {hh.day(_dt.date.fromisoformat(key))} was recorded as paid on {when} by {who}."


def cmd_bill_edit(ctx, args) -> dict:
    _require(ctx, "edit")
    hh = ctx.household
    with hh.transaction(dry_run=args.dry_run):
        data = hh.data("budget")
        bill = find_bill(data, args.bill)
        if args.due:  # moves the next due date (and every later one)
            start = hh.date(args.due, prefer="nearest")
            if bill.get("rrule"):
                bill["rrule"] = recur.reanchor(bill["rrule"], start)
            bill["start"] = start.isoformat()
        if args.until or args.no_repeat:
            if not bill.get("rrule"):
                raise ToolError(f"{bill['name']} doesn't repeat.", code="usage")
            if args.no_repeat:
                bill["rrule"] = None
            else:
                rule = recur.parse(bill["rrule"])
                rule["until"], rule["count"] = hh.date(args.until), None
                bill["rrule"] = recur.to_text(rule)
        if args.name:
            bill["name"] = clean_text(args.name, "bill name", max_len=60)
        if args.amount:
            bill["amount"] = str(amount(hh, args.amount))
        if args.category:
            bill["category"] = find_category(data, args.category)["id"]
        if args.remind is not None:
            from .events import parse_reminders

            bill["remind_minutes"] = parse_reminders(args.remind)
        if args.calendar is not None:
            bill["calendar"] = fold(args.calendar) in ("yes", "on", "true")
        if args.autopay is not None:
            bill["autopay"] = fold(args.autopay) in ("yes", "on", "true")
        hh.touch("budget")
        nxt = next(iter(bill_dues(bill, hh.today(), hh.today() + _dt.timedelta(days=400))), None)
    when = f" Next due {hh.day(nxt)}." if nxt else ""
    return {"bill": bill, "dry_run": args.dry_run,
            "summary": f"{'Would update' if args.dry_run else 'Updated'} the bill {bill['name']}.{when}"}


def cmd_bill_delete(ctx, args) -> dict:
    _require(ctx, "edit")
    hh = ctx.household
    with hh.transaction():
        data = hh.data("budget")
        bill = find_bill(data, args.bill)
        data["bills"] = [b for b in data["bills"] if b["id"] != bill["id"]]
        undo = trash.put(hh, "bill", [bill], ctx.member["id"])
        hh.touch("budget")
    return {"summary": f"Deleted the bill {bill['name']} (past payments stay in the expenses). {trash.kept_for(hh)}",
            "undo": undo}


# --------------------------------------------------------------------------- commands: goals


def find_goal(data: dict, query) -> dict:
    return match_one(data["goals"], query, "savings goal", hint="See them with: fridge budget goals")


def cmd_goal_add(ctx, args) -> dict:
    _require(ctx, "edit")
    hh = ctx.household
    with hh.transaction(dry_run=args.dry_run):
        data = hh.data("budget")
        name = clean_text(args.name, "goal name", max_len=60)
        if any(fold(g["name"]) == fold(name) for g in data["goals"]):
            raise ToolError(f"There's already a goal called {name}.", code="exists")
        goal = {"id": hh.next_id("goal"), "name": name, "target": str(amount(hh, args.target)),
                "deadline": hh.date(args.deadline).isoformat() if args.deadline else None,
                "contributions": [], "created_at": now_stamp()}  # fmt: skip
        data["goals"].append(goal)
        hh.touch("budget")
        view = goal_view(hh, goal)
    return {"goal": view, "dry_run": args.dry_run,
            "summary": f"{'Would start' if args.dry_run else 'Started'} the goal {name}: {view['target_text']}"
                       + (f" by {goal['deadline']}" if goal["deadline"] else "") + "."}  # fmt: skip


def cmd_goal_save(ctx, args) -> dict:
    _require(ctx, "edit")
    hh = ctx.household
    with hh.transaction(dry_run=args.dry_run):
        data = hh.data("budget")
        goal = find_goal(data, args.goal)
        value = amount(hh, args.amount, allow_negative=True)
        saved = sum((Decimal(c["amount"]) for c in goal["contributions"]), ZERO)
        if saved + value < 0:
            raise ToolError("That would take the goal below zero.", code="bad_number")
        goal["contributions"].append({"date": hh.today().isoformat(), "amount": str(value),
                                      "by": _member_id(ctx, args.by) or ctx.member["id"],
                                      "note": clean_text(args.note, "note", max_len=120, required=False)})  # fmt: skip
        hh.touch("budget")
        view = goal_view(hh, goal)
    verb = "Added" if value > 0 else "Took out"
    return {"goal": view, "dry_run": args.dry_run,
            "summary": f"{verb} {money.fmt(abs(value), disp(hh))}: {goal['name']} is at {view['saved_text']} of "
                       f"{view['target_text']} ({view['percent']}%)."}  # fmt: skip


def cmd_goals(ctx, args) -> dict:
    _require(ctx)
    hh = ctx.household
    views = [goal_view(hh, g) for g in hh.data("budget")["goals"]]
    lines = [f"{v['name']}: {v['saved_text']} of {v['target_text']} {bar(v['percent'])} {v['percent']}%"
             + (f" — about {v['per_month_text']} a month to make {v['deadline']}" if v.get("per_month_text") else "")
             for v in views]  # fmt: skip
    return {"goals": views, "text": "\n".join(lines) or "No savings goals yet.",
            "summary": f"{plural(len(views), 'savings goal')}."}  # fmt: skip


def cmd_goal_delete(ctx, args) -> dict:
    _require(ctx, "edit")
    hh = ctx.household
    with hh.transaction():
        data = hh.data("budget")
        goal = find_goal(data, args.goal)
        data["goals"] = [g for g in data["goals"] if g["id"] != goal["id"]]
        undo = trash.put(hh, "goal", [goal], ctx.member["id"])
        hh.touch("budget")
    return {"summary": f"Deleted the goal {goal['name']}. {trash.kept_for(hh)}", "undo": undo}


# --------------------------------------------------------------------------- layers, Today, erase


def bills_layer(ctx, first: _dt.date, last: _dt.date) -> list:
    if not ctx.viewer.sees("budget"):
        return []
    hh = ctx.household
    data = hh.data("budget")
    out = []
    for bill in data["bills"]:
        if not bill.get("calendar", True):
            continue
        for due in bill_dues(bill, first, last):
            label = f"{bill['name']} due"
            if bill.get("amount"):
                label += f" ({money.fmt(Decimal(bill['amount']), disp(hh))})"
            paid = due.isoformat() in bill.get("paid", {})
            out.append({"event": bill["id"], "date": due.isoformat(), "end_date": None, "time": None, "end_time": None,
                        "all_day": True, "title": label + (" ✓ paid" if paid else ""), "type": "bill", "icon": "💳",
                        "location": None, "members": [], "color": None, "repeats": bool(bill.get("rrule")),
                        "layer": "bills"})  # fmt: skip
    return out


def today_bills(ctx, member, day: _dt.date):
    from . import access

    if not ctx.viewer.sees("budget") or not access.can(member, "budget", "view"):
        return None
    hh = ctx.household
    rows = upcoming_bills(hh, hh.data("budget"), day, day + _dt.timedelta(days=6))
    if not rows:
        return None
    lines = [("⚠️ Overdue: " if r["overdue"] else "") + f"{r['name']}" + (f" {r['amount_text']}" if r.get("amount_text")
             else "") + f" — due {r['due']}" + (" (autopay)" if r["autopay"] else "") for r in rows]  # fmt: skip
    return {"title": "💳 Bills", "items": rows, "lines": lines}


def forget_member(hh, member_id: str) -> list:
    data = hh.data("budget")
    for exp in data["expenses"]:
        for key in ("spent_by", "created_by"):
            if exp.get(key) == member_id:
                exp[key] = None
    for goal in data["goals"]:
        for c in goal.get("contributions", []):
            if c.get("by") == member_id:
                c["by"] = None
    for bill in data["bills"]:
        if bill.get("created_by") == member_id:
            bill["created_by"] = None

    def scrub(record: dict) -> None:  # an expense, bill, goal or category in the bin
        for key in ("spent_by", "created_by"):
            if record.get(key) == member_id:
                record[key] = None
        for c in record.get("contributions", []):
            if c.get("by") == member_id:
                c["by"] = None

    trash.forget(hh, "budget", member_id, lambda record: False, scrub)
    hh.touch("budget")
    return []


def register(cli) -> None:
    from . import events
    from .members import FORGET_HOOKS

    FORGET_HOOKS.append(forget_member)
    events.LAYERS["bills"] = bills_layer
    grp = cli.group("budget", "The household budget: categories, expenses, bills, savings goals, month reports.")
    p = grp.add("categories", "Categories with this month's spending against their budgets.",
                ["fridge budget categories", "fridge budget categories --month \"last month\""], cmd_categories)  # fmt: skip
    p.add_argument("--month")
    p = grp.add("category-add", "Add a category, optionally with a monthly budget.",
                ['fridge budget category-add "Pets" --monthly 120 --icon 🐾'], cmd_category_add)  # fmt: skip
    p.add_argument("name")
    p.add_argument("--monthly", help="Monthly budget")
    p.add_argument("--icon")
    p.add_argument("--dry-run", action="store_true")
    grp.add("category-defaults", "Add the usual categories (Groceries, Housing, Utilities ...), with no budgets yet.",
            ["fridge budget category-defaults"], cmd_category_defaults)  # fmt: skip
    p = grp.add("category-edit", "Rename a category, set its monthly budget (or none), or change its icon.",
                ["fridge budget category-edit Groceries --monthly 800"], cmd_category_edit)  # fmt: skip
    p.add_argument("category")
    p.add_argument("--name")
    p.add_argument("--monthly")
    p.add_argument("--icon")
    p = grp.add("category-delete", "Delete a category (move its expenses with --move-to).",
                ["fridge budget category-delete Fun --move-to Other"], cmd_category_delete)  # fmt: skip
    p.add_argument("category")
    p.add_argument("--move-to")
    p = grp.add(
        "spend",
        "Log an expense. From a receipt photo: read it, run with --dry-run, check with the person, then log it.",
        ["fridge budget spend 54.20 --category Groceries", "fridge budget spend 38 --category \"Eating out\" --by Luis "
         '--note "Pizza night" --receipt /workspace/receipts/pizza.jpg --dry-run'],
        cmd_spend,
    )  # fmt: skip
    p.add_argument("amount")
    p.add_argument("--category", required=True)
    p.add_argument("--by", help="Who spent it (default: you)")
    p.add_argument("--date")
    p.add_argument("--note")
    p.add_argument("--receipt", help="Path of a saved receipt photo")
    p.add_argument("--dry-run", action="store_true")
    p = grp.add("expenses", "List expenses for a month, by category or person.",
                ["fridge budget expenses", "fridge budget expenses --month 2026-09 --category Groceries"], cmd_expenses)  # fmt: skip
    p.add_argument("--month")
    p.add_argument("--category")
    p.add_argument("--by")
    p = grp.add(
        "expense-edit", "Change an expense.", ["fridge budget expense-edit X4 --amount 45.10"], cmd_expense_edit
    )
    p.add_argument("expense")
    p.add_argument("--amount")
    p.add_argument("--category")
    p.add_argument("--date")
    p.add_argument("--note")
    p.add_argument("--by")
    p.add_argument("--dry-run", action="store_true")
    p = grp.add("expense-delete", "Delete an expense.", ["fridge budget expense-delete X4"], cmd_expense_delete)
    p.add_argument("expense")
    p.add_argument("--dry-run", action="store_true")
    p = grp.add("month", "The month at a glance: spent vs budget per category.",
                ["fridge budget month", "fridge budget month 2026-09"], cmd_month)  # fmt: skip
    p.add_argument("month", nargs="?")
    p = grp.add("trend", "Spending month by month.", ["fridge budget trend --months 6"], cmd_trend)
    p.add_argument("--months", type=int, default=6)
    p = grp.add(
        "bill-add",
        "Add a recurring bill with its due date (reminded 3 days before by default, shown on the calendar).",
        ['fridge budget bill-add Rent --amount 1800 --due 2026-11-01 --repeat monthly --category Housing',
         'fridge budget bill-add "Car insurance" --amount 640 --due 2027-03-15 --repeat yearly --remind 2w'],
        cmd_bill_add,
    )  # fmt: skip
    p.add_argument("name")
    p.add_argument("--amount")
    p.add_argument("--due", required=True, help="The first due date")
    p.add_argument("--repeat", help="monthly, every 3 months, yearly ... (leave out for a one-off)")
    p.add_argument("--until", help="The last due date, for a bill that stops")
    p.add_argument("--times", type=int, help="How many payments in all")
    p.add_argument("--category")
    p.add_argument("--remind", help='How long before: "3d", "1w" (default 3d)')
    p.add_argument("--no-calendar", action="store_true", help="Don't show it on the calendar")
    p.add_argument("--autopay", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p = grp.add("bills", "Bills coming up (and any overdue).", ["fridge budget bills --days 31"], cmd_bills)
    p.add_argument("--days", type=int, default=31)
    p = grp.add("bill-paid", "Record a bill as paid (logs the expense).",
                ["fridge budget bill-paid Rent", "fridge budget bill-paid Hydro --amount 142.37"], cmd_bill_paid)  # fmt: skip
    p.add_argument("bill")
    p.add_argument("--due", help="Which due date (default: the oldest unpaid, if it's due within a week)")
    p.add_argument("--amount", help="If it differs from the usual amount")
    p.add_argument("--date", help="When it was paid (default today)")
    p.add_argument("--by", help="Who paid it (default: you)")
    p.add_argument("--dry-run", action="store_true")
    p = grp.add("bill-edit", "Change a bill.", ["fridge budget bill-edit Rent --amount 1850"], cmd_bill_edit)
    p.add_argument("bill")
    p.add_argument("--name")
    p.add_argument("--amount")
    p.add_argument("--category")
    p.add_argument("--remind")
    p.add_argument("--calendar", help="yes or no")
    p.add_argument("--autopay", help="yes or no")
    p.add_argument("--due", help="Move the next due date (later ones follow)")
    p.add_argument("--until", help="The last due date, for a bill that stops")
    p.add_argument("--no-repeat", action="store_true", help="Stop it repeating")
    p.add_argument("--dry-run", action="store_true")
    p = grp.add("bill-delete", "Delete a bill.", ["fridge budget bill-delete Gym"], cmd_bill_delete)
    p.add_argument("bill")
    p = grp.add("goal-add", "Start a shared savings goal.",
                ['fridge budget goal-add "Holiday fund" --target 3000 --by 2027-07-01'], cmd_goal_add)  # fmt: skip
    p.add_argument("name")
    p.add_argument("--target", required=True)
    p.add_argument("--by", dest="deadline", help="Target date")
    p.add_argument("--dry-run", action="store_true")
    p = grp.add("goal-save", "Put money towards a goal (negative to take some out).",
                ['fridge budget goal-save "Holiday fund" 150 --by Luis'], cmd_goal_save)  # fmt: skip
    p.add_argument("goal")
    p.add_argument("amount")
    p.add_argument("--by", help="Who put it in (default: you)")
    p.add_argument("--note")
    p.add_argument("--dry-run", action="store_true")
    grp.add("goals", "Savings goals with progress.", ["fridge budget goals"], cmd_goals)
    p = grp.add("goal-delete", "Delete a goal.", ['fridge budget goal-delete "Holiday fund"'], cmd_goal_delete)
    p.add_argument("goal")
