"""Notes: shared or private, with checklists, photos (file paths), folders, tags and pins. Kept lean.

Sensitive notes (wifi passwords, door codes) show only to members with notes access, only in a direct chat, and
never in a group chat unless the owner turned that on (household settings: sensitive_notes_in_groups). They never
go on a printout.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import access, trash
from .util import ToolError, clean_text, fold, match_one, now_stamp, plural

BODY_MAX = 10000


def visible(ctx, note: dict) -> bool:
    viewer = ctx.viewer
    if not viewer.sees("notes"):
        return False
    if note.get("visibility") == "private":
        return viewer.sees_private_of(note.get("author"))
    if note.get("sensitive"):
        return not viewer.group or bool(ctx.household.settings.get("sensitive_notes_in_groups"))
    return True


def note_view(hh, note: dict, full: bool = True) -> dict:
    out = {"id": note["id"], "title": note["title"], "pinned": bool(note.get("pinned")),
           "private": note.get("visibility") == "private", "sensitive": bool(note.get("sensitive")),
           "folder": note.get("folder"), "tags": note.get("tags", [])}  # fmt: skip
    if note.get("checklist"):
        done = sum(1 for item in note["checklist"] if item.get("done"))
        out["progress"] = f"{done}/{len(note['checklist'])}"
    if full:
        out["body"] = note.get("body")
        out["checklist"] = [{"n": i + 1, "text": c["text"], "done": bool(c.get("done"))}
                            for i, c in enumerate(note.get("checklist", []))]  # fmt: skip
        out["photos"] = list(note.get("photos", []))
        out["author"] = hh.member_name(note.get("author"))
        out["updated_at"] = note.get("updated_at") or note.get("created_at")
    return out


def note_text(note: dict) -> str:
    lines = [("📌 " if note.get("pinned") else "") + ("🔒 " if note.get("sensitive") else "") + note["title"]]
    if note.get("body"):
        lines.append(note["body"])
    for item in note.get("checklist", []):
        lines.append(("☑ " if item.get("done") else "☐ ") + item["text"])
    return "\n".join(lines)


def _require(ctx, need: str) -> None:
    ctx.viewer.require("notes", need, "see notes" if need == "view" else "change notes")
    ctx.viewer.require_sees("notes")


def find_note(ctx, data: dict, query) -> dict:
    _require(ctx, "view")
    pool = [n for n in data["notes"] if visible(ctx, n)]
    try:
        return match_one(pool, query, "note", key="title", hint="See them with: fridge note list")
    except ToolError as exc:
        if exc.code != "not_found" or not ctx.viewer.group:
            raise
        # Safe to say so: getting here means everyone in this group may see notes, so each of them could open a shared
        # sensitive note in their own chat. Private notes never count.
        hidden = [n for n in data["notes"] if n.get("sensitive") and n.get("visibility") != "private"]
        try:
            match_one(hidden, query, "note", key="title")
        except ToolError:
            raise exc from None
        raise ToolError("That note is marked sensitive, so it isn't shown in group chats.",
                        hint="Ask for it (or change it) in a direct chat.", code="hidden_in_group") from None  # fmt: skip


_HEALTH = re.compile(r"allerg|epi-?pen|asthma|inhaler|medic|diagnos|diabet|insulin|seizure|epilep|anaphyla|adhd|"
                     r"autis|prescription|eczema|condition|therap")


_SCHOOL = re.compile(r"\b(?:school|elementary|kindergarten|daycare|day care|preschool|nursery school|homeroom|"
                     r"grade \d+|year \d+)\b")


def check_child_details(hh, note: dict) -> None:
    """A child's health or school details stay out of group chats and off the fridge sheet: a shared note that names
    a kid or teen next to them must be sensitive (or private). The sitter's notes can still hold the allergy."""
    if note.get("sensitive") or note.get("visibility") == "private":
        return
    text = fold(" ".join([note["title"], note.get("body") or ""] + [c["text"] for c in note.get("checklist", [])]))
    kids = [m["name"] for m in hh.members
            if access.is_minor(m) and re.search(rf"\b{re.escape(fold(m['name']))}\b", text)]  # fmt: skip
    what = "health" if _HEALTH.search(text) else "school" if _SCHOOL.search(text) else None
    if kids and what:
        raise ToolError(
            f"This note names {kids[0]} next to {what} details, so it can't be a plain shared note: a child's details "
            "stay out of group chats and off the fridge sheet.",
            hint="Save it with --sensitive (adults see it in their own chats) or --private (only you), or leave "
            f"{kids[0]}'s details out.",
            code="child_details",
        )


