"""Command line: python3 fridge.py <command> [<action>] [options]. Every command prints one JSON object."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .store import Hub
from .util import ToolError, default_home, emit, plural

EPILOG = """Examples:
  fridge doctor
  fridge setup --name "The Garcias" --members "Ana, Luis, Sofia (kid)" --country MX
  fridge --home /tmp/fridge-demo demo --region CA
  fridge member list
  fridge who am-i --chat family-group --from @ana

Who's talking: --as <adult member>, or --chat <chat-id> --from <participant> once the chat is linked; with
neither, the household's direct-chat speaker. These options work before or after the command.
Data folder: --home, else $FRIDGE_HOME, else /workspace/fridge-door (if /workspace exists), else ~/fridge-door.
Every command prints JSON: {"ok": true, "summary": ...} or {"ok": false, "error", "hint", "code"}; an
"ask_owner" field is a question only the household owner may answer."""

# Options every command accepts, before or after the command name.
COMMON = (
    ("--home", {"help": "Data folder"}),
    ("--household", {"help": "Which household (name or id); default: the active one"}),
    ("--as", {"dest": "as_member", "metavar": "MEMBER", "help": "Run as this adult member (name or id)"}),
    ("--chat", {"help": "The chat the message came from (registered with: who chat)"}),
    ("--from", {"dest": "from_participant", "metavar": "PARTICIPANT", "help": "Who sent it, in that chat"}),
)


class _Parser(argparse.ArgumentParser):
    def error(self, message):  # usage mistakes come back as JSON too, so the agent can always parse the output
        emit({"ok": False, "error": message, "hint": f"Run: {self.prog} --help", "code": "usage"}, 2)


def _add_common(parser, suppress: bool) -> None:
    group = parser.add_argument_group("who's talking (any command)")
    for flag, kwargs in COMMON:
        group.add_argument(flag, default=argparse.SUPPRESS if suppress else None, **kwargs)


def _make(sub, name: str, help_text: str, examples: list, func, needs: str):
    parser = sub.add_parser(
        name,
        help=help_text,
        description=help_text,
        epilog="Examples:\n  " + "\n  ".join(examples),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_common(parser, suppress=True)
    parser.set_defaults(func=func, needs=needs)
    return parser


class _Group:
    def __init__(self, name: str, parser, sub):
        self.name = name
        self.parser = parser
        self.sub = sub

    def add(self, name: str, help_text: str, examples: list, func, needs: str = "member"):
        return _make(self.sub, name, help_text, examples, func, needs)


class Commands:
    """What feature modules use to register their commands (see each module's register())."""

    def __init__(self, sub):
        self.sub = sub

    def top(self, name: str, help_text: str, examples: list, func, needs: str = "member"):
        return _make(self.sub, name, help_text, examples, func, needs)

    def group(self, name: str, help_text: str) -> _Group:
        parser = self.sub.add_parser(
            name, help=help_text, description=help_text, formatter_class=argparse.RawDescriptionHelpFormatter
        )
        _add_common(parser, suppress=True)
        sub = parser.add_subparsers(dest="action", parser_class=_Parser)

        def _no_action(_home, _args, _parser=parser, _name=name):
            actions = sorted(sub.choices)
            raise ToolError(f"{_name} needs an action.", hint=f"Use one of: {', '.join(actions)}.", code="usage")

        parser.set_defaults(func=_no_action, needs="none")
        return _Group(name, parser, sub)


def cmd_selftest(home, args) -> dict:
    from .selftest import run_selftest

    return run_selftest()


def _flag_notices(ctx, args, result: dict) -> dict:
    """Every reply to a member says when notices are waiting for them, so they hear the next time they talk."""
    if args.command == "notices" or not ctx.household.path.exists():
        return result
    waiting = [
        n
        for n in ctx.household.fresh("notices")["notices"]
        if n["to"] == ctx.member["id"] and not n.get("delivered_at")
    ]
    if waiting:
        result = dict(result)
        result["pending_notices"] = len(waiting)
        news = f"{ctx.member['name']} has {plural(len(waiting), 'new notice')}"
        if ctx.viewer.group:
            result["notices_hint"] = (
                f"{news}. Don't read them out here: they're shown in a direct chat only (fridge notices list)."
            )
        else:
            result["notices_hint"] = f"{news}: run `fridge notices list` and tell them."
    return result


def build_parser() -> argparse.ArgumentParser:
    from . import (budget, context, demo, events, ics, mealplan, members, notes, notices, onboarding, printables,
                   recipes, reminders, shopping, today, todos, trash)

    parser = _Parser(
        prog="fridge",
        description="Fridge Door: a household organizer for any household in any country. "
        "Shared calendar, to-dos and chores, grocery lists, recipes, meal plans, notes and a budget.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=__version__)
    _add_common(parser, suppress=False)
    # No metavar: argparse then lists every registered command, so --help and references/cli.md stay complete.
    sub = parser.add_subparsers(dest="command", parser_class=_Parser)
    cli = Commands(sub)
    onboarding.register(cli)
    cli.top("selftest", "Run the built-in checks.", ["fridge selftest"], cmd_selftest, needs="none")
    demo.register(cli)
    members.register(cli)
    context.register(cli)
    shopping.register(cli)
    todos.register(cli)
    notices.register(cli)
    today.register(cli)
    events.register(cli)
    recipes.register(cli)
    mealplan.register(cli)
    notes.register(cli)
    budget.register(cli)
    trash.register(cli)
    reminders.register(cli)
    ics.register(cli)
    printables.register(cli)
    return parser


def main(argv=None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        sys.exit(0)
    home = Path(args.home).expanduser() if getattr(args, "home", None) else default_home()
    try:
        needs = getattr(args, "needs", "member")
        if needs == "none":
            result = args.func(home, args)
        elif needs == "hub":
            result = args.func(Hub(home), args)
        else:
            from .context import resolve

            ctx = resolve(Hub(home), args)
            result = args.func(ctx, args)
            result = _flag_notices(ctx, args, result or {})
    except ToolError as exc:
        payload = {"ok": False, "error": exc.message, "code": exc.code}
        if exc.hint:
            payload["hint"] = exc.hint
        if exc.ask_owner:
            payload["ask_owner"] = exc.ask_owner
        payload.update(exc.extra)
        emit(payload, 1)
    except KeyboardInterrupt:
        emit({"ok": False, "error": "Interrupted."}, 130)
    payload = {"ok": True}
    payload.update({k: v for k, v in (result or {}).items() if v is not None or k in ("dry_run",)})
    emit(payload, 0 if payload["ok"] else 1)


if __name__ == "__main__":  # pragma: no cover
    main()
