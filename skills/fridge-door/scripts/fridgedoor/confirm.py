"""The owner's yes: a plain yes to one specific question, tied to that question by a one-time confirmation code.

What can't be undone, or opens something up (deleting the household, removing someone, letting an adult chat with the
agent, showing sensitive notes in groups, reminders outside the chat), waits for the household owner. The toolkit
refuses with the exact question in `ask_owner` and a code in `confirm` that belongs to that action, that target and
that owner, for a day, and works once. The agent asks the question word for word; only if the owner says yes does it
run the command again with `--owner-confirmed "<their exact words>" --confirm <code>`.

Only a plain yes counts, and it must be the whole answer: "yes", "yep", "yeah", "yup", "confirm", "go ahead" or
"do it", with "please", commas, full stops and exclamation marks, and the question's own words ("yes, remove Luis",
"yes, delete it"). A no anywhere is refused as a no. Everything else is refused as unclear, so the agent asks again:
"ok", "sure", an emoji, a question, a condition or a delay ("yes, next week"), a joke ("yes lol jk") and a yes that
names someone else ("yes, remove Zoe" when the question is about Luis). The 18-or-older question also takes one age
of 18 or over ("yes, she's 19", "yes, Jo is 34"); an answer that says or suggests they're under 18 is refused as such.

A code proves the toolkit asked that question, not that the owner saw it: the agent is trusted to ask them.
"""

from __future__ import annotations

import functools
import hashlib
import hmac
import re
import secrets

from .util import ToolError, clean_text, fold, utc_now

CODE_HOURS = 24
CLOCK_SLACK = 60  # minutes: a code still works if the computer's clock is set back a little

# A plain yes opens the answer ("please" may come first); after it, only these and the question's own words.
_YES = ("yes", "yep", "yeah", "yup", "confirm", "confirmed", "go ahead", "do it", "please do")
_THEN = _YES + ("please",)
_ON_ITS_OWN = ("oui", "ja", "si", "sim")  # a yes in another language, as the whole answer
_ADULT_WORDS = ("he", "she", "they", "is", "are", "he's", "she's", "they're", "an adult", "already", "turned",
                "years", "years old", "or older", "over")  # "yes, she's 19", "yes, Jo is 34", "yes, 18 or older"

_NO = re.compile(r"\b(?:no+|nope|nah|naw|not|never|none|nothing|dont|doesnt|didnt|isnt|wont|cant|cannot|shouldnt|"
                 r"wouldnt|aint|do not|cancel|stop|abort|undo|negative|non|nein|nee|nej|nei|nao|nie)\b|\w+n't\b")

# Words, or runs of other characters: "yes, she's 19!" -> yes , she's 19 !
_TOKEN = re.compile(r"[^\W_]+(?:['-][^\W_]+)*|[^\w\s]+|\S")
_WORD = re.compile(r"[^\W_]+(?:['-][^\W_]+)*")
_PUNCT = re.compile(r"[,.]|!+")

# Signs in an answer to "Is <name> 18 or older?" that they're under 18: an age that isn't 18 yet, or teen and school
# words when it gives no age. An answer with several numbers ("Jo is 34 and has 2 kids") is unclear, not a minor.
_NOT_YET_18 = re.compile(r"\b(?:almost|nearly|turning|turns|soon|will be|'ll be)\s+(?:18|eighteen)\b"
                         r"|\b(?:18|eighteen)\s+(?:next|soon)\b")
_MINOR_WORDS = re.compile(r"\b(?:teen\w*|tween\w*|preteen\w*|adolescent|minor|underage|under age|under 18|grades?|"
                          r"school|highschool|elementary|kindergarten|preschool|secondary|junior high|middle school)\b")
# A number of up to three digits, with any decimals ("16", "16.", "17.9"), not part of a longer one or a year.
_NUMBER = re.compile(r"(?<!\d)(?<!\d\.)\d{1,3}(?:\.\d+)?(?!\.?\d)")
_SMALL = ("", "", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
          "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen")
_TENS = ("twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")

