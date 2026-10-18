"""The owner's yes: a clear yes to one specific question, tied to that question by a confirmation code.

What can't be undone, or opens something up (deleting the household, removing someone, letting an adult chat with the
agent, showing sensitive notes in groups, reminders outside the chat), waits for the household owner. The toolkit
refuses with the exact question in `ask_owner` and a code in `confirm` that belongs to that action, that target and
that owner, for a day. The agent asks the question word for word; only if the owner says yes does it run the command
again with `--owner-confirmed "<their exact words>" --confirm <code>`.

The words must be a clear yes ("yes", "yep", "confirm", "go ahead", "do it"). Any no anywhere in them ("absolutely
not", "I said no", "please don't") is refused as a no. A vague, unsure or conditional answer ("ok", "sure", "k", an
emoji, "maybe", a question, "yes but after dinner", "remove Zoe instead") is refused as unclear: ask again.
"""

from __future__ import annotations

import hashlib
import hmac
import re

from .util import ToolError, clean_text, fold, now

CODE_HOURS = 24

_YES = re.compile(r"\b(?:ye+s+|yeah+|yep+|yup+|yea|aye|oui|ja|sim|confirm(?:ed|ing)?|go ahead|go for it|do it|"
                  r"please do|proceed|approved?|affirmative|absolutely|definitely|certainly|of course)\b")
_NO = re.compile(r"\b(?:no+|nope|nah|naw|not|never|none|nothing|dont|doesnt|didnt|isnt|wont|cant|cannot|shouldnt|"
                 r"wouldnt|aint|do not|cancel|stop|abort|undo|negative|non|nein|nee|nej|nei|nao|nie)\b|\w+n't\b")
_UNSURE = re.compile(r"[?<>]|\b(?:maybe|perhaps|probably|possibly|might|guess|think|unsure|idk|dunno|h+m+|huh|"
                     r"wait|hold|later|tomorrow|tonight|soon|after|until|unless|if|but|instead|except|nevermind|"
                     r"never mind|forget|skip|rather)\b")

# Signs in an answer to "Is <name> 18 or older?" that the person is under 18: an age under 18 in digits or words,
# teen and school words, or "almost 18". A family word ("my son") needs an adult age with it ("my son is 25").
_UNDER_18 = re.compile(
    r"(?<![\d.])(?:[1-9]|1[0-7])(?!\d)"
    r"|\b(?:two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen)\b"
    r"|\b(?:teen\w*|adolescent|minor|underage|under age|under 18)\b"
    r"|\b(?:grades?|school|highschool|elementary|kindergarten|preschool|secondary|junior high|middle school)\b"
    r"|\b(?:almost|nearly|turning|turns|soon|will be|'ll be)\s+(?:18|eighteen)\b|\b(?:18|eighteen)\s+(?:next|soon)\b"
)
_FAMILY = re.compile(r"\b(?:son|daughter|child|children|kid|kids|stepson|stepdaughter|grandson|granddaughter|"
                     r"grandchild|grandkid|baby|toddler)\b")
_ADULT_AGE = re.compile(r"(?<![\d.])(?:1[89]|[2-9]\d|1[01]\d|120)(?![\d.])")

ASK_HINT = ('Ask the owner the question in ask_owner, word for word, and wait. Only if they say yes, run this again '
            'with --owner-confirmed "<their exact words>" --confirm <the code in confirm>. Never answer it yourself.')


def _minutes() -> int:
    return int(now("UTC").timestamp() // 60)


def _sign(hh, action: str, owner_id: str, expires: int) -> str:
    """Ties a code to this household's folder, the action and its target, the owner and the expiry."""
    key = hashlib.sha256(f"fridge-door-confirm|{hh.path.resolve()}|{hh.id}".encode()).digest()
    return hmac.new(key, f"{action}|{owner_id}|{expires}".encode(), hashlib.sha256).hexdigest()[:10]


def code_for(hh, action: str, owner_id: str) -> str:
    expires = _minutes() + CODE_HOURS * 60
    return f"{expires:x}-{_sign(hh, action, owner_id, expires)}"


def _code_ok(hh, action: str, owner_id: str, code) -> bool:
    match = re.fullmatch(r"([0-9a-f]{1,12})-([0-9a-f]{10})", str(code or "").strip().lower())
    if not match:
        return False
    expires = int(match.group(1), 16)
    if not _minutes() <= expires <= _minutes() + CODE_HOURS * 60:
        return False
    return hmac.compare_digest(match.group(2), _sign(hh, action, owner_id, expires))


def _reads_as_no(text: str) -> bool:
    return bool(_NO.search(fold(text).replace("’", "'")))


def _is_clear_yes(text: str) -> bool:
    words = fold(text).replace("’", "'")
    return bool(_YES.search(words)) and not _UNSURE.search(words) and not _NO.search(words)


def adult_check(name: str, text: str) -> None:
    """For "Is <name> 18 or older?": refuses an answer that says or suggests they're under 18."""
    words = fold(text).replace("’", "'")
    if _UNDER_18.search(words):
        raise ToolError(
            f"The owner's answer says or suggests {name} is under 18, so they can't chat with the agent.",
            hint=f"If they're under 18, make them a kid or teen (member access {name} --role teen); they take part "
            "through a parent. If they're 18 or older, ask again for a plain yes.",
            code="minor_cannot_chat",
        )
    if _FAMILY.search(words) and not _ADULT_AGE.search(words):
        raise ToolError(
            f"The owner's answer doesn't say {name} is 18 or older.",
            hint="Ask again for a plain yes (\"yes, they're 18 or older\").",
            code="unclear_answer",
        )


def owner_yes(hh, owner_id: str, action: str, question: str, words, code, *, why: str, check=None) -> str:
    """The owner's exact words, once they're a clear yes to `question`, passed with that question's code. Otherwise
    refuses: with the question and a code when there's no answer yet (or no code, an old one or another question's),
    as a no, or as unclear. `action` names the action and its target, e.g. "member.remove|M3"."""
    text = clean_text(words, "owner's answer", max_len=500, required=False)
    if not text:
        raise ToolError(why, hint=ASK_HINT, code="needs_owner", ask_owner=question,
                        confirm=code_for(hh, action, owner_id))  # fmt: skip
    if _reads_as_no(text):
        raise ToolError(
            "The owner's answer reads as a no, so nothing was changed.",
            hint="Tell them it wasn't done. If they change their mind, start again and ask the question afresh.",
            code="owner_declined",
        )
    if check:
        try:
            check(text)
        except ToolError as exc:
            if exc.code == "unclear_answer":  # ask again: with the question and a code
                exc.ask_owner, exc.extra["confirm"] = question, code_for(hh, action, owner_id)
            raise
    if not _code_ok(hh, action, owner_id, code):
        raise ToolError(
            "That answer isn't tied to this question: the confirmation code is missing, out of date or for "
            "something else, so nothing was changed.",
            hint=ASK_HINT, code="needs_owner", ask_owner=question, confirm=code_for(hh, action, owner_id),
        )
    if not _is_clear_yes(text):
        raise ToolError(
            "The owner's answer isn't a clear yes, so nothing was changed.",
            hint="Ask the question again and wait for a plain yes, such as \"yes\", \"confirm\" or \"go ahead\". "
            "\"ok\", \"sure\", an emoji, a question or a yes with a condition isn't enough.",
            code="unclear_answer", ask_owner=question, confirm=code_for(hh, action, owner_id),
        )
    return text
