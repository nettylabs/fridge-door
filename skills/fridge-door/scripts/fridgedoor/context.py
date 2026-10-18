"""Who's talking, and who will see the reply.

- Direct chat: the household's speaker (whoever set it up, unless the owner chose someone else), or --as <adult>.
- Group chat: the owner registers the chat once (who chat), saying whether anyone under 18 is in it, then links
  each adult participant to a member once (who link). Messages then carry --chat <id> --from <participant>.
- Only adults chat with the agent. Kids and teens can't be linked and never act through --as; a parent records
  things for them (todo done T5 --by Mia).
- In a group chat the audience is every linked member, plus a kid-level stand-in when minors are present, and
  replies show only what all of them may see.
"""

from __future__ import annotations

import shutil

from . import access, confirm
from .access import Viewer
from .store import Hub, Household
from .util import ToolError, clean_text, fold, match_one, now_stamp, plural, set_local_tz


class Ctx:
    """Everything a command needs: the hub, the household, who's acting and who's watching."""

    def __init__(self, hub: Hub, household: Household, viewer: Viewer, chat_id: str | None = None):
        self.hub = hub
        self.household = household
        self.viewer = viewer
        self.chat_id = chat_id

    @property
    def member(self) -> dict:
        return self.viewer.actor

    def describe(self) -> dict:
        hh = self.household
        return {
            "household": {"id": hh.id, "name": hh.name},
            "member": {"id": self.member["id"], "name": self.member["name"], "role": self.member["role"]},
            "chat": self.chat_id,
            "group": self.viewer.group,
            "audience": [p["name"] for p in self.viewer.audience],
            "minors_present": self.viewer.minors_present,
        }


def find_member(household: Household, query, what: str = "member") -> dict:
    return match_one(household.members, query, what, hint="See the members with: fridge member list")


def refuse_minor(member: dict, doing: str = "chat with the agent") -> None:
    if access.is_minor(member):
        raise ToolError(
            f"{member['name']} is a {member['role']}: kids and teens don't {doing} in Fridge Door.",
            hint=f"An adult records things for them instead, e.g. todo done <task> --by {member['name']}. "
            "Their chores and stars show on the printable fridge sheet.",
            code="minor_cannot_chat",
        )


