"""Notices: things a member should hear about the next time they talk, such as a task someone assigned them.

Nothing here sends a message anywhere. In a group chat the agent tells the person there and then; otherwise the
notice waits, every reply to that person flags it, and `fridge notices list` delivers it. Messaging someone
outside the current chat needs the owner's OK, every time.
"""

from __future__ import annotations

import datetime as _dt

from . import access
from .util import now_stamp, plural


def add(hh, to: str, kind: str, text: str, by: str | None, ref: str | None = None, delivered: bool = False) -> dict:
    data = hh.data("notices")
    notice = {
        "id": hh.next_id("notice"),
        "to": to,
        "kind": kind,
        "text": text,
        "ref": ref,
        "by": by,
        "at": now_stamp(),
        "delivered_at": now_stamp() if delivered else None,
    }
    data["notices"].append(notice)
    hh.touch("notices")
    return notice


# Which module each kind of notice comes from: the person must still be able to see it.
KIND_MODULE = {"task_assigned": "todos"}


def pending(hh, member_id: str) -> list:
    return [n for n in hh.data("notices")["notices"] if n["to"] == member_id and not n.get("delivered_at")]


def readable(ctx, notice: dict) -> bool:
    """A notice is shown only in a direct chat, and only while its person can still see what it's about."""
    if ctx.viewer.group:
        return False
    return ctx.viewer.can_act(KIND_MODULE.get(notice.get("kind"), "todos"), "view")


_PRIORITY_WORDS = {1: "low", 2: "medium", 3: "high"}


def assignment(hh, task: dict, assignee: dict, by: dict, viewer, turn: bool = False) -> dict:
    """Leave a notice for a newly assigned task, or (turn=True) a chore whose turn has come round to them (not for
    kids and teens, who see chores on the fridge sheet). It says when it's due and how urgent it is.

    Returns how it will reach them, for the reply."""
    if assignee["id"] == by["id"] and not turn:
        return {"notice": None, "how": "self"}
    if access.is_minor(assignee):
        return {"notice": None, "how": "fridge_sheet"}
    here = viewer.group and assignee["id"] in viewer.audience_ids()
    title = task["title"] if len(task["title"]) <= 180 else task["title"][:179] + "…"
    text = f"Your turn: {title}" if turn else f"New task from {by['name']}: {title}"
    if task.get("due"):
        text += f", due {hh.day(_dt.date.fromisoformat(task['due']))}"
    if _PRIORITY_WORDS.get(int(task.get("priority") or 0)):
        text += f" ({_PRIORITY_WORDS[int(task['priority'])]} priority)"
    note = add(hh, assignee["id"], "chore_turn" if turn else "task_assigned", text, by["id"], ref=task["id"],
               delivered=here)  # fmt: skip
    return {"notice": note["id"], "how": "in_this_chat" if here else "next_time_they_talk"}


def withdraw(hh, ref: str) -> int:
    """Take back notices about a task that's gone (an undone chore's next turn), unless they were read already."""
    data = hh.data("notices")
    before = len(data["notices"])
    data["notices"] = [n for n in data["notices"] if n.get("ref") != ref or n.get("delivered_at")]
    if len(data["notices"]) != before:
        hh.touch("notices")
    return before - len(data["notices"])


def forget_member(hh, member_id: str) -> list:
    data = hh.data("notices")
    before = len(data["notices"])
    data["notices"] = [n for n in data["notices"] if n["to"] != member_id]
    for notice in data["notices"]:
        if notice.get("by") == member_id:
            notice["by"] = None
    if before != len(data["notices"]) or data["notices"]:
        hh.touch("notices")
    return []


def cmd_list(ctx, args) -> dict:
    hh = ctx.household
    if ctx.viewer.group:
        count = len(pending(hh, ctx.member["id"]))
        return {
            "count": count,
            "summary": f"{ctx.member['name']} has {plural(count, 'new notice')}; they're shown in a direct chat only.",
        }
    with hh.transaction():
        data = hh.data("notices")
        mine = [n for n in data["notices"] if n["to"] == ctx.member["id"] and readable(ctx, n)]
        waiting = [n for n in mine if not n.get("delivered_at")]
        shown = mine if args.all else waiting
        if waiting and not args.keep:
            stamp = now_stamp()
            for notice in waiting:
                notice["delivered_at"] = stamp
            hh.touch("notices")
    items = [{"id": n["id"], "text": n["text"], "at": n["at"], "ref": n.get("ref"),
              "new": n in waiting} for n in sorted(shown, key=lambda n: n["at"])]  # fmt: skip
    text = "\n".join(("• " if i["new"] else "  ") + i["text"] for i in items) or "Nothing new."
    return {"notices": items, "text": text,
            "summary": f"{plural(len(waiting), 'new notice')} for {ctx.member['name']}."}  # fmt: skip


def cmd_clear(ctx, args) -> dict:
    hh = ctx.household
    with hh.transaction():
        data = hh.data("notices")
        before = len(data["notices"])
        data["notices"] = [n for n in data["notices"] if not (n["to"] == ctx.member["id"] and n.get("delivered_at"))]
        hh.touch("notices")
        gone = before - len(data["notices"])
    return {"cleared": gone, "summary": f"Cleared {plural(gone, 'old notice')}."}


def register(cli) -> None:
    from .members import FORGET_HOOKS

    FORGET_HOOKS.append(forget_member)
    grp = cli.group("notices", "Notices waiting for the person talking (e.g. tasks someone assigned them).")
    p = grp.add("list", "Show the person's new notices and mark them as delivered (--keep to leave them new).",
                ["fridge notices list", "fridge notices list --all"], cmd_list)  # fmt: skip
    p.add_argument("--all", action="store_true", help="Include ones already delivered")
    p.add_argument("--keep", action="store_true", help="Don't mark them as delivered")
    grp.add("clear", "Delete the person's delivered notices.", ["fridge notices clear"], cmd_clear)
