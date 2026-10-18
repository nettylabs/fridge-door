"""Reminders: what needs saying right now, to whom, held through quiet hours, never sent twice.

The toolkit never sends anything. The agent runs `fridge remind due` on its own schedule (for example every 15
minutes) and passes each message on:
- only to adults who turned reminders on themselves (member edit --reminders on: nobody gets reminders they didn't
  ask for), and never to kids or teens: their events remind the adult who made them, as do events for adults who
  never talk with the agent;
- only in the chats each reminder lists: bills and private events only in that person's own chats, members-only
  events only in groups where everyone linked is one of its people. Someone with no chat to get one in is named in
  "nowhere" (without what it was), so the owner can register their one-to-one chat;
- inside the chat platform only, unless the owner allowed reminders outside the chat (reminders_outside_chat).
A reminder whose person is in quiet hours is held (not marked sent) and comes back once the quiet hours end, or goes
just before they begin when the thing starts before they end. A late one is still sent while the thing is ahead, and
dropped once it has started.
"""

from __future__ import annotations

import datetime as _dt

from . import access, events, members
from .access import Viewer
from .util import ToolError, and_list, get_tz, in_window, now_stamp, parse_stamp, parse_time, plural

STALE = _dt.timedelta(hours=24)
ALL_DAY_AT = "08:00"  # reminders for all-day events count back from 8am on the day
BILL_AT = "09:00"
LOOKAHEAD_DAYS = 31
KEEP_SENT_DAYS = 60
EARLY_MARGIN = _dt.timedelta(minutes=30)  # sent this long before quiet hours start, so a 15-minute routine catches it


def _local(hh, day: _dt.date, at: str) -> _dt.datetime:
    return _dt.datetime.combine(day, parse_time(at)).replace(tzinfo=get_tz(hh.tz()))


def _before(start: _dt.datetime, minutes: int) -> _dt.datetime:
    """When a reminder fires: whole days before at the same clock time (a day earlier is a day earlier, clock
    change or not); hours and minutes before in real time (12 hours before 9am the morning the clocks go back is
    10pm, not 9pm)."""
    if minutes and minutes % 1440 == 0:
        return start - _dt.timedelta(minutes=minutes)  # wall-clock arithmetic keeps the time of day
    utc = start.astimezone(_dt.timezone.utc) - _dt.timedelta(minutes=minutes)
    return utc.astimezone(start.tzinfo)


def _window(hh, member: dict, moment: _dt.datetime):
    """The quiet-hours stretch around moment, as (start, end) datetimes, or None if moment is outside it."""
    window = members.quiet_hours(member, hh.settings)
    if not window or not in_window(moment.timetz().replace(tzinfo=None), window["start"], window["end"]):
        return None
    begin_t, end_t = parse_time(window["start"]), parse_time(window["end"])
    day = moment.date()
    begin = _dt.datetime.combine(day, begin_t).replace(tzinfo=moment.tzinfo)
    if begin > moment:
        begin -= _dt.timedelta(days=1)
    finish = _dt.datetime.combine(begin.date(), end_t).replace(tzinfo=moment.tzinfo)
    if finish <= begin:
        finish += _dt.timedelta(days=1)
    return begin, finish


def quiet_until(hh, member: dict, now: _dt.datetime) -> _dt.datetime | None:
    """If the member is in quiet hours now, when they end; else None."""
    stretch = _window(hh, member, now)
    return stretch[1] if stretch else None