def resolve(hub: Hub, args) -> Ctx:
    """Work out the household, the acting member and the audience from --household/--as/--chat/--from."""
    hub.require()
    chat_id = getattr(args, "chat", None)
    query = getattr(args, "household", None)
    if not query and chat_id:
        query = hub.chat_household(chat_id)
        if not query:
            raise ToolError(
                f"The chat {chat_id!r} isn't linked to a household yet.",
                hint=REGISTER_HINT,
                code="chat_not_linked",
            )
    household = hub.household(query)
    meta = household.meta()
    chat = meta.get("chats", {}).get(chat_id) if chat_id else None
    if chat_id and chat is None:
        raise ToolError(
            f"The chat {chat_id!r} isn't linked to {household.name}.",
            hint=REGISTER_HINT,
            code="chat_not_linked",
        )
    set_local_tz(household.tz())
    if not chat_id and hub.direct_chats_in_use():
        # A one-to-one chat is registered (setup --chat, who chat): the platform gives chats ids, so from then on
        # every message, in every household here, says which chat it came from, and an unregistered chat is
        # refused. No other chat can act as someone, not with --as and not after the speaker changes.
        raise ToolError(
            "Say which chat this came from: one-to-one chats are registered here.",
            hint="Pass --chat <chat-id> with every message and every scheduled routine. A chat that isn't registered "
            "is refused until the owner registers it (who chat).",
            code="which_chat",
        )

    actor = None
    as_member = getattr(args, "as_member", None)
    sender = getattr(args, "from_participant", None)
    if as_member and chat and chat.get("type") == "group":
        raise ToolError(
            "In a group chat, the sender decides who's acting, not --as.",
            hint=f"Pass --from <their handle> (linked with: who link {chat_id} ...), so nobody can act as someone "
            "else.",
            code="use_from_in_groups",
        )
    if as_member and chat and chat.get("member"):
        # A registered direct chat belongs to one adult: nobody else acts from it, so --as can't swap the
        # person (or who sees the reply) for someone with more access.
        owner_of_chat = household.member(chat["member"])
        if owner_of_chat is None or find_member(household, as_member)["id"] != owner_of_chat["id"]:
            raise ToolError(
                f"The chat {chat_id!r} belongs to {household.member_name(chat.get('member'))}, so commands from it "
                "run as them.",
                hint="Leave out --as here. Someone else asks from their own chat.",
                code="chat_belongs_to_someone",
            )
    if as_member:
        actor = find_member(household, as_member)
    elif chat and sender:
        member_id = chat.get("participants", {}).get(sender)
        minor_id = chat.get("minor_participants", {}).get(sender)
        if member_id is None and minor_id:
            minor = household.member(minor_id)
            raise ToolError(
                f"That's {minor['name'] if minor else 'one of the kids'}, who doesn't chat with the agent.",
                hint="Be kind, don't record anything they ask for, and suggest they ask a parent (who can add it "
                "for them).",
                code="minor_cannot_chat",
            )
        if member_id is None:
            raise ToolError(
                f"I don't know who {sender} is in {household.name} yet.",
                hint=f"Ask the owner once who they are, then link them: fridge who link {chat_id} --participant "
                f"{sender} --member <name>. A kid or teen gets noted the same way, so they're recognised and nothing "
                "they ask is recorded. Until then, don't record anything they ask for.",
                code="unknown_participant",
                participant=sender,
            )
        actor = household.member(member_id)
    elif chat and chat.get("type") == "group":
        raise ToolError(
            "In a group chat, say who sent the message.",
            hint=f"Add --from <participant> (their handle in this chat), e.g. --chat {chat_id} --from @alex",
            code="who_is_talking",
        )
    elif chat:
        # A registered direct chat belongs to one adult. If that person is gone, refuse: never fall back to the
        # speaker or the owner, or a removed member could keep acting as someone else.
        actor = household.member(chat.get("member")) if chat.get("member") else None
        if actor is None:
            raise ToolError(
                f"The direct chat {chat_id!r} no longer belongs to a member of {household.name}.",
                hint="Ask the owner to register it again for the right adult: fridge who chat <chat-id> --type "
                "direct --member <name>",
                code="chat_not_linked",
            )
    else:
        speaker = hub.speaker(household.id)
        actor = household.member(speaker) if speaker else None
        if actor is None:
            raise ToolError(
                f"I don't know who's talking in direct chats for {household.name}.",
                hint="The owner sets it once: fridge --as <owner> who speaker <name>. Or pass --as <name>.",
                code="who_is_talking",
            )
    refuse_minor(actor, "act through the agent")

    audience = [actor]
    group = bool(chat and chat.get("type") == "group")
    if group:
        linked = set(chat.get("participants", {}).values())
        audience += [m for m in household.members if m["id"] in linked]
    viewer = Viewer(actor, audience, group=group, minors_present=bool(group and chat.get("minors_present")))
    return Ctx(hub, household, viewer, chat_id)


# --------------------------------------------------------------------------- commands


REGISTER_HINT = ("Ask the owner to register it once: fridge who chat <chat-id> --type group --minors yes|no for a "
                 "group chat, or --type direct --member <name> for one person's own chat.")
def adult_confirmed(ctx: Ctx, member: dict, words, code, why: str | None = None) -> str | None:
    """The owner's words confirming someone is an adult who may chat (already confirmed once: None): a plain yes to
    "Is <name> 18 or older?", perhaps with their age, and that question's code. An answer that says or suggests
    they're under 18 is refused (confirm.owner_yes)."""
    if member["role"] == "owner" or member.get("chat_ok"):
        return None
    return confirm.owner_yes(
        ctx.household, ctx.member["id"], f"adult|{member['id']}",
        f"Is {member['name']} 18 or older? Fridge Door is for adults to chat with; kids and teens take part through "
        "a parent.",
        words, code,
        why=why or f"Before {member['name']} can chat with the agent, the owner must confirm they're 18 or older.",
        adult=member["name"],
    )