def _can_change(ctx, note: dict) -> None:
    ctx.viewer.require("notes", "edit", "change notes")
    if note.get("visibility") == "private" and note.get("author") != ctx.member["id"]:
        raise ToolError("That's someone else's private note.", code="not_authorized")


def _tags(values) -> list:
    out = []
    for value in values or []:
        for tag in str(value).split(","):
            tag = fold(tag).lstrip("#")
            if tag and tag not in out:
                out.append(tag)
    return out


def _photo(path: str) -> str:
    file = Path(path).expanduser()
    if not file.is_file():
        raise ToolError(f"There's no file at {path}.", hint="Save the photo first, then pass its path.", code="no_file")
    return str(file)


def cmd_add(ctx, args) -> dict:
    _require(ctx, "edit")
    hh = ctx.household
    with hh.transaction(dry_run=args.dry_run):
        data = hh.data("notes")
        title = clean_text(args.title, "note title", max_len=120)
        # Shared notes, sensitive ones too (everyone here may see notes, so each could open those in their own chat),
        # and the person's own private notes, but not in a group: a group never learns what those are called.
        clashing = [n for n in data["notes"] if n.get("visibility") != "private"
                    or (n.get("author") == ctx.member["id"] and not ctx.viewer.group)]  # fmt: skip
        if any(fold(n["title"]) == fold(title) for n in clashing):
            raise ToolError(f"There's already a note called {title}.",
                            hint=f'Change that one instead (fridge note edit "{title}" ...), or give this a new title. '
                            "If it isn't shown here, it may be marked sensitive: ask in a direct chat.",
                            code="exists")  # fmt: skip
        note = {
            "id": hh.next_id("note"),
            "title": title,
            "body": clean_text(args.body, "note", max_len=BODY_MAX, required=False) if args.body else None,
            "checklist": [{"text": clean_text(item, "checklist item", max_len=200), "done": False}
                          for item in args.item or []],  # fmt: skip
            "photos": [_photo(p) for p in args.photo or []],
            "folder": clean_text(args.folder, "folder", max_len=40, required=False),
            "tags": _tags(args.tag),
            "pinned": bool(args.pin),
            "visibility": "private" if args.private else "shared",
            "sensitive": bool(args.sensitive),
            "author": ctx.member["id"],
            "created_at": now_stamp(),
        }
        if args.body and len(args.body) > BODY_MAX:
            raise ToolError("That note is too long.", code="too_long")
        check_child_details(hh, note)
        data["notes"].append(note)
        hh.touch("notes")
        hh.log("note.add", ctx.member["id"], note=note["id"])
    kind = "private note" if note["visibility"] == "private" else "note"
    extra = " It's marked sensitive: shown only in direct chats." if note["sensitive"] else ""
    out = {"note": note_view(hh, note), "dry_run": args.dry_run,
           "summary": f"{'Would save' if args.dry_run else 'Saved'} the {kind} \"{note['title']}\".{extra}"}  # fmt: skip
    return out


def cmd_list(ctx, args) -> dict:
    _require(ctx, "view")
    hh = ctx.household
    notes = [n for n in hh.data("notes")["notes"] if visible(ctx, n)]
    if args.folder:
        notes = [n for n in notes if fold(n.get("folder")) == fold(args.folder)]
    if args.tag:
        notes = [n for n in notes if fold(args.tag).lstrip("#") in n.get("tags", [])]
    if args.pinned:
        notes = [n for n in notes if n.get("pinned")]
    if args.search:
        q = fold(args.search)
        notes = [n for n in notes if q in fold(n["title"]) or q in fold(n.get("body"))
                 or any(q in fold(c["text"]) for c in n.get("checklist", []))]  # fmt: skip
    notes.sort(key=lambda n: (not n.get("pinned"), fold(n.get("folder")), fold(n["title"])))
    views = [note_view(hh, n, full=False) for n in notes]
    lines = [("📌 " if v["pinned"] else "• ") + v["title"] + (f" [{v['folder']}]" if v["folder"] else "")
             + (f" ({v['progress']})" if v.get("progress") else "") for v in views]  # fmt: skip
    hidden = 0
    if ctx.viewer.group:
        hidden = sum(1 for n in hh.data("notes")["notes"]
                     if n.get("sensitive") and n.get("visibility") != "private" and not visible(ctx, n))  # fmt: skip
    out = {"notes": views, "text": "\n".join(lines) or "No notes.", "summary": f"{plural(len(views), 'note')}."}
    if hidden:
        out["summary"] += f" {plural(hidden, 'sensitive note')} not shown in this group."
    return out


