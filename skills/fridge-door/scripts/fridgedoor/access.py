"""Who may see and change what: roles, the eight modules, access levels, and what a group chat may show.

Every command runs as a member, and the toolkit (not the agent's good behaviour) refuses anything that member's
access doesn't allow. In a group chat, a reply may only show what everyone in the chat may see.
"""

from __future__ import annotations

from .util import ToolError

ROLES = ("owner", "adult", "teen", "kid")
ADULT_ROLES = ("owner", "adult")
MINOR_ROLES = ("teen", "kid")

# none < view < edit: the index is the rank.
LEVELS = ("none", "view", "edit")

# The eight modules, in display order.
MODULES = ("calendar", "todos", "shopping_lists", "grocery", "recipes", "meal_plan", "notes", "budget")

MODULE_LABELS = {
    "calendar": "Calendar",
    "todos": "To-dos",
    "shopping_lists": "Shopping lists",
    "grocery": "Grocery",
    "recipes": "Recipes",
    "meal_plan": "Meal plan",
    "notes": "Notes",
    "budget": "Budget",
}

_ALL_EDIT = {module: "edit" for module in MODULES}

# Role presets. The owner can change any member's levels afterwards; the member's own map is the truth.
PRESETS = {
    "owner": dict(_ALL_EDIT),
    "adult": dict(_ALL_EDIT),
    "teen": {
        "calendar": "view",
        "todos": "edit",
        "shopping_lists": "edit",
        "grocery": "edit",
        "recipes": "view",
        "meal_plan": "view",
        "notes": "view",
        "budget": "none",
    },
    "kid": {
        "calendar": "none",
        "todos": "edit",
        "shopping_lists": "none",
        "grocery": "view",
        "recipes": "none",
        "meal_plan": "none",
        "notes": "none",
        "budget": "none",
    },
}

# Each list kind belongs to one module: a kid with grocery=view and shopping_lists=none sees the grocery list
# but not the hardware-store list.
LIST_KIND_MODULE = {"todo": "todos", "shopping": "shopping_lists", "grocery": "grocery"}

# Module aliases people (and agents) use.
_ALIASES = {
    "calendar": "calendar",
    "events": "calendar",
    "todos": "todos",
    "todo": "todos",
    "to-dos": "todos",
    "tasks": "todos",
    "chores": "todos",
    "shopping": "shopping_lists",
    "shopping_lists": "shopping_lists",
    "shopping-lists": "shopping_lists",
    "grocery": "grocery",
    "groceries": "grocery",
    "recipes": "recipes",
    "meal_plan": "meal_plan",
    "meal-plan": "meal_plan",
    "mealplan": "meal_plan",
    "meals": "meal_plan",
    "notes": "notes",
    "budget": "budget",
    "money": "budget",
}


def rank(level) -> int:
    """none=0, view=1, edit=2. A missing or unknown value ranks as none."""
    try:
        return LEVELS.index(level)
    except ValueError:
        return 0


def module_name(text: str) -> str:
    key = str(text or "").strip().lower().replace(" ", "_")
    if key in _ALIASES:
        return _ALIASES[key]
    raise ToolError(
        f"{text!r} isn't a module.",
        hint="Modules: " + ", ".join(MODULES) + ".",
        code="bad_permissions",
    )


def validate_access(access) -> dict:
    """A permissions map must have exactly the eight modules, each none, view or edit."""
    if not isinstance(access, dict) or set(access) != set(MODULES) or any(v not in LEVELS for v in access.values()):
        raise ToolError(
            "Those access settings aren't valid.",
            hint="Every member needs exactly these modules, each none, view or edit: " + ", ".join(MODULES) + ".",
            code="bad_permissions",
        )
    return {module: access[module] for module in MODULES}


def preset(role: str) -> dict:
    if role not in PRESETS:
        raise ToolError(f"{role!r} isn't a role.", hint="Roles: owner, adult, teen, kid.", code="bad_role")
    return dict(PRESETS[role])


def level(member: dict, module: str) -> str:
    return (member.get("access") or {}).get(module, "none") if member else "none"


def can(member: dict, module: str, needed: str) -> bool:
    """True when the member's level for module is at least needed."""
    return rank(level(member, module)) >= rank(needed)


def is_owner(member: dict) -> bool:
    return bool(member) and member.get("role") == "owner"


def is_adult(member: dict) -> bool:
    return bool(member) and member.get("role") in ADULT_ROLES


def is_minor(member: dict) -> bool:
    return bool(member) and member.get("role") in MINOR_ROLES


def in_their_day(member: dict, module: str) -> bool:
    """Whether a member's Today summary covers a module. An adult's day follows their own access. A kid or teen
    never reads theirs (a parent does, for them), so for them only the person asking and the chat decide."""
    return is_minor(member) or can(member, module, "view")


# A stand-in for a child who is in a group chat but isn't (and can't be) linked to a member.
MINOR_VIEWER = {"id": "_minor", "name": "a child", "role": "kid", "access": dict(PRESETS["kid"])}


class Viewer:
    """Who is acting, and who will see the reply.

    In a direct chat the audience is just the actor. In a group chat it's every linked member, plus a kid-level
    stand-in when the owner said children are in the chat. Anything shown must be visible to the whole audience.
    """

    def __init__(self, actor: dict, audience: list | None = None, group: bool = False, minors_present: bool = False):
        self.actor = actor
        people = [actor] + [m for m in (audience or []) if m and m.get("id") != actor.get("id")]
        if minors_present:
            people.append(MINOR_VIEWER)
        self.audience = people
        self.group = group
        self.minors_present = minors_present

    @property
    def actor_id(self) -> str:
        return self.actor["id"]

    def audience_ids(self) -> set:
        return {m["id"] for m in self.audience}

    def can_act(self, module: str, needed: str) -> bool:
        return can(self.actor, module, needed)

    def require(self, module: str, needed: str, what: str = "do that") -> None:
        """Refuse unless the actor has at least `needed` on module."""
        if not self.can_act(module, needed):
            have = level(self.actor, module)
            raise ToolError(
                f"{self.actor['name']} can't {what}: their {MODULE_LABELS[module]} access is {have}.",
                hint=f"Only the owner can change access (member access {self.actor['name']} --set {module}={needed}).",
                code="not_authorized",
            )

    def require_owner(self, what: str = "do that") -> None:
        if not is_owner(self.actor):
            raise ToolError(
                f"Only the household owner can {what}.",
                hint="Ask the owner to do it, or to make the change for you.",
                code="not_authorized",
            )

    def sees(self, module: str) -> bool:
        """Everyone in the audience may view this module."""
        return all(can(person, module, "view") for person in self.audience)

    def require_sees(self, module: str) -> None:
        """For read commands: the actor needs view access, and in a group so does everyone present."""
        self.require(module, "view", f"see {MODULE_LABELS[module].lower()}")
        if not self.sees(module):
            hidden = [p["name"] for p in self.audience if not can(p, module, "view")]
            raise ToolError(
                f"{MODULE_LABELS[module]} can't be shown in this chat: {', '.join(hidden)} can't see it.",
                hint="Ask for it in a direct chat instead.",
                code="hidden_in_group",
            )

    def sees_private_of(self, member_id: str) -> bool:
        """A member's private things (their personal list, private events or notes) show only to that member, in a
        direct chat. Never in a group: people who aren't linked yet may be reading too."""
        return not self.group and self.audience_ids() == {member_id}

    def sees_selected(self, member_ids) -> bool:
        """Something shared with selected members shows only when everyone present is one of them."""
        allowed = set(member_ids or ())
        return self.audience_ids() <= allowed