def _yes_no(value: str, flag: str) -> bool:
    key = fold(value)
    if key in ("yes", "y", "true", "1"):
        return True
    if key in ("no", "n", "false", "0"):
        return False
    raise ToolError(f"{flag} needs yes or no.", code="usage")


def cmd_chat(ctx: Ctx, args) -> dict:
    ctx.viewer.require_owner("register chats")
    chat_id = clean_text(args.chat_id, "chat id", max_len=200)
    if args.type == "group" and args.minors is None:
        raise ToolError(
            "Is anyone under 18 in this group chat?",
            hint="Ask the owner, then pass --minors yes or --minors no. With minors present, replies there only "
            "show what kids may see, and nothing a child writes is recorded.",
            code="needs_owner",
            ask_owner="Is anyone under 18 in this group chat?",
        )
    owner_of_chat, words = None, None
    if args.type == "direct":
        owner_of_chat = find_member(ctx.household, args.member)["id"] if args.member else ctx.member["id"]
    # A chat belongs to one household. Only the owner's own one-to-one chat is also in the households they add
    # (household add), and there it stays theirs.
    here = ctx.household.meta().get("chats", {}).get(chat_id) or {}
    elsewhere = [h for h in ctx.hub.chat_homes(chat_id) if h != ctx.household.id]
    if elsewhere and not (owner_of_chat and here.get("type") == "direct" and here.get("member") == owner_of_chat):
        raise ToolError(
            f"The chat {chat_id!r} already belongs to another household.",
            hint="Remove it there first (who forget-chat), or use a different chat id.",
            code="chat_in_other_household",
        )
    if owner_of_chat:
        refuse_minor(ctx.household.member(owner_of_chat))
        words = adult_confirmed(ctx, ctx.household.member(owner_of_chat), args.owner_confirmed, args.confirm)
    hh = ctx.household
    with hh.transaction(dry_run=args.dry_run):
        if words:
            hh.member(owner_of_chat)["chat_ok"] = {"owner_said": words, "at": now_stamp(), "by": ctx.member["id"]}
        chats = hh.meta().setdefault("chats", {})
        existing = chats.get(chat_id, {})
        record = {
            "type": args.type,
            "minors_present": _yes_no(args.minors, "--minors") if args.type == "group" else False,
            "participants": existing.get("participants", {}),
            "registered_at": existing.get("registered_at", now_stamp()),
        }
        if owner_of_chat:
            record["member"] = owner_of_chat
            record["participants"] = {}
        chats[chat_id] = record
        hh.touch("household")
        hh.log("chat.register", ctx.member["id"], chat=chat_id, type=args.type)
    if not args.dry_run:
        with ctx.hub.transaction() as data:
            data.setdefault("chats", {}).setdefault(chat_id, hh.id)
    kind = "group chat" if args.type == "group" else "direct chat"
    extra = ""
    if record["minors_present"]:
        extra = " Anyone under 18 is treated as present, so replies there stay kid-safe."
    return {
        "chat": chat_id,
        "record": record,
        "dry_run": args.dry_run,
        "summary": f"{'Would register' if args.dry_run else 'Registered'} the {kind} {chat_id} for {hh.name}.{extra}",
        "next": "Link each adult once: fridge who link <chat-id> --participant <handle> --member <name>"
        if args.type == "group"
        else None,
    }


