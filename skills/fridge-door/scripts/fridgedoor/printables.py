"""Printables: the "this week" fridge sheet, month and week calendars, a shopping checklist, a recipe card and a
budget report. Each is a PDF from the built-in engine (pdf.py, reused from Job to Paid) and an accessible HTML
page, on the household's paper size (A4 or Letter).

What goes on paper is what anyone in the home may see: the fridge sheet and calendars carry household-wide events
only (no private or members-only ones unless --mine), never sensitive notes, never the budget.
"""

from __future__ import annotations

import datetime as _dt
import html as _html
import re
import shutil
from decimal import Decimal

from . import access, budget, events, ingredients, mealplan, money, pdf, recipes, shopping, todos
from .render import pdf_text, write
from .util import ToolError, add_months, day_text, plural, servings_arg

ACCENT = "#3D5A80"
WARN = "#C0392B"
OK = "#2E9E8F"
INK = pdf.INK
MUTED = pdf.MUTED
RULE = pdf.RULE
DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
MONTH_NAMES = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
               "November", "December")  # fmt: skip


class Sheet:
    """One or more pages with top-left coordinates and helpers for fitting text."""

    def __init__(self, paper: str, landscape: bool, title: str):
        width, height = pdf.PAPER.get(paper, pdf.PAPER["a4"])
        if landscape:
            width, height = height, width
        self.doc = pdf.PDF(width, height, pdf_text(title))
        self.c = pdf.Canvas(self.doc)
        self.c.start_page()
        self.w, self.h, self.m = width, height, 36.0

    def text(self, x, top, text, font="F1", size=10, color=INK, align="left"):
        self.c.text(x, top, pdf_text(text), font=font, size=size, color=color, align=align)

    def fit(self, text, font: str, size: float, width: float) -> str:
        text = pdf_text(text)
        if pdf.text_width(text, font, size) <= width:
            return text
        while text and pdf.text_width(text + "…", font, size) > width:
            text = text[:-1]
        return text.rstrip() + "…"

    def wrap(self, text, font: str, size: float, width: float) -> list:
        return pdf.wrap(pdf_text(text), font, size, width)

    def lines(self, text, font: str, size: float, width: float, most: int) -> list:
        """Wrapped lines, at most `most`; the last one ends in "…" when the text runs on."""
        wrapped = self.wrap(text, font, size, width) or [""]
        if len(wrapped) <= most:
            return wrapped
        return wrapped[: most - 1] + [self.fit(" ".join(wrapped[most - 1 :]), font, size, width)]

    def header(self, title: str, subtitle: str, right: str = "") -> float:
        self.text(self.m, self.m + 14, title, font="F2", size=18, color=ACCENT)
        self.text(self.m, self.m + 30, subtitle, size=10, color=MUTED)
        if right:
            self.text(self.w - self.m, self.m + 14, right, size=10, color=MUTED, align="right")
        self.c.line(self.m, self.m + 38, self.w - self.m, self.m + 38, color=RULE, width=0.8)
        return self.m + 52

    def footer(self, text: str) -> None:
        self.text(self.m, self.h - 20, text, size=7, color=MUTED)

    def new_page(self) -> None:
        self.c.start_page()

    def save(self, path) -> None:
        pdf.write_pdf(self.doc, path)


def _printed(hh) -> str:
    """ "printed 19 Oct 2026" (the household's day and date format, not the computer's UTC date)."""
    return "printed " + day_text(hh.today(), hh.settings, weekday=False, year=True)


def _page_html(title: str, body: str, landscape: bool = False, paper: str = "a4", printed: str = "") -> str:
    size = ("A4" if paper == "a4" else "letter") + (" landscape" if landscape else "")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_html.escape(title)}</title>