def _relative(hh, start: _dt.datetime, now: _dt.datetime, all_day: bool) -> str:
    """When something happens, said from now: "in 25 minutes at 9am", "today at 3pm", "tomorrow", "on Thu 22 Oct"."""
    days = (start.date() - now.date()).days
    if all_day:
        return "today" if days <= 0 else "tomorrow" if days == 1 else f"on {hh.day(start.date())}"
    clock = events.fmt_time(start.strftime("%H:%M"), hh.settings)
    minutes = int((start - now).total_seconds() // 60)
    if minutes <= 0:
        return f"now ({clock})"
    if minutes <= 90:
        return f"in {plural(minutes, 'minute')} at {clock}"
    if days == 0:
        return f"today at {clock}"
    return f"tomorrow at {clock}" if days == 1 else f"on {hh.day(start.date())} at {clock}"


def _talks_here(hh, member_id: str) -> bool:
    """Whether the person talks with the agent anywhere: as the household's direct-chat speaker, in a one-to-one chat
    of their own, or linked in a group chat."""
    if hh.hub.speaker(hh.id) == member_id:
        return True
    return any((chat.get("type") == "direct" and chat.get("member") == member_id)
               or (chat.get("type") == "group" and member_id in (chat.get("participants") or {}).values())
               for chat in hh.meta().get("chats", {}).values())  # fmt: skip


def _event_recipients(hh, event: dict) -> list:
    """Adults to remind: the adults it's for who talk with the agent; for a kid's event, or one whose adults never
    talk with the agent, the adult who added it ("remind me about Marc's dentist"); a birthday reminds every adult in
    the household except the person whose birthday it is."""
    if event.get("kind") == "birthday":
        whose = (event.get("birthday") or {}).get("member")
        return [m for m in hh.members if access.is_adult(m) and m["id"] != whose and members.wants_reminders(m)]
    adults = [hh.member(m) for m in event.get("members") or []]
    adults = [m for m in adults if m and access.is_adult(m) and members.wants_reminders(m)]
    reachable = [m for m in adults if _talks_here(hh, m["id"])]
    if reachable:
        return reachable
    owner = hh.member(event.get("owner")) if event.get("owner") else None
    if owner and access.is_adult(owner) and members.wants_reminders(owner):
        return [owner]
    return adults  # nobody else to tell: they're named in "nowhere"


def _candidates(ctx, now: _dt.datetime) -> list:
    """Every reminder that could be due now, as dicts: person, key, fire, start, all_day, what (to word it at
    send time), event or bill, the occurrence it belongs to, and the minutes before."""
    hh = ctx.household
    out = []
    first = (now - STALE).date()
    last = (now + _dt.timedelta(days=LOOKAHEAD_DAYS)).date()
    for event in hh.data("calendar")["events"]:
        if not event.get("reminders"):
            continue
        for person in _event_recipients(hh, event):
            viewer = Viewer(person)
            if not access.can(person, "calendar", "view") or not events.visible(viewer, event):
                continue
            for occ in events.occurrences(hh, event, first, last):
                day = _dt.date.fromisoformat(occ["date"])
                start = _local(hh, day, occ["time"] or ALL_DAY_AT)
                who = f" ({', '.join(occ['members'])})" if occ.get("members") else ""
                where = f" @ {occ['location']}" if occ.get("location") else ""
                for minutes in event["reminders"]:
                    out.append({"person": person, "fire": _before(start, minutes), "start": start,
                                "all_day": occ["all_day"], "minutes": minutes, "kind": "event", "record": event,
                                "occurrence": f"event:{event['id']}:{occ['original_date']}",
                                "key": f"event:{event['id']}:{occ['original_date']}:{minutes}:{person['id']}",
                                "what": (f"{occ['icon']} {occ['title']}{who}", where)})  # fmt: skip
    budget_people = [m for m in hh.members if access.is_adult(m) and access.can(m, "budget", "view")
                     and members.wants_reminders(m)]  # fmt: skip
    from .budget import bill_dues, disp
    from .money import fmt

    for bill in hh.data("budget")["bills"]:
        for due_day in bill_dues(bill, first, last):
            if due_day.isoformat() in bill.get("paid", {}):
                continue
            start = _local(hh, due_day, BILL_AT)
            amount = f" ({fmt(bill['amount'], disp(hh))})" if bill.get("amount") else ""
            auto = " (autopay)" if bill.get("autopay") else ""
            for minutes in bill.get("remind_minutes") or [4320]:
                for person in budget_people:
                    out.append({"person": person, "fire": _before(start, minutes), "start": start, "all_day": True,
                                "minutes": minutes, "kind": "bill", "record": bill,
                                "occurrence": f"bill:{bill['id']}:{due_day.isoformat()}",
                                "key": f"bill:{bill['id']}:{due_day.isoformat()}:{minutes}:{person['id']}",
                                "what": (f"💳 {bill['name']}{amount} is due", auto)})  # fmt: skip
    return out


def _text(hh, cand: dict, now: _dt.datetime, early: bool = False) -> str:
    head, tail = cand["what"]
    text = f"{head} {_relative(hh, cand['start'], now, cand['all_day'])}{tail}"
    return text + (" (sent before quiet hours start)" if early else "")


def _chats(hh, cand: dict, now: _dt.datetime) -> list:
    """Where it may be posted: the person's own registered chat(s), and (except for bills: money stays out of groups)
    group chats they're in that have no kids, where everyone linked may see it and nobody linked is in quiet hours.
    "direct" stands for an unregistered one-to-one chat with the household's speaker."""
    person = cand["person"]
    chats = hh.meta().get("chats", {})
    out = [chat_id for chat_id, chat in sorted(chats.items())
           if chat.get("type") == "direct" and chat.get("member") == person["id"]]  # fmt: skip
    if hh.hub.speaker(hh.id) == person["id"] and not out:  # their one-to-one chat, when it isn't registered
        out.append("direct")
    if cand["kind"] == "bill":
        return out
    for chat_id, chat in sorted(chats.items()):
        linked = set((chat.get("participants") or {}).values())
        if chat.get("type") != "group" or chat.get("minors_present") or person["id"] not in linked:
            continue
        audience = [m for m in (hh.member(x) for x in linked) if m]
        viewer = Viewer(person, audience, group=True)
        if events.visible(viewer, cand["record"]) and not any(quiet_until(hh, m, now) for m in audience):
            out.append(chat_id)
    return out


def due(ctx, now: _dt.datetime, only: str | None = None, mark: bool = True) -> dict:
    """What to pass on now. A reminder is sent once. One that falls in the person's quiet hours waits until they
    end, unless the thing itself starts before then: that one goes just before the quiet hours begin. One whose
    moment has passed is still sent while the thing is ahead (worded from now); once it has started, it's dropped.
    Several reminders for the same thing due at once become one. One with no chat to go to is only named, once."""
    hh = ctx.household
    sent = hh.data("notices").setdefault("sent", {})
    send, held, dropped, nowhere = [], [], [], []
    picked: dict = {}  # (person, occurrence) -> the candidate to send now
    for cand in sorted(_candidates(ctx, now), key=lambda c: c["fire"]):
        person = cand["person"]
        if (only and person["id"] != only) or cand["key"] in sent:
            continue
        fire, start, early = cand["fire"], cand["start"], False
        over = start if not cand["all_day"] else start.replace(hour=23, minute=59)
        stretch = _window(hh, person, fire)
        if stretch and start < stretch[1] and fire > now:
            early_at = stretch[0] - EARLY_MARGIN  # before they go quiet
            if early_at <= now < stretch[0]:
                fire, early = now, True
        if fire > now:
            continue
        if now >= over:
            dropped.append({"to": person["name"], "text": _text(hh, cand, now), "why": "it has already started"})
            if mark:
                sent[cand["key"]] = now_stamp()
            continue
        until = quiet_until(hh, person, now)
        if until:
            entry = {"to": person["name"], "member": person["id"], "text": _text(hh, cand, now),
                     "until": until.isoformat()}  # fmt: skip
            if until > start:
                entry["note"] = ("it starts before their quiet hours end, so it can't be sent in time: tell them "
                                 "when they're next around, or ask the owner whether to send it anyway")  # fmt: skip
            held.append(entry)
            continue
        slot = (person["id"], cand["occurrence"])
        if slot in picked:  # an earlier reminder for the same thing is also due: the later (closer) one wins
            if mark:
                sent[picked[slot]["key"]] = now_stamp()
        picked[slot] = dict(cand, early=early)
    for cand in picked.values():
        chats = _chats(hh, cand, now)
        if chats:
            send.append({"to": cand["person"]["name"], "member": cand["person"]["id"],
                         "text": _text(hh, cand, now, cand["early"]), "kind": cand["kind"], "key": cand["key"],
                         "chats": chats})  # fmt: skip
        else:
            nowhere.append({"to": cand["person"]["name"], "member": cand["person"]["id"], "kind": cand["kind"]})
        if mark:
            sent[cand["key"]] = now_stamp()
    cutoff = now - _dt.timedelta(days=KEEP_SENT_DAYS)
    for key, stamp in list(sent.items()):
        if (parse_stamp(stamp) or now) < cutoff:
            del sent[key]
    return {"send": send, "held": held, "dropped": dropped, "nowhere": nowhere}


def cmd_due(ctx, args) -> dict:
    hh = ctx.household
    if ctx.viewer.group:
        raise ToolError("Reminders are worked out in a direct chat (they can include private things).",
                        hint="Run it from the agent's own routine or a direct chat.", code="direct_chat_only")  # fmt: skip
    only = ctx.member["id"] if args.mine else None
    if not only:
        ctx.viewer.require_owner("work out everyone's reminders (use --mine for your own)")
    now = hh.now()
    with hh.transaction(dry_run=args.peek):
        result = due(ctx, now, only=only, mark=not args.peek)
        hh.touch("notices")
    outside = hh.settings.get("reminders_outside_chat")
    by_person: dict = {}
    for item in result["send"]:
        by_person.setdefault(item["to"], []).append(item["text"])
    lines = [f"{name}: " + " · ".join(texts) for name, texts in by_person.items()]
    summary = f"{plural(len(result['send']), 'reminder')} to pass on now"
    if result["held"]:
        summary += f", {len(result['held'])} held for quiet hours"
    summary += "."
    if result["send"]:
        summary += ' Post each one only in a chat its "chats" list names.'
        if outside:
            summary += " The owner also allowed reminders outside the chat."
    if result["nowhere"]:
        names = and_list(sorted({r["to"] for r in result["nowhere"]}))
        summary += (f" {names} had a reminder but no chat to get it in, so it wasn't sent. The owner can register "
                    "their own one-to-one chat: fridge who chat <chat-id> --type direct --member <name>")
    wanting = [m["name"] for m in hh.members if access.is_adult(m) and members.wants_reminders(m)]
    if args.mine and ctx.member["name"] not in wanting:
        summary += (" Your reminders are off. If you'd like them, say so, and this runs: fridge member edit "
                    f"{ctx.member['name']} --reminders on")
    elif not wanting:
        summary += (" Nobody has turned reminders on yet: each adult who wants them says so in their own chat "
                    "(member edit <name> --reminders on).")
    return dict(result, now=now.isoformat(), outside_chat_ok=bool(outside), reminders_on=wanting,
                text="\n".join(lines) or "Nothing due.", summary=summary)  # fmt: skip


def register(cli) -> None:
    grp = cli.group("remind", "Reminders for events, birthdays and bills, respecting quiet hours.")
    p = grp.add(
        "due",
        "What to remind people of right now (owner; --mine for your own). Run it on a schedule, e.g. every 15 "
        "minutes. Held reminders come back after quiet hours; nothing is repeated.",
        ["fridge remind due", "fridge remind due --mine", "fridge remind due --peek"],
        cmd_due,
    )
    p.add_argument("--mine", action="store_true", help="Only reminders for the person talking")
    p.add_argument("--peek", action="store_true", help="Show without marking them as sent")