def cmd_link(ctx: Ctx, args) -> dict:
    ctx.viewer.require_owner("link chat participants")
    hh = ctx.household
    chat = hh.meta().get("chats", {}).get(args.chat_id)
    if chat is None or chat.get("type") != "group":
        raise ToolError(
            f"{args.chat_id!r} isn't a registered group chat in {hh.name}.",
            hint="Register it first: fridge who chat <chat-id> --type group --minors yes|no",
            code="chat_not_linked",
        )
    member = find_member(hh, args.member)
    participant = clean_text(args.participant, "participant", max_len=200)
    if access.is_minor(member):
        return _note_minor(ctx, chat, args, member, participant)
    words = adult_confirmed(ctx, member, args.owner_confirmed, args.confirm)
    with hh.transaction(dry_run=args.dry_run):
        m = hh.member(member["id"])
        chat = hh.meta()["chats"][args.chat_id]
        taken = chat["participants"].get(participant)
        if taken and taken != m["id"]:
            raise ToolError(
                f"{participant} is already linked to {hh.member_name(taken)} in this chat.",
                hint="Unlink them first: fridge who unlink <chat-id> --participant <handle>",
                code="already_linked",
            )
        chat["participants"][participant] = m["id"]
        chat.get("minor_participants", {}).pop(participant, None)
        if words and m["role"] != "owner" and not m.get("chat_ok"):
            m["chat_ok"] = {"owner_said": words, "at": now_stamp(), "by": ctx.member["id"]}
        hh.touch("household")
        hh.log("chat.link", ctx.member["id"], chat=args.chat_id, member=m["id"])
    return {
        "chat": args.chat_id,
        "participant": participant,
        "member": {"id": member["id"], "name": member["name"]},
        "dry_run": args.dry_run,
        "summary": f"{'Would link' if args.dry_run else 'Linked'} {participant} to {member['name']} in {args.chat_id}.",
    }


def _note_minor(ctx: Ctx, chat: dict, args, member: dict, participant: str) -> dict:
    """Remember a kid's or teen's handle in a group chat: their messages are then recognised (and never acted on),
    and the chat counts as having children in it."""
    hh = ctx.household
    with hh.transaction(dry_run=args.dry_run):
        chat = hh.meta()["chats"][args.chat_id]
        if participant in chat.get("participants", {}):
            raise ToolError(f"{participant} is linked to {hh.member_name(chat['participants'][participant])}.",
                            hint="Unlink them first: fridge who unlink <chat-id> --participant <handle>",
                            code="already_linked")  # fmt: skip
        chat.setdefault("minor_participants", {})[participant] = member["id"]
        chat["minors_present"] = True
        hh.touch("household")
        hh.log("chat.note_minor", ctx.member["id"], chat=args.chat_id, member=member["id"])
    verb = "Would note" if args.dry_run else "Noted"
    summary = (f"{verb} {participant} as {member['name']} ({member['role']}) in {args.chat_id}. They don't chat with "
               "the agent: their messages are recognised and nothing they ask is recorded, and the chat now counts "
               "as having kids in it.")  # fmt: skip
    return {"chat": args.chat_id, "participant": participant, "member": {"id": member["id"], "name": member["name"]},
            "dry_run": args.dry_run, "summary": summary}  # fmt: skip


def cmd_unlink(ctx: Ctx, args) -> dict:
    ctx.viewer.require_owner("unlink chat participants")
    hh = ctx.household
    with hh.transaction():
        chat = hh.meta().get("chats", {}).get(args.chat_id)
        if not chat or args.participant not in chat.get("participants", {}):
            raise ToolError(
                f"{args.participant} isn't linked in {args.chat_id}.", hint="See links with: fridge who show",
                code="not_found",
            )  # fmt: skip
        member_id = chat["participants"].pop(args.participant)
        hh.touch("household")
        hh.log("chat.unlink", ctx.member["id"], chat=args.chat_id, member=member_id)
    return {"summary": f"Unlinked {args.participant} from {args.chat_id}."}


def cmd_forget_chat(ctx: Ctx, args) -> dict:
    ctx.viewer.require_owner("remove chats")
    hh = ctx.household
    with hh.transaction():
        if hh.meta().get("chats", {}).pop(args.chat_id, None) is None:
            raise ToolError(f"No chat {args.chat_id!r} in {hh.name}.", code="not_found")
        hh.touch("household")
        hh.log("chat.forget", ctx.member["id"], chat=args.chat_id)
    with ctx.hub.transaction() as data:
        ctx.hub.rehome_chat(data, args.chat_id, hh.id)
    shutil.rmtree(hh.chat_output(args.chat_id), ignore_errors=True)  # its printouts go with it
    return {"summary": f"Removed the chat {args.chat_id} and its printouts from {hh.name}."}