ASK_HINT = ('Ask the owner the question in ask_owner, word for word, and wait. Only if they say yes, run this again '
            'with --owner-confirmed "<their exact words>" --confirm <the code in confirm>. Never answer it yourself.')


def _minutes() -> int:
    return int(utc_now().timestamp() // 60)


def _sign(hh, action: str, owner_id: str, expires: int, nonce: str) -> str:
    """Ties a code to this household's folder, the action and its target, the owner, the expiry and its own random
    part (so every question asked gets a new code, even twice in a minute)."""
    key = hashlib.sha256(f"fridge-door-confirm|{hh.path.resolve()}|{hh.id}".encode()).digest()
    return hmac.new(key, f"{action}|{owner_id}|{expires}|{nonce}".encode(), hashlib.sha256).hexdigest()[:10]


def code_for(hh, action: str, owner_id: str) -> str:
    expires, nonce = _minutes() + CODE_HOURS * 60, secrets.token_hex(3)
    return f"{expires:x}-{nonce}-{_sign(hh, action, owner_id, expires, nonce)}"


def _code_ok(hh, action: str, owner_id: str, code) -> bool:
    match = re.fullmatch(r"([0-9a-f]{1,12})-([0-9a-f]{6})-([0-9a-f]{10})", code_key(code))
    if not match:
        return False
    expires = int(match.group(1), 16)
    if not _minutes() <= expires <= _minutes() + CODE_HOURS * 60 + CLOCK_SLACK:
        return False
    return hmac.compare_digest(match.group(3), _sign(hh, action, owner_id, expires, match.group(2)))


def code_key(code) -> str:
    return str(code or "").strip().lower()


def code_expires(code) -> int:
    """The minute a code stops working (0 for something that isn't a code)."""
    head = code_key(code).split("-")[0]
    return int(head, 16) if re.fullmatch(r"[0-9a-f]{1,12}", head) else 0


def used_codes_kept(used: dict) -> dict:
    """The used codes still worth remembering: the ones that haven't expired."""
    now = _minutes()
    return {code: at for code, at in used.items() if code_expires(code) >= now}


def _words(text: str):
    """The answer as words, or None when it holds anything but words, commas, full stops and exclamation marks (an
    emoji, a question mark, brackets, a dash, an ellipsis)."""
    words = []
    for token in _TOKEN.findall(fold(text).replace("’", "'").replace("‘", "'")):
        if _WORD.fullmatch(token):
            words.append(token)
        elif not _PUNCT.fullmatch(token):
            return None
    return words


def _phrases(texts, possessive: bool = False) -> list:
    """Phrases as word tuples, longest first; with possessive, each also ending in "'s" ("jo's 34")."""
    found = set()
    for text in texts:
        words = tuple(_words(text) or ())
        if words:
            found.update({words, words[:-1] + (words[-1] + "'s",)} if possessive else {words})
    return sorted(found, key=len, reverse=True)


def _age(word: str):
    """An age said in digits or words ("19", "nineteen", "thirty-four"), else None."""
    if word.isdigit():
        return int(word) if len(word) <= 3 else None
    if word and word in _SMALL:  # from two: "one" is too often not a number ("the one", "one of them")
        return _SMALL.index(word)
    tens, _, unit = word.partition("-")
    if tens in _TENS and (not unit or unit in _SMALL[2:10] + ("one",)):
        return 20 + 10 * _TENS.index(tens) + (1 if unit == "one" else _SMALL.index(unit) if unit else 0)
    return None


def plain_yes(text: str, echo=(), ages: bool = False) -> bool:
    """Whether the whole answer is a plain yes: one of _YES first (perhaps after "please"), or a yes in another
    language on its own, then only more of _THEN and the echo phrases (and, with ages, adult ages: 18 to 120)."""
    words = tuple(_words(text) or ())
    if len(words) == 1 and words[0] in _ON_ITS_OWN:
        return True
    then = _phrases(_THEN) + _phrases(echo, possessive=True)

    @functools.lru_cache(maxsize=None)
    def rest_fits(i: int) -> bool:  # words[i:] is made only of allowed phrases (and ages)
        if i == len(words):
            return True
        if ages and 18 <= (_age(words[i]) or 0) <= 120 and rest_fits(i + 1):
            return True
        return any(words[i:i + len(p)] == p and rest_fits(i + len(p)) for p in then)

    openings = [p for p in _phrases(_YES) if words[:len(p)] == p]
    if words[:1] == ("please",):
        openings += [("please",) + p for p in _phrases(_YES) if words[1:1 + len(p)] == p]
    return any(rest_fits(len(p)) for p in openings)


def _ages(text: str) -> list:
    """Every age-like number anywhere in the answer, in digits (decimals too) or words."""
    folded = fold(text)
    return [float(n) for n in _NUMBER.findall(folded)] + [a for a in map(_age, re.findall(r"[a-z]+(?:-[a-z]+)?",
                                                                                           folded)) if a is not None]


def _says_under_18(text: str) -> bool:
    folded = fold(text).replace("’", "'")
    if _NOT_YET_18.search(folded):
        return True
    ages = _ages(text)
    if ages:
        return len(ages) == 1 and ages[0] < 18
    return bool(_MINOR_WORDS.search(folded))


def adult_yes(name: str, text: str) -> bool:
    """For "Is <name> 18 or older?": a plain yes, with at most one age, and that one 18 or over. It counts the ages
    in the same words the yes check reads, so punctuation can't hide one ("yes, he's 16." is 16)."""
    ages = [a for a in map(_age, _words(text) or ()) if a is not None]
    return len(ages) <= 1 and all(18 <= a <= 120 for a in ages) and plain_yes(text, _ADULT_WORDS + (name,), ages=True)


def owner_yes(hh, owner_id: str, action: str, question: str, words, code, *, why: str, echo=(),
              adult: str | None = None) -> str:
    """The owner's exact words, once they're a plain yes to `question` (see the module notes), passed with that
    question's code, which is then used up when the command saves (Household.transaction). Otherwise refuses: with
    the question and a fresh code when there's no answer yet (or no code, an old or used one, or another question's),
    as a no, or as unclear. `action` names the action and its target, e.g. "member.remove|M3"; `echo` lists the
    question's own words an answer may repeat; `adult` is the name in an "Is <name> 18 or older?" question."""
    text = clean_text(words, "owner's answer", max_len=500, required=False)

    def ask(message, hint=ASK_HINT, code_name="needs_owner"):
        return ToolError(message, hint=hint, code=code_name, ask_owner=question, confirm=code_for(hh, action, owner_id))

    if not text:
        raise ask(why)
    if _NO.search(fold(text).replace("’", "'")):
        raise ToolError(
            "The owner's answer reads as a no, so nothing was changed.",
            hint="Tell them it wasn't done. If they change their mind, start again and ask the question afresh.",
            code="owner_declined",
        )
    if adult and _says_under_18(text):
        raise ToolError(
            f"The owner's answer says or suggests {adult} is under 18, so they can't chat with the agent.",
            hint=f"If they're under 18, make them a kid or teen (member access {adult} --role teen); they take part "
            "through a parent. If they're 18 or older, ask again for a plain yes.",
            code="minor_cannot_chat",
        )
    if not _code_ok(hh, action, owner_id, code):
        raise ask("That answer isn't tied to this question: the confirmation code is missing, out of date or for "
                  "something else, so nothing was changed.")
    if code_key(code) in hh.meta().get("used_codes", {}):
        raise ask("That confirmation code was already used, so nothing was changed. Each yes counts once.")
    if not (adult_yes(adult, text) if adult else plain_yes(text, echo)):
        example = f"yes, {adult} is 18 or older" if adult else "yes, go ahead"
        raise ask(
            "The owner's answer isn't a plain yes, so nothing was changed.",
            hint=f'Ask the question again and wait for a plain yes as the whole answer, such as "yes" or "{example}". '
            '"ok", "sure", an emoji, a question, a joke, a yes with a condition or a delay, or one that names '
            "someone else isn't enough.",
            code_name="unclear_answer",
        )
    hh.used_codes.append(code_key(code))
    return text
