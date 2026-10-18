"""Households and members: names, roles, access, colours, quiet hours, Today sections, stars, and erasing.

Kids and teens are records their parents manage: a first name or nickname, a colour, their chores and a star
count. They never chat with the agent and never act through --as; adults record things for them.
"""

from __future__ import annotations

import re

from . import access, confirm
from .util import ToolError, clean_text, fold, now_stamp, parse_hours_range, plural

# The 10-colour member palette: mid-tones that read on white paper and dark screens.
PALETTE = (
    ("red", "#D9534F"),
    ("orange", "#E67E22"),
    ("gold", "#D4A017"),
    ("green", "#58A55C"),
    ("teal", "#2E9E8F"),
    ("blue", "#3E8FC4"),
    ("indigo", "#5C6BC0"),
    ("purple", "#9068BE"),
    ("pink", "#D264A6"),
    ("brown", "#8D6E63"),
)

# What a member's Today summary can show, in order.
TODAY_SECTIONS = ("events", "tasks", "dinner", "lists", "birthdays", "bills", "notices")

NAME_MAX = 60
MINOR_NAME_MAX = 30

# Other modules register a function(household, member_id) -> list of strings saying what they changed, which
# runs when a member is removed (their personal things go, their name leaves every record).
FORGET_HOOKS: list = []


def color_hex(value: str) -> str:
    text = str(value or "").strip()
    for name, hexcode in PALETTE:
        if fold(text) == name or text.upper() == hexcode:
            return hexcode
    if re.fullmatch(r"#[0-9A-Fa-f]{6}", text):
        return text.upper()
    raise ToolError(
        f"{value!r} isn't a colour I know.",
        hint="Use a palette colour (" + ", ".join(n for n, _ in PALETTE) + ") or a hex code like #3E8FC4.",
        code="bad_color",
    )


def color_name(hexcode: str) -> str:
    for name, code in PALETTE:
        if code == (hexcode or "").upper():
            return name
    return hexcode


def next_color(members: list) -> str:
    """The first palette colour nobody uses yet (cycling once all ten are taken)."""
    used = [m.get("color") for m in members]
    for _, code in PALETTE:
        if code not in used:
            return code
    return PALETTE[len(members) % len(PALETTE)][1]


def check_name(members: list, name, role: str, exclude_id: str | None = None) -> str:
    """Clean a member name; unique in the household; first name or nickname only for kids and teens."""
    limit = MINOR_NAME_MAX if role in access.MINOR_ROLES else NAME_MAX
    text = clean_text(name, "name", max_len=limit)
    if re.search(r"[\d()\[\]]", text) and role not in access.MINOR_ROLES:
        raise ToolError(
            f"A name can't hold an age or other numbers (got {text!r}).",
            hint='Give an age in brackets when adding someone, like --name "Max (15)": it only picks the role '
            "(under 13 kid, 13-17 teen) and isn't stored.",
            code="bad_name",
        )
    if role in access.MINOR_ROLES and (len(text.split()) > 1 or re.search(r"[\d@/()\[\]]", text)):
        raise ToolError(
            f"For kids and teens, use one name: a first name or nickname (got {text!r}).",
            hint="No surnames, ages or other details: Fridge Door keeps only a first name or nickname for kids. "
            "Write a double first name with a hyphen, like Mary-Jane.",
            code="minor_details",
        )
    for member in members:
        if member["id"] != exclude_id and fold(member["name"]) == fold(text):
            raise ToolError(
                f"There's already a member called {member['name']}.",
                hint="Use a different name or a nickname, so each member can be told apart.",
                code="already_member",
            )
    return text


def new_member(members: list, member_id: str, name, role: str = "adult", color=None, access_map=None) -> dict:
    role = (role or "adult").lower()
    if role not in access.ROLES:
        raise ToolError(f"{role!r} isn't a role.", hint="Roles: owner, adult, teen, kid.", code="bad_role")
    member = {
        "id": member_id,
        "name": check_name(members, name, role),
        "role": role,
        "access": access.validate_access(access_map) if access_map else access.preset(role),
        "color": color_hex(color) if color else next_color(members),
        "joined_at": now_stamp(),
    }
    if role in access.MINOR_ROLES:
        member["stars"] = 0
    return member


def owners(members: list) -> list:
    return [m for m in members if m["role"] == "owner"]