def cmd_speaker(ctx: Ctx, args) -> dict:
    ctx.viewer.require_owner("choose who's talking in direct chats")
    if ctx.chat_id:
        raise ToolError(
            "Each chat here already says who's talking, so there's no speaker to choose.",
            hint="The speaker is only for a platform without chat ids, such as a terminal. Register each adult's own "
            "chat instead: fridge who chat <chat-id> --type direct --member <name>",
            code="uses_chats",
        )
    member = find_member(ctx.household, args.member)
    refuse_minor(member)
    words = adult_confirmed(ctx, member, args.owner_confirmed, args.confirm)
    if words:
        with ctx.household.transaction():
            ctx.household.member(member["id"])["chat_ok"] = {"owner_said": words, "at": now_stamp(),
                                                             "by": ctx.member["id"]}  # fmt: skip
            ctx.household.touch("household")
    with ctx.hub.transaction() as data:
        data.setdefault("speakers", {})[ctx.household.id] = member["id"]
    return {
        "speaker": {"id": member["id"], "name": member["name"]},
        "summary": f"In direct chats, Fridge Door now treats the person talking as {member['name']}.",
    }


def cmd_show(ctx: Ctx, args) -> dict:
    hh = ctx.household
    chats = hh.meta().get("chats", {})
    items = []
    for chat_id, chat in sorted(chats.items()):
        if args.chat_id and chat_id != args.chat_id:
            continue
        items.append(
            {
                "chat": chat_id,
                "type": chat["type"],
                "minors_present": chat.get("minors_present", False),
                "member": hh.member_name(chat.get("member")),
                "participants": {p: hh.member_name(m) for p, m in chat.get("participants", {}).items()},
            }
        )
    speaker = ctx.hub.speaker(hh.id)
    own = [f"{item['chat']} ({item['member']})" for item in items if item["type"] == "direct"]
    summary = f"{plural(len(items), 'chat')} linked to {hh.name}"
    summary += f"; one-to-one chats: {', '.join(own)}" if own else ""
    if ctx.hub.direct_chats_in_use():
        summary += "; every message names its chat, and a chat nobody registered is refused."
        speaker = None
    else:
        summary += f"; any other direct chat speaks as {hh.member_name(speaker)}."
    return {"you": ctx.describe(), "speaker": hh.member_name(speaker), "chats": items, "summary": summary}


def cmd_whoami(ctx: Ctx, args) -> dict:
    info = ctx.describe()
    who = info["member"]["name"]
    where = f"the group chat {ctx.chat_id}" if ctx.viewer.group else "a direct chat"
    return dict(info, summary=f"You're {who} in {ctx.household.name}, in {where}.")


def drop_member_chats(household: Household, member_id: str) -> tuple:
    """Take a member out of every chat: delete their direct chats and unlink them from group chats.

    Returns (deleted direct chat ids, group chat ids they were unlinked from). The caller then removes the
    deleted chats from hub.json with clear_member_from_hub().
    """
    deleted, unlinked = [], []
    chats = household.meta().get("chats", {})
    for chat_id in list(chats):
        chat = chats[chat_id]
        if chat.get("type") == "direct" and chat.get("member") == member_id:
            del chats[chat_id]
            deleted.append(chat_id)
            continue
        for participant, linked in list(chat.get("participants", {}).items()):
            if linked == member_id:
                del chat["participants"][participant]
                unlinked.append(chat_id)
        for participant, noted in list(chat.get("minor_participants", {}).items()):
            if noted == member_id:  # a kid's noted handle goes too
                del chat["minor_participants"][participant]
                unlinked.append(chat_id)
    if deleted or unlinked:
        household.touch("household")
    household.dropped_chats.extend(deleted)
    return deleted, sorted(set(unlinked))