def cmd_show(ctx, args) -> dict:
    hh = ctx.household
    note = find_note(ctx, hh.data("notes"), args.note)
    return {"note": note_view(hh, note), "text": note_text(note), "summary": note["title"]}


def cmd_edit(ctx, args) -> dict:
    hh = ctx.household
    with hh.transaction(dry_run=args.dry_run):
        data = hh.data("notes")
        note = find_note(ctx, data, args.note)
        _can_change(ctx, note)
        changed = []
        if args.title:
            note["title"] = clean_text(args.title, "note title", max_len=120)
            changed.append("title")
        if args.body is not None:
            note["body"] = clean_text(args.body, "note", max_len=BODY_MAX, required=False)
            changed.append("text")
        if args.append:
            note["body"] = ((note.get("body") or "") + "\n" + args.append).strip()[:BODY_MAX]
            changed.append("text")
        if args.folder is not None:
            note["folder"] = clean_text(args.folder, "folder", max_len=40, required=False)
            changed.append("folder")
        if args.tag:
            note["tags"] = list(dict.fromkeys(note.get("tags", []) + _tags(args.tag)))
            changed.append("tags")
        if args.untag:
            gone = set(_tags(args.untag))
            note["tags"] = [t for t in note.get("tags", []) if t not in gone]
            changed.append("tags")
        for flag, key, value in ((args.pin, "pinned", True), (args.unpin, "pinned", False),
                                 (args.sensitive, "sensitive", True), (args.not_sensitive, "sensitive", False)):  # fmt: skip
            if flag:
                note[key] = value
                changed.append(key)
        if args.private or args.shared:
            if note.get("author") != ctx.member["id"]:
                raise ToolError("Only the person who wrote a note can make it private or shared.",
                                code="not_authorized")  # fmt: skip
            note["visibility"] = "private" if args.private else "shared"
            changed.append("visibility")
        for item in args.add_item or []:
            note.setdefault("checklist", []).append({"text": clean_text(item, "checklist item", max_len=200),
                                                     "done": False})  # fmt: skip
            changed.append("checklist")
        for path in args.add_photo or []:
            path = _photo(path)
            if path not in note.setdefault("photos", []):
                note["photos"].append(path)
            changed.append("photos")
        if not changed:
            raise ToolError("Nothing to change.", hint="See: fridge note edit --help", code="usage")
        check_child_details(hh, note)
        note["updated_at"] = now_stamp()
        hh.touch("notes")
        hh.log("note.edit", ctx.member["id"], note=note["id"], fields=sorted(set(changed)))
    verb = "Would update" if args.dry_run else "Updated"
    out = {"note": note_view(hh, note), "dry_run": args.dry_run,
           "summary": f"{verb} \"{note['title']}\": {', '.join(sorted(set(changed)))}."}  # fmt: skip
    return out


def cmd_check(ctx, args) -> dict:
    hh = ctx.household
    with hh.transaction():
        data = hh.data("notes")
        note = find_note(ctx, data, args.note)
        _can_change(ctx, note)
        items = note.get("checklist", [])
        if not items:
            raise ToolError(f"\"{note['title']}\" has no checklist.", hint="Add items with --add-item.", code="usage")
        ticked = []
        for query in args.items:
            if str(query).isdigit() and 1 <= int(query) <= len(items):
                item = items[int(query) - 1]
            else:
                item = match_one([dict(c, id=str(i)) for i, c in enumerate(items)], query, "checklist item",
                                 key="text")  # fmt: skip
                item = items[int(item["id"])]
            item["done"] = not args.undo
            ticked.append(item["text"])
        note["updated_at"] = now_stamp()
        hh.touch("notes")
        done = sum(1 for c in items if c.get("done"))
    verb = "Unticked" if args.undo else "Ticked"
    return {"progress": f"{done}/{len(items)}", "summary": f"{verb} {', '.join(ticked)} ({done}/{len(items)} done)."}