def guard_last_owner(members: list, member: dict, new_role: str | None) -> None:
    """A household needs at least one owner: the last one can't be demoted or removed."""
    if member["role"] == "owner" and new_role != "owner" and len(owners(members)) <= 1:
        raise ToolError(
            f"{member['name']} is the only owner.",
            hint="A household needs at least one owner. Make someone else an owner first.",
            code="last_owner",
        )


def wants_reminders(member: dict) -> bool:
    """Reminders are opt-in: an adult gets them only after turning them on themselves (member edit --reminders on)."""
    return bool(member.get("reminders"))


def set_role(member: dict, role: str, keep_custom: bool = False) -> None:
    """Change the role; the access levels reset to the role's preset unless keep_custom."""
    role = role.lower()
    if role not in access.ROLES:
        raise ToolError(f"{role!r} isn't a role.", hint="Roles: owner, adult, teen, kid.", code="bad_role")
    became_minor = role in access.MINOR_ROLES and member["role"] not in access.MINOR_ROLES
    became_adult = role in access.ADULT_ROLES and member["role"] in access.MINOR_ROLES
    member["role"] = role
    if not keep_custom:
        member["access"] = access.preset(role)
    if became_minor:
        member.setdefault("stars", 0)
        member.pop("chat_ok", None)  # kids and teens don't chat with the agent
        member.pop("quiet_hours", None)
        member.pop("today_sections", None)
    if became_adult:
        member.pop("stars", None)


def apply_access_changes(member: dict, changes: list) -> dict:
    """Apply "module=level" changes on top of the member's current map."""
    levels = dict(member["access"])
    for change in changes:
        if "=" not in change:
            raise ToolError(
                f"{change!r} should look like module=level.", hint="e.g. budget=none or grocery=view.",
                code="bad_permissions",
            )  # fmt: skip
        module, lvl = (part.strip() for part in change.split("=", 1))
        if lvl not in access.LEVELS:
            raise ToolError(f"{lvl!r} isn't an access level.", hint="Levels: none, view, edit.", code="bad_permissions")
        levels[access.module_name(module)] = lvl
    if member["role"] in access.MINOR_ROLES and levels.get("budget") != "none":
        raise ToolError(f"{member['name']} is a {member['role']}: kids and teens never see the budget.",
                        hint="Leave budget at none for them.", code="minor_details")  # fmt: skip
    member["access"] = access.validate_access(levels)
    return member["access"]


def set_quiet_hours(member: dict, value: str | None) -> None:
    if value in (None, "", "default"):
        member.pop("quiet_hours", None)
        return
    if fold(value) in ("none", "off", "no"):
        member["quiet_hours"] = None
        return
    start, end = parse_hours_range(value)
    member["quiet_hours"] = {"start": start, "end": end}


def set_today_sections(member: dict, value: str | None) -> None:
    if value in (None, "", "default", "all"):
        member.pop("today_sections", None)
        return
    wanted = [fold(part) for part in re.split(r"[,\s]+", value) if part.strip()]
    bad = [w for w in wanted if w not in TODAY_SECTIONS]
    if bad:
        raise ToolError(
            f"Unknown Today {'section' if len(bad) == 1 else 'sections'}: {', '.join(bad)}.",
            hint="Choose from: " + ", ".join(TODAY_SECTIONS) + ".",
            code="bad_section",
        )
    member["today_sections"] = [s for s in TODAY_SECTIONS if s in wanted]


def quiet_hours(member: dict, settings: dict):
    """The member's quiet hours (their own, else the household default), or None for none."""
    if "quiet_hours" in member:
        return member["quiet_hours"]
    return settings.get("quiet_hours")


def public(member: dict, settings: dict | None = None, viewer=None, detail: bool = True) -> dict:
    """What a member record looks like in replies (detail adds access levels, quiet hours and Today sections)."""
    out = {
        "id": member["id"],
        "name": member["name"],
        "role": member["role"],
        "color": member["color"],
        "color_name": color_name(member["color"]),
    }
    if detail:
        out["access"] = dict(member["access"])
    if member["role"] in access.MINOR_ROLES:
        out["stars"] = int(member.get("stars", 0))
        out["chats"] = False
    else:
        out["chats"] = bool(member.get("chat_ok")) or member["role"] == "owner"
        out["reminders"] = wants_reminders(member)
        if detail and settings is not None:
            out["quiet_hours"] = quiet_hours(member, settings)
        if detail:
            out["today_sections"] = member.get("today_sections") or list(TODAY_SECTIONS)
    if viewer is not None and member["id"] == viewer.actor_id:
        out["you"] = True
    return out