def clear_member_from_hub(hub: Hub, household_id: str, member_id: str, deleted_chats) -> None:
    """Forget a member's deleted direct chats in hub.json, and stop treating them as the direct-chat speaker."""
    with hub.transaction() as data:
        for chat_id in deleted_chats:
            hub.rehome_chat(data, chat_id, household_id)
        if data.get("speakers", {}).get(household_id) == member_id:
            data["speakers"][household_id] = None


def _forget_hook(household: Household, member_id: str) -> list:
    deleted, unlinked = drop_member_chats(household, member_id)
    return [f"deleted their direct chat {c}" for c in deleted] + [f"unlinked from {c}" for c in unlinked]


def register(cli) -> None:
    from .members import FORGET_HOOKS

    FORGET_HOOKS.append(_forget_hook)
    who = cli.group("who", "Who's talking: link chats and adult participants to members (owner).")
    p = who.add(
        "chat",
        "Register a chat with this household (owner). Group chats must say whether anyone under 18 is in them.",
        [
            "fridge who chat family-group --type group --minors yes",
            "fridge who chat jo-dm --type direct --member Jo",
            'fridge who chat jo-dm --type direct --member Jo --owner-confirmed "yes, Jo is 34" '
            "--confirm 1c5e2a0-8d41f2-3f9b27d41c",
        ],
        cmd_chat,
    )
    p.add_argument("chat_id", help="The chat's id, as the platform gives it")
    p.add_argument("--type", choices=("group", "direct"), required=True)
    p.add_argument("--minors", help="yes or no: is anyone under 18 in this group chat?")
    p.add_argument("--member", help="For a direct chat: whose chat it is (default: you)")
    p.add_argument("--owner-confirmed", help="The owner's own words confirming that person is 18 or older")
    p.add_argument("--confirm", help="The code that came with the owner's question (confirm)")
    p.add_argument("--dry-run", action="store_true", help="Show what would happen without saving")
    p = who.add(
        "link",
        "Link a group-chat participant to an adult member (owner). The first link asks the owner to confirm 18+. "
        "A kid's or teen's handle is noted instead: they're recognised, never act, and the chat counts as having "
        "kids in it.",
        [
            "fridge who link family-group --participant @sam --member Sam",
            'fridge who link family-group --participant @sam --member Sam --owner-confirmed "yes, Sam is 42" '
            "--confirm 1c5e2a0-8d41f2-3f9b27d41c",
            "fridge who link family-group --participant @arjun --member Arjun",
        ],
        cmd_link,
    )
    p.add_argument("chat_id")
    p.add_argument("--participant", required=True, help="Their handle or id in that chat")
    p.add_argument("--member", required=True, help="The member (name or id)")
    p.add_argument("--owner-confirmed", help="The owner's own words confirming the person is 18 or older")
    p.add_argument("--confirm", help="The code that came with the owner's question (confirm)")
    p.add_argument("--dry-run", action="store_true")
    p = who.add("unlink", "Unlink a participant from a group chat (owner).",
                ["fridge who unlink family-group --participant @sam"], cmd_unlink)  # fmt: skip
    p.add_argument("chat_id")
    p.add_argument("--participant", required=True)
    p = who.add("forget-chat", "Remove a chat from this household (owner).",
                ["fridge who forget-chat family-group"], cmd_forget_chat)  # fmt: skip
    p.add_argument("chat_id")
    p = who.add("speaker", "Choose who's talking in direct chats for this household (owner).",
                ["fridge who speaker Ana"], cmd_speaker)  # fmt: skip
    p.add_argument("member")
    p.add_argument("--owner-confirmed", help="The owner's own words confirming that person is 18 or older")
    p.add_argument("--confirm", help="The code that came with the owner's question (confirm)")
    p = who.add("show", "Show the linked chats, their participants and the direct-chat speaker.",
                ["fridge who show", "fridge who show family-group"], cmd_show)  # fmt: skip
    p.add_argument("chat_id", nargs="?")
    who.add("am-i", "Say which member and household this message runs as, and who will see the reply.",
            ["fridge who am-i", "fridge who am-i --chat family-group --from @ana"], cmd_whoami)  # fmt: skip