def cmd_delete(ctx, args) -> dict:
    hh = ctx.household
    with hh.transaction():
        data = hh.data("notes")
        note = find_note(ctx, data, args.note)
        _can_change(ctx, note)
        data["notes"] = [n for n in data["notes"] if n["id"] != note["id"]]
        undo = trash.put(hh, "note", [note], ctx.member["id"])
        hh.touch("notes")
        hh.log("note.delete", ctx.member["id"], note=note["id"])
    return {"summary": f"Deleted \"{note['title']}\". {trash.kept_for(hh)}", "undo": undo}


def forget_member(hh, member_id: str) -> list:
    data = hh.data("notes")
    before = len(data["notes"])
    data["notes"] = [
        n for n in data["notes"] if not (n.get("visibility") == "private" and n.get("author") == member_id)
    ]
    def scrub(note: dict) -> None:
        if note.get("author") == member_id:
            note["author"] = None

    for note in data["notes"]:
        scrub(note)
    trash.forget(hh, "notes", member_id, lambda n: n.get("visibility") == "private" and n.get("author") == member_id,
                 scrub)  # fmt: skip
    hh.touch("notes")
    gone = before - len(data["notes"])
    return [f"deleted {plural(gone, 'private note')}"] if gone else []


def register(cli) -> None:
    from .members import FORGET_HOOKS

    FORGET_HOOKS.append(forget_member)
    grp = cli.group("note", "Notes: shared or private, checklists, folders and tags, pinned notes, sensitive notes.")
    p = grp.add(
        "add",
        "Save a note. --sensitive keeps it out of group chats and printouts; --private keeps it to yourself.",
        [
            'fridge note add "Wifi" --body "Network: Maple-5G" --pin --sensitive',
            'fridge note add "Sitter instructions" --body "Bedtime 8pm" --folder Kids --pin',
            'fridge note add "Camping packing list" --item tent --item "sleeping bags" --tag trips',
        ],
        cmd_add,
    )
    p.add_argument("title")
    p.add_argument("--body")
    p.add_argument("--item", action="append", help="A checklist item; repeat")
    p.add_argument("--photo", action="append", help="Path of a saved photo; repeat")
    p.add_argument("--folder")
    p.add_argument("--tag", action="append")
    p.add_argument("--pin", action="store_true")
    p.add_argument("--private", action="store_true")
    p.add_argument("--sensitive", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p = grp.add("list", "List notes (pinned first), by folder, tag or search words.",
                ["fridge note list", "fridge note list --folder Kids", "fridge note list --search wifi"], cmd_list)  # fmt: skip
    p.add_argument("--folder")
    p.add_argument("--tag")
    p.add_argument("--pinned", action="store_true")
    p.add_argument("--search")
    p = grp.add("show", "Show one note.", ['fridge note show Wifi'], cmd_show)
    p.add_argument("note")
    p = grp.add(
        "edit",
        "Change a note: title, text (or --append), folder, tags, pin, sensitive, private/shared, items, photos.",
        ['fridge note edit Wifi --body "Network: Maple-5G, password on the router"', "fridge note edit "
         '"Sitter instructions" --append "Allergic to peanuts"', 'fridge note edit "Packing list" --add-item torch'],
        cmd_edit,
    )  # fmt: skip
    p.add_argument("note")
    p.add_argument("--title")
    p.add_argument("--body")
    p.add_argument("--append")
    p.add_argument("--folder")
    p.add_argument("--tag", action="append")
    p.add_argument("--untag", action="append")
    p.add_argument("--pin", action="store_true")
    p.add_argument("--unpin", action="store_true")
    p.add_argument("--sensitive", action="store_true")
    p.add_argument("--not-sensitive", action="store_true")
    p.add_argument("--private", action="store_true")
    p.add_argument("--shared", action="store_true")
    p.add_argument("--add-item", action="append")
    p.add_argument("--add-photo", action="append")
    p.add_argument("--dry-run", action="store_true")
    p = grp.add("check", "Tick checklist items by number or words (--undo to untick).",
                ['fridge note check "Packing list" 1 tent'], cmd_check)  # fmt: skip
    p.add_argument("note")
    p.add_argument("items", nargs="+")
    p.add_argument("--undo", action="store_true")
    p = grp.add("delete", "Delete a note.", ['fridge note delete "Old wifi"'], cmd_delete)
    p.add_argument("note")