def parse_person(text: str) -> tuple:
    """Read "Mateo (15)" or "Sofia (kid)" into (name, role), or (name, None) with no tag. An age in brackets only
    picks the role (under 13 kid, 13-17 teen, 18+ adult) and is never stored."""
    match = re.fullmatch(r"(.+?)\s*[(\[]\s*([^)\]]+?)\s*[)\]]", str(text or "").strip())
    if not match:
        return str(text or "").strip(), None
    name, tag = match.group(1).strip(), match.group(2)
    key = fold(tag)
    if key in access.ROLES:
        return name, key
    if key in ("child", "kids", "son", "daughter", "baby", "toddler"):
        return name, "kid"
    if key in ("teenager", "teens"):
        return name, "teen"
    if key in ("me", "parent", "mum", "mom", "dad", "partner", "roommate", "flatmate", "grandparent"):
        return name, "adult"
    if re.fullmatch(r"\d{1,3}", key):
        age = int(key)
        return name, "kid" if age < 13 else "teen" if age < 18 else "adult"
    raise ToolError(
        f"I can't tell what {tag!r} means for {name}.",
        hint="Mark people as (owner), (adult), (teen) or (kid), or give an age like (9), which isn't stored.",
        code="bad_role",
    )


def parse_member_list(text: str) -> list:
    """Read "Ana, Luis, Sofia (kid), Mateo (15)" into [(name, role)] (see parse_person). The first person is the
    owner unless someone is marked "(owner)"."""
    parts = [p.strip() for p in re.split(r"[,;\n]|\band\b|&", str(text or "")) if p.strip()]
    if not parts:
        raise ToolError("Who's in the household?", hint='e.g. --members "Ana, Luis, Sofia (kid)"', code="missing")
    people = [list(parse_person(part)) for part in parts]
    if not any(role == "owner" for _, role in people):
        if people[0][1] in access.MINOR_ROLES:
            raise ToolError(
                "The first person listed becomes the owner, and the owner must be an adult.",
                hint="List the adult setting this up first, or mark them (owner).",
                code="bad_role",
            )
        people[0][1] = "owner"
    return [(name, role or "adult") for name, role in people]


def forget(household, member_id: str) -> list:
    """Run every module's erase hook for a member being removed."""
    changes = []
    for hook in FORGET_HOOKS:
        changes.extend(hook(household, member_id) or [])
    return changes


# --------------------------------------------------------------------------- commands


def _find(ctx, query) -> dict:
    from .context import find_member

    return find_member(ctx.household, query)


def cmd_list(ctx, args) -> dict:
    hh = ctx.household
    roster = [public(m, hh.settings, ctx.viewer, detail=args.detail) for m in hh.members]
    lines = []
    for m in roster:
        extra = f", {m['stars']} stars" if "stars" in m else ""
        lines.append(f"{m['name']} ({m['role']}, {m['color_name']}{extra})")
    return {"members": roster, "text": "\n".join(lines), "summary": f"{plural(len(roster), 'member')} in {hh.name}."}


def cmd_show(ctx, args) -> dict:
    member = _find(ctx, args.member)
    return {"member": public(member, ctx.household.settings, ctx.viewer), "summary": member["name"]}


def cmd_add(ctx, args) -> dict:
    ctx.viewer.require_owner("add members")
    from . import todos

    hh = ctx.household
    name, tagged = parse_person(args.name)  # "Max (15)" is a teen called Max, as in setup
    if tagged and args.role and tagged != args.role:
        raise ToolError(f"{args.name!r} says {tagged}, but --role says {args.role}.",
                        hint="Give one: an age or tag in brackets, or --role.", code="bad_role")  # fmt: skip
    with hh.transaction(dry_run=args.dry_run):
        member = new_member(hh.members, hh.next_id("member"), name, tagged or args.role or "adult", args.color)
        hh.members.append(member)
        if args.quiet_hours and member["role"] in access.ADULT_ROLES:
            set_quiet_hours(member, args.quiet_hours)
        hh.touch("household")
        made = todos.ensure_default_lists(hh)
        hh.log("member.add", ctx.member["id"], member=member["id"], role=member["role"])
        result = public(member, hh.settings)
    verb = "Would add" if args.dry_run else "Added"
    summary = f"{verb} {member['name']} as {'an' if member['role'] in ('owner', 'adult') else 'a'} {member['role']}."
    if member["role"] in access.MINOR_ROLES:
        summary += (
            " They take part through the adults: chores and stars on the fridge sheet, no chatting with the agent."
        )
    return {"member": result, "lists": [lst["name"] for lst in made], "dry_run": args.dry_run, "summary": summary}