<style>
@page {{ size: {size}; margin: 12mm; }}
body {{ font-family: -apple-system, "Segoe UI", Roboto, "Noto Sans", Arial, sans-serif; color: #1c1f23; margin: 0;
       padding: 16px; background: #fff; }}
h1 {{ color: {ACCENT}; font-size: 22px; margin: 0 0 2px; }}
.sub {{ color: #6b7079; margin: 0 0 12px; font-size: 13px; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #dcdfe3; padding: 4px 6px; vertical-align: top; font-size: 12px; text-align: left; }}
th {{ background: #f2f4f7; }}
.dot {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 4px; }}
.muted {{ color: #6b7079; }}
.box {{ display: inline-block; width: 10px; height: 10px; border: 1px solid #444; margin-right: 5px; }}
.bar {{ background: #e6e9ee; height: 10px; border-radius: 3px; overflow: hidden; }}
.bar span {{ display: block; height: 100%; background: {ACCENT}; }}
.bar span.over {{ background: {WARN}; }}
.cols {{ columns: 2; column-gap: 24px; }}
footer {{ margin-top: 16px; color: #6b7079; font-size: 11px; }}
</style></head><body>
{body}
<footer>Made with Fridge Door · {printed}</footer>
</body></html>
"""


def _e(text) -> str:
    return _html.escape(str(text or ""))


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", name).strip("-").lower() or "printable"


def _dates(first: _dt.date, days: int) -> list:
    return [first + _dt.timedelta(days=i) for i in range(days)]


def _day_heading(day: _dt.date, settings: dict) -> str:
    """A column heading the household's way: "Sun 18/10", "Sun 10/18", or "Sun Oct 18" where dates are written
    2026-10-18 (a bare 18/10 could be read either way there)."""
    order = str(settings.get("date_format", ""))
    if order.startswith("YYYY"):
        return f"{DAY_NAMES[day.weekday()]} {MONTH_NAMES[day.month - 1][:3]} {day.day}"
    if order.startswith("MM"):
        return f"{DAY_NAMES[day.weekday()]} {day.month}/{day.day}"
    return f"{DAY_NAMES[day.weekday()]} {day.day}/{day.month}"


def _span_text(first: _dt.date, last: _dt.date, settings: dict) -> str:
    """ "18 Oct – 24 Oct 2026", or "Oct 18 – Oct 24, 2026" where the month comes first (both years across New Year)."""
    start, end = MONTH_NAMES[first.month - 1][:3], MONTH_NAMES[last.month - 1][:3]
    other_year = first.year != last.year
    if str(settings.get("date_format", "")).startswith("DD"):
        return f"{first.day} {start}{f' {first.year}' if other_year else ''} – {last.day} {end} {last.year}"
    return f"{start} {first.day}{f', {first.year}' if other_year else ''} – {end} {last.day}, {last.year}"


# --------------------------------------------------------------------------- data


def _household_events(ctx, first: _dt.date, last: _dt.date, mine: bool, member_id=None) -> list:
    """Events for paper: household-wide ones only, unless --mine (direct chat) adds the person's own."""
    occs = events.agenda(ctx, first, last, member_id)
    if mine and not ctx.viewer.group:
        return occs
    every = ctx.household.data("calendar")["events"]
    allowed = {e["id"] for e in every if e.get("visibility", "household") == "household"}
    return [o for o in occs if o["event"] in allowed]


def week_data(ctx, first: _dt.date, with_chores: bool = True, mine: bool = False, member_id=None) -> dict:
    hh = ctx.household
    last = first + _dt.timedelta(days=6)
    viewer = ctx.viewer
    days = []
    occs = _household_events(ctx, first, last, mine, member_id) if viewer.sees("calendar") else []
    plan = hh.data("mealplan")["plan"] if viewer.sees("meal_plan") else {}
    by_id = {r["id"]: r for r in hh.data("recipes")["recipes"]}
    for day in _dates(first, 7):
        iso = day.isoformat()
        dinners = [mealplan.entry_label(hh, iso, "dinner", e, by_id) for e in plan.get(iso, {}).get("dinner", [])]
        days.append({"date": iso, "heading": _day_heading(day, hh.settings),
                     "events": [o for o in occs if o["date"] <= iso <= (o.get("end_date") or o["date"])],
                     "dinner": ", ".join(dinners) or None})  # fmt: skip
    out = {"first": first.isoformat(), "last": last.isoformat(), "days": days, "chores": [], "stars": [], "notes": []}
    if with_chores and viewer.sees("todos"):
        projected = todos.project_chores(hh, todos.kid_level(ctx, hh.data("todos")), first, last)
        for member in hh.members:
            mine_ = [c for c in projected if c["member_id"] == member["id"]]
            if mine_:
                cells = {}
                for chore in mine_:
                    cells.setdefault(chore["date"], []).append(chore["title"])
                out["chores"].append({"member": member["name"], "color": member["color"], "days": cells})
        unassigned = [c for c in projected if not c["member_id"]]
        if unassigned:
            cells = {}
            for chore in unassigned:
                cells.setdefault(chore["date"], []).append(chore["title"])
            out["chores"].append({"member": "Anyone", "color": "#8D8F94", "days": cells})
        out["stars"] = [{"member": m["name"], "stars": int(m.get("stars", 0))} for m in hh.members
                        if access.is_minor(m)]  # fmt: skip
    if viewer.sees("notes"):
        out["notes"] = [{"title": n["title"], "body": n.get("body") or ""}
                        for n in hh.data("notes")["notes"] if n.get("pinned") and n.get("visibility") == "shared"
                        and not n.get("sensitive")][:4]  # fmt: skip
    return out


# --------------------------------------------------------------------------- the fridge sheet / week calendar


def _event_line(occ: dict, settings: dict) -> str:
    when = "" if occ["all_day"] else events.fmt_time(occ["time"], settings) + " "
    who = f" ({', '.join(occ['members'])})" if occ.get("members") else ""
    return f"{when}{occ['title']}{who}"


def _chore_lines(sheet, titles: list, width: float, room: int) -> list:
    """(tick box?, text) lines for one day's chores: each chore on up to two lines when they all fit, else one
    shortened line each, else the first few and "+N more"."""
    full = [sheet.lines(title, "F1", 7, width, 2) for title in titles]
    if sum(len(lines) for lines in full) <= room:
        return [(n == 0, line) for lines in full for n, line in enumerate(lines)]
    if len(titles) <= room:
        return [(True, sheet.fit(title, "F1", 7, width)) for title in titles]
    shown = [(True, sheet.fit(title, "F1", 7, width)) for title in titles[: room - 1]]
    return shown + [(False, f"+{len(titles) - len(shown)} more")]


def draw_week(hh, data: dict, title: str, path, with_chores: bool) -> None:
    paper = hh.settings.get("paper", "a4")
    sheet = Sheet(paper, landscape=True, title=title)
    first = _dt.date.fromisoformat(data["first"])
    last = _dt.date.fromisoformat(data["last"])
    top = sheet.header(title, hh.name, _span_text(first, last, hh.settings))
    col_w = (sheet.w - 2 * sheet.m) / 7
    rows = data["chores"] if with_chores else []
    extra = (14 if data["stars"] else 0) + (24 if data["notes"] else 0) + 40
    per_line = 9.5
    name_w = 70
    cell_w = (sheet.w - 2 * sheet.m - name_w) / 7

    def cells(row, room):
        return [_chore_lines(sheet, row["days"].get(day["date"], []), cell_w - 15, room) for day in data["days"]]

    def row_h(row, room):
        return max(18, 4 + max(len(lines) for lines in cells(row, room)) * per_line)

    room = 4  # lines per chore cell, fewer when there are many rows
    room_for_chores = sheet.h - top - 16 - 120 - 22 - extra  # keep at least 120pt of calendar
    while room > 1 and rows and 24 + sum(row_h(r, room) for r in rows) > room_for_chores:
        room -= 1
    chores_h = (24 + sum(row_h(r, room) for r in rows)) if rows else 0
    grid_h = max(120, min(sheet.h * 0.45, sheet.h - top - 16 - 22 - chores_h - extra)) if with_chores else (
        sheet.h - top - 60)  # fmt: skip
    step = 9.0  # between the wrapped lines of one event
    for index, day in enumerate(data["days"]):
        x = sheet.m + index * col_w
        sheet.c.rect(x, top, col_w, 16, fill=pdf.tint(ACCENT, 0.85), stroke=RULE)
        sheet.text(x + 4, top + 11.5, day["heading"], font="F2", size=9, color=ACCENT)
        sheet.c.rect(x, top + 16, col_w, grid_h, stroke=RULE)
        dinner = sheet.lines("Dinner: " + day["dinner"], "F3", 7.5, col_w - 8, 2) if day["dinner"] else []
        bottom = top + 16 + grid_h - 5  # the last line in the box
        floor = bottom - len(dinner) * step - 3 if dinner else bottom  # events stay above the dinner
        y = top + 28
        for most in (6, 3, 2, 1):  # a busy day shows every event on fewer lines before hiding any
            blocks = [(occ.get("color") or ACCENT, sheet.lines(_event_line(occ, hh.settings), "F1", 7.5, col_w - 15,
                                                               most)) for occ in day["events"]]  # fmt: skip
            fits = y - 3 - step + sum(len(lines) * step + 1.5 for _, lines in blocks) <= floor
            if fits:
                break
        for n, (color, lines) in enumerate(blocks):
            if not fits and y + len(lines) * step > floor:  # keep a line for "+N more"
                sheet.text(x + 11, y - 1.5, f"+{len(blocks) - n} more", font="F3", size=7, color=MUTED)
                break
            sheet.c.rect(x + 4, y - 6, 4, 4, fill=color)
            for i, line in enumerate(lines):
                sheet.text(x + 11, y - 1.5 + i * step, line, size=7.5)
            y += len(lines) * step + 1.5
        for i, line in enumerate(dinner):
            sheet.text(x + 4, bottom - (len(dinner) - 1 - i) * step, line, font="F3", size=7.5, color=MUTED)
    y = top + 16 + grid_h + 22
    if with_chores and data["chores"]:
        sheet.text(sheet.m, y, "Chores", font="F2", size=12, color=ACCENT)
        for index, day in enumerate(data["days"]):  # its columns are narrower than the calendar's: label them
            sheet.text(sheet.m + name_w + index * cell_w + 3, y, day["heading"], font="F2", size=7, color=ACCENT)
        y += 8
        for row in data["chores"]:
            height = row_h(row, room)
            sheet.c.rect(sheet.m, y, sheet.w - 2 * sheet.m, height, stroke=RULE)
            sheet.c.rect(sheet.m, y, 4, height, fill=row["color"])
            sheet.text(sheet.m + 8, y + 11, sheet.fit(row["member"], "F2", 9, name_w - 10), font="F2", size=9)
            for index, lines in enumerate(cells(row, room)):
                cx = sheet.m + name_w + index * cell_w
                sheet.c.line(cx, y, cx, y + height, color=RULE)
                for n, (box, text) in enumerate(lines):
                    cy = y + 5 + n * per_line
                    if box:
                        sheet.c.rect(cx + 3, cy, 6, 6, stroke=INK, line_width=0.5)
                    sheet.text(cx + 12, cy + 5.5, text, size=7)
            y += height
        y += 14
    if data["stars"]:
        stars = ", ".join(f"{s['member']} {s['stars']}" for s in data["stars"])
        sheet.text(sheet.m, y, f"Stars: {stars}", font="F2", size=9, color=ACCENT)
        y += 14
    if data["notes"] and y < sheet.h - 50:
        text = " · ".join(f"{n['title']}: {n['body']}" if n["body"] else n["title"] for n in data["notes"])
        for line in sheet.lines("Pinned: " + text, "F1", 8, sheet.w - 2 * sheet.m, 2):
            sheet.text(sheet.m, y, line, size=8, color=MUTED)
            y += 10
    sheet.footer(f"Made with Fridge Door · {_printed(hh)}")
    sheet.save(path)


def week_html(hh, data: dict, title: str, with_chores: bool) -> str:
    head = "".join(f"<th scope='col'>{_e(d['heading'])}</th>" for d in data["days"])
    cells = []
    for day in data["days"]:
        items = "".join(f"<div><span class='dot' style='background:{_e(o.get('color') or ACCENT)}'></span>"
                        f"{_e(o['icon'])} {_e(_event_line(o, hh.settings))}</div>" for o in day["events"])  # fmt: skip
        dinner = f"<div class='muted'><em>Dinner: {_e(day['dinner'])}</em></div>" if day["dinner"] else ""
        cells.append(f"<td>{items or '<span class=muted>—</span>'}{dinner}</td>")
    span = _span_text(_dt.date.fromisoformat(data["first"]), _dt.date.fromisoformat(data["last"]), hh.settings)
    body = (f"<h1>{_e(title)}</h1><p class='sub'>{_e(hh.name)} · {_e(span)}</p>"
            f"<table><thead><tr>{head}</tr></thead><tbody><tr>{''.join(cells)}</tr></tbody></table>")  # fmt: skip
    if with_chores and data["chores"]:
        rows = []
        for row in data["chores"]:
            tds = "".join("<td>" + "".join(f"<div><span class='box'></span>{_e(t)}</div>"
                                            for t in row["days"].get(d["date"], [])) + "</td>" for d in data["days"])  # fmt: skip
            rows.append(f"<tr><th scope='row'><span class='dot' style='background:{_e(row['color'])}'></span>"
                        f"{_e(row['member'])}</th>{tds}</tr>")  # fmt: skip
        body += (f"<h2>Chores</h2><table><thead><tr><th></th>{head}</tr></thead><tbody>{''.join(rows)}</tbody>"
                 "</table>")  # fmt: skip
    if data["stars"]:
        body += "<p><strong>Stars:</strong> " + ", ".join(f"{_e(s['member'])} {'★' * min(s['stars'], 20)} {s['stars']}"
                                                          for s in data["stars"]) + "</p>"  # fmt: skip
    if data["notes"]:
        body += "<h2>Pinned</h2><ul>" + "".join(f"<li><strong>{_e(n['title'])}</strong> {_e(n['body'])}</li>"
                                               for n in data["notes"]) + "</ul>"  # fmt: skip
    return _page_html(title, body, landscape=True, paper=hh.settings.get("paper", "a4"), printed=_printed(hh))


def _strings_week(data: dict) -> list:
    out = [d["dinner"] for d in data["days"]]
    for d in data["days"]:
        out += [o["title"] for o in d["events"]] + [m for o in d["events"] for m in o.get("members", [])]
    for row in data["chores"]:
        out.append(row["member"])
        out += [t for titles in row["days"].values() for t in titles]
    out += [n["title"] + " " + n["body"] for n in data["notes"]]
    return out


# --------------------------------------------------------------------------- month calendar


def month_data(ctx, first: _dt.date, member_id=None, mine: bool = False) -> dict:
    hh = ctx.household
    week_start = todos.week_start(hh)
    last = (first.replace(day=28) + _dt.timedelta(days=4)).replace(day=1) - _dt.timedelta(days=1)
    grid_first = first - _dt.timedelta(days=(first.weekday() - week_start) % 7)
    grid_last = last + _dt.timedelta(days=(week_start - last.weekday() - 1) % 7)
    occs = _household_events(ctx, grid_first, grid_last, mine, member_id)
    weeks, day = [], grid_first
    while day <= grid_last:
        week = []
        for _ in range(7):
            iso = day.isoformat()
            week.append({"date": iso, "day": day.day, "in_month": day.month == first.month,
                         "events": [o for o in occs if o["date"] <= iso <= (o.get("end_date") or o["date"])]})  # fmt: skip
            day += _dt.timedelta(days=1)
        weeks.append(week)
    used = {m for o in occs for m in o.get("members", [])}
    legend = [{"member": m["name"], "color": m["color"]} for m in hh.members if m["name"] in used]
    heads = [DAY_NAMES[(week_start + i) % 7] for i in range(7)]
    return {"month": f"{MONTH_NAMES[first.month - 1]} {first.year}", "weeks": weeks, "legend": legend, "heads": heads}


def draw_month(hh, data: dict, path) -> None:
    sheet = Sheet(hh.settings.get("paper", "a4"), landscape=True, title=data["month"])
    top = sheet.header(data["month"], hh.name)
    x = sheet.w - sheet.m
    for item in reversed(data["legend"]):
        width = pdf.text_width(pdf_text(item["member"]), "F1", 8) + 14
        x -= width
        sheet.c.rect(x, sheet.m + 24, 7, 7, fill=item["color"])
        sheet.text(x + 10, sheet.m + 30, item["member"], size=8, color=MUTED)
    col_w = (sheet.w - 2 * sheet.m) / 7
    for i, name in enumerate(data["heads"]):
        sheet.text(sheet.m + i * col_w + 4, top + 2, name, font="F2", size=9, color=ACCENT)
    top += 8
    rows = len(data["weeks"])
    cell_h = (sheet.h - top - 34) / rows
    for r, week in enumerate(data["weeks"]):
        for c, day in enumerate(week):
            x0, y0 = sheet.m + c * col_w, top + r * cell_h
            sheet.c.rect(x0, y0, col_w, cell_h, stroke=RULE, fill=None if day["in_month"] else (0.97, 0.97, 0.98))
            sheet.text(x0 + 4, y0 + 11, str(day["day"]), font="F2", size=9, color=INK if day["in_month"] else MUTED)
            room = int((cell_h - 16) // 9)
            items = day["events"]
            most = 2 if sum(len(sheet.lines(_event_line(o, hh.settings), "F1", 6.8, col_w - 11, 2))
                            for o in items) <= room else 1  # fmt: skip
            shown = items if len(items) <= room else items[: max(0, room - 1)]
            y = y0 + 22
            for occ in shown:
                sheet.c.rect(x0 + 3, y - 6.5, 2, 7, fill=occ.get("color") or ACCENT)
                for line in sheet.lines(_event_line(occ, hh.settings), "F1", 6.8, col_w - 11, most):
                    sheet.text(x0 + 8, y - 0.5, line, size=6.8)
                    y += 9
            if len(shown) < len(items):
                sheet.text(x0 + 8, y - 0.5, f"+{len(items) - len(shown)} more", font="F3", size=6.5, color=MUTED)
    sheet.footer(f"Made with Fridge Door · {_printed(hh)}")
    sheet.save(path)


def month_html(hh, data: dict) -> str:
    head = "".join(f"<th scope='col'>{_e(h)}</th>" for h in data["heads"])
    rows = []
    for week in data["weeks"]:
        tds = []
        for day in week:
            items = "".join(f"<div><span class='dot' style='background:{_e(o.get('color') or ACCENT)}'></span>"
                            f"{_e(_event_line(o, hh.settings))}</div>" for o in day["events"])  # fmt: skip
            style = "" if day["in_month"] else " class='muted'"
            tds.append(f"<td{style}><strong>{day['day']}</strong>{items}</td>")
        rows.append(f"<tr>{''.join(tds)}</tr>")
    legend = " ".join(f"<span class='dot' style='background:{_e(i['color'])}'></span>{_e(i['member'])}"
                      for i in data["legend"])  # fmt: skip
    body = (f"<h1>{_e(data['month'])}</h1><p class='sub'>{_e(hh.name)} {legend}</p>"
            f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>")  # fmt: skip
    return _page_html(data["month"], body, landscape=True, paper=hh.settings.get("paper", "a4"), printed=_printed(hh))


# --------------------------------------------------------------------------- shopping checklist


def draw_list(hh, lst: dict, groups: list, path) -> None:
    sheet = Sheet(hh.settings.get("paper", "a4"), landscape=False, title=lst["name"])
    top = sheet.header(lst["name"], lst.get("store") or hh.name, hh.day(hh.today()))
    lines = []
    for group in groups:
        if group["aisle"]:
            lines.append(("aisle", group["aisle"]))
        for item in group["items"]:
            qty = shopping.qty_label(item.get("qty"))
            name = f"{shopping.display_name(item['name'])}{' ' + qty if qty else ''}"
            lines.append(("item", name, item.get("note")))
    per_col = int((sheet.h - top - 50) // 15)
    cols = 2 if len(lines) > per_col else 1
    col_w = (sheet.w - 2 * sheet.m) / cols
    laid = []  # a note that doesn't fit beside its item goes on the line below, in small type
    for kind, text, *note in lines:
        note = note[0] if note else None
        whole = f"{text} ({note})" if note else text
        if kind == "item" and note and pdf.text_width(pdf_text(whole), "F1", 10) > col_w - 24:
            laid += [("item", text), ("note", note)]
        else:
            laid.append((kind, whole))
    lines = laid
    for index, (kind, text) in enumerate(lines[: per_col * cols]):
        col, row = divmod(index, per_col)
        x, y = sheet.m + col * col_w, top + row * 15
        if kind == "aisle":
            sheet.text(x, y + 10, text, font="F2", size=10, color=ACCENT)
        elif kind == "note":
            sheet.text(x + 17, y + 8, sheet.fit(text, "F3", 8, col_w - 24), font="F3", size=8, color=MUTED)
        else:
            sheet.c.rect(x + 2, y + 2, 9, 9, stroke=INK, line_width=0.6)
            sheet.text(x + 17, y + 10, sheet.fit(text, "F1", 10, col_w - 24), size=10)
    if len(lines) > per_col * cols:
        sheet.text(sheet.m, sheet.h - 34, f"+{len(lines) - per_col * cols} more on the list", font="F3", size=8,
                   color=MUTED)  # fmt: skip
    sheet.footer(f"Made with Fridge Door · {_printed(hh)}")
    sheet.save(path)


def list_html(hh, lst: dict, groups: list) -> str:
    parts = []
    for group in groups:
        if group["aisle"]:
            parts.append(f"<h3>{_e(group['aisle'])}</h3>")
        for item in group["items"]:
            qty = shopping.qty_label(item.get("qty"))
            parts.append(f"<div><label><input type='checkbox'> {_e(shopping.display_name(item['name']))}"
                         f"{' ' + _e(qty) if qty else ''}{' (' + _e(item['note']) + ')' if item.get('note') else ''}"
                         "</label></div>")  # fmt: skip
    body = f"<h1>{_e(lst['name'])}</h1><p class='sub'>{_e(lst.get('store') or hh.name)}</p><div class='cols'>" \
           + "".join(parts) + "</div>"  # fmt: skip
    return _page_html(lst["name"], body, paper=hh.settings.get("paper", "a4"), printed=_printed(hh))


# --------------------------------------------------------------------------- recipe card


def draw_recipe(hh, recipe: dict, parts: list, servings, path) -> None:
    sheet = Sheet(hh.settings.get("paper", "a4"), landscape=False, title=recipe["title"])
    facts = []
    if servings or recipe.get("servings"):
        facts.append(f"Serves {servings or recipe['servings']}")
    for key, label in (("prep_min", "prep"), ("cook_min", "cook"), ("total_min", "total")):
        if recipe.get(key):
            facts.append(f"{recipe[key]} min {label}")
    top = sheet.header(recipe["title"], " · ".join(facts) or hh.name)
    sheet.text(sheet.m, top + 4, "Ingredients", font="F2", size=12, color=ACCENT)
    top += 14
    col_w = (sheet.w - 2 * sheet.m) / 2
    lines = [ingredients.describe(p) for p in parts]
    half = (len(lines) + 1) // 2
    for index, line in enumerate(lines):
        col, row = (0, index) if index < half else (1, index - half)
        sheet.text(sheet.m + col * col_w, top + 12 + row * 13, sheet.fit("• " + line, "F1", 10, col_w - 10), size=10)
    y = top + 24 + half * 13
    sheet.text(sheet.m, y, "Steps", font="F2", size=12, color=ACCENT)
    y += 16
    for number, step in enumerate(recipe.get("steps", []), 1):
        wrapped = sheet.wrap(step, "F1", 10, sheet.w - 2 * sheet.m - 20)
        if y + 13 * len(wrapped) > sheet.h - 40:
            sheet.footer("Made with Fridge Door")
            sheet.new_page()
            y = sheet.m + 10
        sheet.text(sheet.m, y, f"{number}.", font="F2", size=10, color=ACCENT)
        for line in wrapped:
            sheet.text(sheet.m + 20, y, line, size=10)
            y += 13
        y += 4
    if recipe.get("notes") and y < sheet.h - 60:
        for line in sheet.wrap("Notes: " + recipe["notes"], "F3", 9, sheet.w - 2 * sheet.m)[:4]:
            sheet.text(sheet.m, y + 6, line, font="F3", size=9, color=MUTED)
            y += 12
    sheet.footer("Made with Fridge Door" + (f" · from {recipe['source_url']}" if recipe.get("source_url") else ""))
    sheet.save(path)


def recipe_html(hh, recipe: dict, parts: list, servings) -> str:
    items = "".join(f"<li>{_e(ingredients.describe(p))}</li>" for p in parts)
    steps = "".join(f"<li>{_e(s)}</li>" for s in recipe.get("steps", []))
    serves = servings or recipe.get("servings")
    body = (f"<h1>{_e(recipe['title'])}</h1><p class='sub'>{'Serves ' + str(serves) if serves else ''}"
            f"{' · ' + str(recipe['total_min']) + ' min' if recipe.get('total_min') else ''}</p>"
            f"<h2>Ingredients</h2><ul class='cols'>{items}</ul><h2>Steps</h2><ol>{steps}</ol>"
            + (f"<p class='muted'><em>{_e(recipe['notes'])}</em></p>" if recipe.get("notes") else ""))  # fmt: skip
    return _page_html(recipe["title"], body, paper=hh.settings.get("paper", "a4"), printed=_printed(hh))


# --------------------------------------------------------------------------- budget report


def budget_data(hh, first: _dt.date, last: _dt.date) -> dict:
    data = hh.data("budget")
    summary = budget.month_summary(hh, data, first, last)
    trend = []
    for back in range(5, -1, -1):
        month_first = add_months(first, -back)
        month_last = add_months(month_first, 1) - _dt.timedelta(days=1)
        total = sum(budget.spent_by_category(data, month_first, month_last).values(), Decimal(0))
        trend.append({"month": month_first.strftime("%b"), "total": total})
    goals = [budget.goal_view(hh, g) for g in data["goals"]]
    return {"summary": summary, "trend": trend, "goals": goals, "title": f"Budget — {MONTH_NAMES[first.month - 1]} "
                                                                           f"{first.year}"}  # fmt: skip


def draw_budget(hh, data: dict, path) -> None:
    d = budget.disp(hh)
    sheet = Sheet(hh.settings.get("paper", "a4"), landscape=False, title=data["title"])
    s = data["summary"]
    line = f"Spent {s['spent_text']}"
    if s["budgeted"]:
        line += (f"; {s['spent_in_budgets_text']} of {s['budgeted_text']} budgeted"
                 + (f", {s['over_by_text']} over" if s["over_by_text"] else f", {s['left_text']} left"))  # fmt: skip
    top = sheet.header(data["title"], hh.name + " · private household budget")
    sheet.text(sheet.m, top + 4, line, font="F2", size=11)
    y = top + 24
    widths = (150, 80, 80, 80)
    heads = ("Category", "Budget", "Spent", "Left")
    x = sheet.m
    for head, width in zip(heads, widths):
        sheet.text(x, y, head, font="F2", size=9, color=MUTED, align="left" if head == "Category" else "left")
        x += width
    sheet.text(sheet.m + sum(widths) + 6, y, "Spent vs budget", font="F2", size=9, color=MUTED)
    y += 6
    bar_x, bar_w = sheet.m + sum(widths) + 6, sheet.w - 2 * sheet.m - sum(widths) - 6
    for row in s["rows"]:
        if not row["spent"] and row["budget"] is None:
            continue
        y += 16
        sheet.c.line(sheet.m, y + 4, sheet.w - sheet.m, y + 4, color=RULE, width=0.4)
        values = (row["category"], money.fmt(row["budget"], d) if row["budget"] is not None else "—", row["spent_text"],
                  row.get("left_text") or "—")  # fmt: skip
        x = sheet.m
        for value, width in zip(values, widths):
            color = WARN if value == row.get("left_text") and row.get("over") else INK
            sheet.text(x, y, sheet.fit(value, "F1", 9, width - 6), size=9, color=color)
            x += width
        if row["budget"]:
            ratio = min(Decimal(1), row["spent"] / row["budget"]) if row["budget"] else Decimal(1)
            sheet.c.rect(bar_x, y - 8, bar_w, 9, fill=(0.91, 0.92, 0.94))
            sheet.c.rect(bar_x, y - 8, float(bar_w * float(ratio)), 9, fill=WARN if row.get("over") else ACCENT)
    y += 34
    sheet.text(sheet.m, y, "Last 6 months", font="F2", size=12, color=ACCENT)
    chart_top, chart_h = y + 24, 110
    peak = max((m["total"] for m in data["trend"]), default=Decimal(0)) or Decimal(1)
    slot = (sheet.w - 2 * sheet.m) / len(data["trend"])
    for i, month in enumerate(data["trend"]):
        height = float(chart_h * float(month["total"] / peak))
        x0 = sheet.m + i * slot + slot * 0.25
        fill = ACCENT if i == 5 else pdf.tint(ACCENT, 0.5)
        sheet.c.rect(x0, chart_top + chart_h - height, slot * 0.5, height, fill=fill)
        sheet.text(x0 + slot * 0.25, chart_top + chart_h + 12, month["month"], size=8, color=MUTED, align="center")
        sheet.text(x0 + slot * 0.25, chart_top + chart_h - height - 4, money.fmt(month["total"], d), size=7,
                   color=INK, align="center")  # fmt: skip
    y = chart_top + chart_h + 40
    if data["goals"]:
        sheet.text(sheet.m, y, "Savings goals", font="F2", size=12, color=ACCENT)
        y += 8
        for goal in data["goals"]:
            y += 20
            sheet.text(sheet.m, y, sheet.fit(goal["name"], "F1", 10, 150), size=10)
            sheet.c.rect(sheet.m + 160, y - 9, 200, 10, fill=(0.91, 0.92, 0.94))
            sheet.c.rect(sheet.m + 160, y - 9, 2 * min(100, goal["percent"]), 10, fill=OK)
            sheet.text(sheet.m + 370, y, f"{goal['saved_text']} of {goal['target_text']} ({goal['percent']}%)", size=9)
    sheet.footer(f"Made with Fridge Door · {_printed(hh)} · private: keep off the fridge")
    sheet.save(path)


def budget_html(hh, data: dict) -> str:
    d = budget.disp(hh)
    s = data["summary"]
    rows = []
    for row in s["rows"]:
        if not row["spent"] and row["budget"] is None:
            continue
        pct = min(100, row.get("percent") or 0)
        bar = (f"<div class='bar'><span class='{'over' if row.get('over') else ''}' style='width:{pct}%'></span></div>"
               if row["budget"] else "")  # fmt: skip
        planned = _e(money.fmt(row["budget"], d)) if row["budget"] is not None else "—"
        rows.append(f"<tr><td>{_e(row['category'])}</td><td>{planned}</td><td>{_e(row['spent_text'])}</td>"
                    f"<td>{_e(row.get('left_text') or '—')}</td><td>{bar}</td></tr>")  # fmt: skip
    trend = "".join(f"<tr><td>{_e(m['month'])}</td><td>{_e(money.fmt(m['total'], d))}</td></tr>" for m in data["trend"])
    goals = "".join(f"<tr><td>{_e(g['name'])}</td><td><div class='bar'><span style='width:{min(100, g['percent'])}%'>"
                    f"</span></div></td><td>{_e(g['saved_text'])} of {_e(g['target_text'])}</td></tr>" for g in data["goals"])  # fmt: skip
    body = (f"<h1>{_e(data['title'])}</h1><p class='sub'>{_e(hh.name)} · private household budget · spent "
            f"{_e(s['spent_text'])}</p><table><thead><tr><th>Category</th><th>Budget</th><th>Spent</th><th>Left</th>"
            f"<th>Spent vs budget</th></tr></thead><tbody>{''.join(rows)}</tbody></table><h2>Last 6 months</h2>"
            f"<table><tbody>{trend}</tbody></table>" + (f"<h2>Savings goals</h2><table><tbody>{goals}</tbody></table>"
                                                         if goals else ""))  # fmt: skip
    return _page_html(data["title"], body, paper=hh.settings.get("paper", "a4"), printed=_printed(hh))


# --------------------------------------------------------------------------- commands


def _out(ctx, name: str, fmt: str, draw, html_text: str, strings, landscape: bool) -> dict:
    """Write the printout in the folder for the chat it's made in (Household.output_for): a person's own folder, or
    a group chat's, so a sheet made for the kids' group never overwrites one made for a parent."""
    folder = ctx.household.output_for(ctx.member["id"], ctx.chat_id if ctx.viewer.group else None)
    return write(folder, name, fmt, draw, html_text, strings, landscape=landscape)


def forget_member(hh, member_id: str) -> list:
    """A member's own printouts go with them."""
    folder = hh.output_dir() / "private" / member_id
    if folder.is_dir():
        shutil.rmtree(folder, ignore_errors=True)
        return ["deleted their own printouts"]
    return []


def cmd_week(ctx, args) -> dict:
    hh = ctx.household
    day = mealplan._date(hh, args.date)
    first = mealplan.week_of(hh, day)
    data = week_data(ctx, first, with_chores=True)
    title = "This week"
    result = _out(ctx, f"fridge-sheet-{first.isoformat()}", args.format, lambda p: draw_week(hh, data, title, p, True),
                  week_html(hh, data, title, True), _strings_week(data), True)  # fmt: skip
    counts = sum(len(d["events"]) for d in data["days"])
    summary = f"The fridge sheet for the week of {hh.day(first)} is ready ({plural(counts, 'event')}, "
    summary += f"{plural(len(data['chores']), 'chore row')})."
    return dict(result, summary=summary)


def cmd_calendar(ctx, args) -> dict:
    hh = ctx.household
    ctx.viewer.require("calendar", "view", "print the calendar")
    ctx.viewer.require_sees("calendar")
    member_id = None
    if args.who:
        from .context import find_member

        member_id = find_member(hh, args.who)["id"]
    if args.mine and ctx.viewer.group:
        raise ToolError("--mine only works in a direct chat.", code="direct_chat_only")
    if args.week:
        first = mealplan.week_of(hh, mealplan._date(hh, args.week))
        data = week_data(ctx, first, with_chores=False, mine=args.mine, member_id=member_id)
        title = "Week of " + hh.day(first)
        result = _out(ctx, f"calendar-week-{first.isoformat()}", args.format,
                      lambda p: draw_week(hh, data, title, p, False), week_html(hh, data, title, False),
                      _strings_week(data), True)  # fmt: skip
        return dict(result, summary=f"The calendar for the week of {hh.day(first)} is ready.")
    first, _ = budget.parse_month(hh, args.month)
    data = month_data(ctx, first, member_id, args.mine)
    strings = [o["title"] for w in data["weeks"] for d in w for o in d["events"]]
    strings += [i["member"] for i in data["legend"]]
    result = _out(ctx, f"calendar-{first.strftime('%Y-%m')}", args.format, lambda p: draw_month(hh, data, p),
                  month_html(hh, data), strings, True)  # fmt: skip
    return dict(result, summary=f"The {data['month']} calendar is ready.")


def cmd_list(ctx, args) -> dict:
    hh = ctx.household
    shop = hh.data("shopping")
    lst = shopping.find_list(ctx, shop, args.list)
    open_items = shopping.items_of(shop, lst["id"], crossed=False)
    groups = shopping.group_by_aisle(lst, open_items)
    strings = [lst["name"], lst.get("store")] + [i["name"] + " " + (i.get("note") or "") for i in open_items]
    result = _out(ctx, f"list-{_safe(lst['name'])}", args.format, lambda p: draw_list(hh, lst, groups, p),
                  list_html(hh, lst, groups), strings, False)  # fmt: skip
    return dict(result, summary=f"A printable checklist of {lst['name']} is ready ({plural(len(open_items), 'item')}).")


def cmd_recipe(ctx, args) -> dict:
    hh = ctx.household
    recipe = recipes.find_recipe(ctx, hh.data("recipes"), args.recipe)
    parts, _ = recipes.scaled(recipe, args.servings)
    strings = [recipe["title"], recipe.get("notes")] + recipe.get("steps", []) + [p.get("item") for p in parts]
    page = recipe_html(hh, recipe, parts, args.servings)
    result = _out(ctx, f"recipe-{_safe(recipe['title'])}", args.format,
                  lambda p: draw_recipe(hh, recipe, parts, args.servings, p), page, strings, False)  # fmt: skip
    return dict(result, summary=f"The recipe card for {recipe['title']} is ready.")


def cmd_budget(ctx, args) -> dict:
    hh = ctx.household
    ctx.viewer.require("budget", "view", "print the budget")
    ctx.viewer.require_sees("budget")
    if ctx.viewer.group:
        raise ToolError("The budget report is made in a direct chat only.", hint="Ask for it in a direct chat.",
                        code="direct_chat_only")  # fmt: skip
    first, last = budget.parse_month(hh, args.month)
    data = budget_data(hh, first, last)
    strings = [r["category"] for r in data["summary"]["rows"]] + [g["name"] for g in data["goals"]]
    result = _out(ctx, f"budget-{first.strftime('%Y-%m')}", args.format, lambda p: draw_budget(hh, data, p),
                  budget_html(hh, data), strings, False)  # fmt: skip
    month = data["summary"]["month_name"]
    return dict(result, summary=f"The budget report for {month} is ready (private: not for the fridge).")


def register(cli) -> None:
    from .members import FORGET_HOOKS

    FORGET_HOOKS.append(forget_member)
    grp = cli.group("print", "Printables: fridge sheet, calendar, shopping checklist, recipe card, budget report.")
    common = {"choices": ("pdf", "html", "both"), "default": "pdf", "help": "pdf (default), html or both"}
    p = grp.add("week", "The one-page \"this week\" fridge sheet: household events, dinners, chores with tick boxes, "
                "kids' stars and pinned notes (nothing private).", ["fridge print week", "fridge print week "
                "--date \"next week\" --format both"], cmd_week)  # fmt: skip
    p.add_argument("--date", help="Any day in the week (default this week)")
    p.add_argument("--format", **common)
    p = grp.add("calendar", "A month (or --week) calendar in member colours; --for one member; --mine adds your own "
                "private events (direct chat).", ["fridge print calendar", "fridge print calendar --month 2026-11 "
                "--for Lily", "fridge print calendar --week tomorrow"], cmd_calendar)  # fmt: skip
    p.add_argument("--month", help="YYYY-MM (default this month)")
    p.add_argument("--week", help="Print a week instead (any day in it)")
    p.add_argument("--for", dest="who")
    p.add_argument("--mine", action="store_true")
    p.add_argument("--format", **common)
    p = grp.add("list", "A shopping checklist with tick boxes, by aisle.", ["fridge print list", "fridge print list "
                "--list Hardware"], cmd_list)  # fmt: skip
    p.add_argument("--list")
    p.add_argument("--format", **common)
    p = grp.add("recipe", "A recipe card (scaled with --servings).", ['fridge print recipe Chili --servings 6'],
                cmd_recipe)  # fmt: skip
    p.add_argument("recipe")
    p.add_argument("--servings", type=servings_arg)
    p.add_argument("--format", **common)
    p = grp.add("budget", "The month's budget report with charts (private).", ["fridge print budget",
                "fridge print budget --month 2026-09"], cmd_budget)  # fmt: skip
    p.add_argument("--month")
    p.add_argument("--format", **common)