def cmd_edit(ctx, args) -> dict:
    hh = ctx.household
    target = _find(ctx, args.member)
    if target["id"] != ctx.member["id"]:
        if args.reminders == "on":  # reminders are each adult's own yes, never someone else's
            raise ToolError(
                f"Only {target['name']} can turn on their own reminders: it's their yes to hear from the agent.",
                hint=f"Ask {target['name']}. If they want reminders, they say so in their own chat, which runs: "
                f"fridge member edit {target['name']} --reminders on",
                code="not_their_own",
            )
        ctx.viewer.require_owner("change another member's details")
    if not any((args.name, args.color, args.quiet_hours, args.today_sections, args.reminders)):
        raise ToolError("Nothing to change.", hint="Pass --name, --color, --quiet-hours, --today-sections or "
                        "--reminders.", code="usage")  # fmt: skip
    with hh.transaction(dry_run=args.dry_run):
        member = hh.member(target["id"])
        changed = []
        if args.name:
            member["name"] = check_name(hh.members, args.name, member["role"], exclude_id=member["id"])
            changed.append("name")
        if args.color:
            member["color"] = color_hex(args.color)
            changed.append("colour")
        if args.quiet_hours or args.today_sections or args.reminders:
            if member["role"] in access.MINOR_ROLES:
                raise ToolError(
                    f"{member['name']} doesn't chat with the agent, so quiet hours, Today sections and reminders "
                    "don't apply.",
                    code="minor_cannot_chat",
                )
            if args.quiet_hours:
                set_quiet_hours(member, args.quiet_hours)
                changed.append("quiet hours")
            if args.today_sections:
                set_today_sections(member, args.today_sections)
                changed.append("Today sections")
            if args.reminders == "on":
                member["reminders"] = {"on": True, "at": now_stamp()}
                changed.append("reminders (on)")
            elif args.reminders == "off":
                member.pop("reminders", None)
                changed.append("reminders (off)")
        hh.touch("household")
        hh.log("member.edit", ctx.member["id"], member=member["id"], fields=changed)
        result = public(member, hh.settings, ctx.viewer)
    verb = "Would update" if args.dry_run else "Updated"
    return {"member": result, "dry_run": args.dry_run, "summary": f"{verb} {member['name']}'s {', '.join(changed)}."}


def cmd_access(ctx, args) -> dict:
    ctx.viewer.require_owner("change roles and access")
    from . import todos
    from .context import adult_confirmed, clear_member_from_hub, drop_member_chats

    hh = ctx.household
    target = _find(ctx, args.member)
    if not (args.role or args.set or args.reset):
        lines = [f"{access.MODULE_LABELS[m]}: {lvl}" for m, lvl in target["access"].items()]
        return {"member": public(target, hh.settings), "text": "\n".join(lines),
                "summary": f"{target['name']} is {target['role']}."}  # fmt: skip
    # Making a kid or teen an adult lets them chat with the agent and see the budget: the owner's clear yes first.
    promoting = bool(args.role) and args.role.lower() in access.ADULT_ROLES and target["role"] in access.MINOR_ROLES
    words = adult_confirmed(
        ctx, target, args.owner_confirmed, args.confirm,
        why=f"Making {target['name']} an adult lets them chat with the agent and see the budget, so the owner must "
        "confirm they're 18 or older.",
    ) if promoting else None  # fmt: skip
    with hh.transaction(dry_run=args.dry_run):
        member = hh.member(target["id"])
        deleted, unlinked = [], []
        if args.role:
            role = args.role.lower()
            guard_last_owner(hh.members, member, role)
            if role in access.MINOR_ROLES and member["role"] in access.ADULT_ROLES:
                check_name([], member["name"], role)  # kids and teens keep only a first name or nickname
                deleted, unlinked = drop_member_chats(hh, member["id"])  # and never chat with the agent
            set_role(member, role)
            if words:
                member["chat_ok"] = {"owner_said": words, "at": now_stamp(), "by": ctx.member["id"]}
        if args.reset:
            member["access"] = access.preset(member["role"])
        if args.set:
            apply_access_changes(member, args.set)
        hh.touch("household")
        made = todos.ensure_default_lists(hh)
        hh.log("member.access", ctx.member["id"], member=member["id"], role=member["role"])
        result = public(member, hh.settings)
    became_minor = result["role"] in access.MINOR_ROLES and target["role"] in access.ADULT_ROLES
    if became_minor and not args.dry_run:
        clear_member_from_hub(ctx.hub, hh.id, target["id"], deleted)
    verb = "Would set" if args.dry_run else "Set"
    levels = ", ".join(f"{m} {lvl}" for m, lvl in result["access"].items())
    summary = f"{verb} {result['name']} to {result['role']}: {levels}."
    if deleted or unlinked:
        chats = ", ".join(sorted(set(deleted + unlinked)))
        summary += f" Removed from {chats}: kids and teens don't chat with the agent."
    return {
        "member": result,
        "lists": [lst["name"] for lst in made],
        "deleted_chats": deleted or None,
        "unlinked_chats": unlinked or None,
        "dry_run": args.dry_run,
        "summary": summary,
    }


def cmd_remove(ctx, args) -> dict:
    ctx.viewer.require_owner("remove members")
    from .context import clear_member_from_hub
    hh = ctx.household
    target = _find(ctx, args.member)
    guard_last_owner(hh.members, target, None)
    words = confirm.owner_yes(
        hh, ctx.member["id"], f"member.remove|{target['id']}",
        f"Remove {target['name']} from {hh.name} and erase their details?", args.owner_confirmed, args.confirm,
        why=f"Removing {target['name']} erases their profile and personal list, unassigns their tasks and takes their "
        "name off every record. It can't be undone.",
        echo=("remove", "delete", "them", target["name"]),
    )
    with hh.transaction(dry_run=args.dry_run):
        changes = forget(hh, target["id"])
        hh.meta()["members"] = [m for m in hh.members if m["id"] != target["id"]]
        hh.touch("household")
        hh.log("member.remove", ctx.member["id"], member=target["id"], owner_said=words)
    if not args.dry_run:
        clear_member_from_hub(ctx.hub, hh.id, target["id"], hh.dropped_chats)
    verb = "Would remove" if args.dry_run else "Removed"
    return {
        "removed": {"id": target["id"], "name": target["name"]},
        "changes": changes,
        "dry_run": args.dry_run,
        "summary": f"{verb} {target['name']} and erased their details"
        + (f" ({'; '.join(changes)})." if changes else "."),
    }


def cmd_stars(ctx, args) -> dict:
    hh = ctx.household
    if args.member is None:
        kids = [public(m) for m in hh.members if m["role"] in access.MINOR_ROLES]
        text = "\n".join(f"{k['name']}: {'★' * min(k['stars'], 20)} {k['stars']}" for k in kids)
        summary = ", ".join(f"{k['name']} {k['stars']}" for k in kids) or "No kids or teens to give stars to."
        return {"stars": [{"name": k["name"], "stars": k["stars"]} for k in kids], "text": text, "summary": summary}
    target = _find(ctx, args.member)
    if target["role"] not in access.MINOR_ROLES:
        raise ToolError("Stars are for kids and teens.", code="not_a_kid")
    if args.add is None:
        return {"member": target["name"], "stars": int(target.get("stars", 0)),
                "summary": f"{target['name']} has {int(target.get('stars', 0))} stars."}  # fmt: skip
    if not access.is_adult(ctx.member):
        raise ToolError("Only adults give or take stars.", code="not_authorized")
    with hh.transaction(dry_run=args.dry_run):
        member = hh.member(target["id"])
        member["stars"] = max(0, int(member.get("stars", 0)) + args.add)
        hh.touch("household")
        hh.log("member.stars", ctx.member["id"], member=member["id"], change=args.add)
        total = member["stars"]
    verb = "gave" if args.add >= 0 else "took"
    summary = f"{ctx.member['name']} {verb} {plural(abs(args.add), 'star')}: {target['name']} has {total}."
    return {"member": target["name"], "stars": total, "dry_run": args.dry_run, "summary": summary}


def register(cli) -> None:
    from . import shopping, todos

    FORGET_HOOKS.extend([todos.forget_member, shopping.forget_member])
    grp = cli.group("member", "Members: list, show, add, edit, access, stars, remove.")
    p = grp.add("list", "List the household's members with their role, colour and stars.",
                ["fridge member list", "fridge member list --detail"], cmd_list)  # fmt: skip
    p.add_argument("--detail", action="store_true", help="Include access levels, quiet hours and Today sections")
    p = grp.add("show", "Show one member.", ["fridge member show Sofia"], cmd_show)
    p.add_argument("member")
    p = grp.add(
        "add",
        "Add a member (owner). Kids and teens get only a first name or nickname, a colour and stars.",
        [
            'fridge member add --name "Grandma Rosa" --role adult',
            "fridge member add --name Mia --role kid --color pink",
        ],
        cmd_add,
    )
    p.add_argument("--name", required=True, help='First name, or a nickname; "Max (15)" makes a teen (the age '
                   "isn't stored)")
    p.add_argument("--role", choices=access.ROLES, help="owner, adult, teen or kid (default: adult)")
    p.add_argument("--color", help="A palette colour name or #RRGGBB (default: the next unused one)")
    p.add_argument("--quiet-hours", help='Adults: e.g. "22:00-07:00", or none')
    p.add_argument("--dry-run", action="store_true")
    p = grp.add(
        "edit",
        "Change a member's name, colour, quiet hours or Today sections (yourself, or anyone if you're the owner).",
        [
            "fridge member edit Ana --color teal",
            'fridge member edit Ana --quiet-hours "22:30-06:30"',
            "fridge member edit Luis --today-sections events,tasks,dinner",
        ],
        cmd_edit,
    )
    p.add_argument("member")
    p.add_argument("--name")
    p.add_argument("--color")
    p.add_argument("--quiet-hours", help='"HH:MM-HH:MM", none, or default (the household\'s)')
    p.add_argument("--today-sections", help="Comma list from: " + ", ".join(TODAY_SECTIONS) + "; or all")
    p.add_argument("--reminders", choices=("on", "off"), help="on: they'd like reminders (only they can say so); off")
    p.add_argument("--dry-run", action="store_true")
    p = grp.add(
        "access",
        "Show or change a member's role and per-module access (owner). A new role resets access to its preset.",
        [
            "fridge member access Mateo",
            "fridge member access Mateo --role teen",
            "fridge member access Sofia --set grocery=edit --set calendar=view",
            "fridge member access Luis --reset",
            'fridge member access Zoe --role adult --owner-confirmed "yes, Zoe is 19" '
            "--confirm 1c5e2a0-8d41f2-3f9b27d41c",
        ],
        cmd_access,
    )
    p.add_argument("member")
    p.add_argument("--role", choices=access.ROLES)
    p.add_argument("--set", action="append", help="module=level (none, view or edit); repeat for more")
    p.add_argument("--reset", action="store_true", help="Back to the role's preset")
    p.add_argument("--owner-confirmed", help="Making a kid or teen an adult: the owner's own words that they're 18+")
    p.add_argument("--confirm", help="The code that came with the owner's question (confirm)")
    p.add_argument("--dry-run", action="store_true")
    p = grp.add(
        "stars",
        "Show the kids' and teens' stars, or give/take some (adults): --add 1, --add -1.",
        ["fridge member stars", "fridge member stars Mia --add 1"],
        cmd_stars,
    )
    p.add_argument("member", nargs="?")
    p.add_argument("--add", type=int, help="Stars to add (negative to take away)")
    p.add_argument("--dry-run", action="store_true")
    p = grp.add(
        "remove",
        "Remove a member and erase their details (owner, needs the owner's own words).",
        ['fridge member remove "Uncle Leo"',
         'fridge member remove "Uncle Leo" --owner-confirmed "yes, remove Uncle Leo" '
         "--confirm 1c5e2a0-8d41f2-3f9b27d41c"],
        cmd_remove,
    )
    p.add_argument("member")
    p.add_argument("--owner-confirmed", help="The owner's own words confirming the removal")
    p.add_argument("--confirm", help="The code that came with the owner's question (confirm)")
    p.add_argument("--dry-run", action="store_true")
