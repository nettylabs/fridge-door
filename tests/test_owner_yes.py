"""The owner's yes (an independent review of 1.0.0, and its re-check of 1.0.1): only a plain yes as the whole
answer counts, tied to its question by a confirmation code that works once, and the 18-or-older question refuses
any answer that says or suggests under 18, or is anything but a plain yes with at most one adult age."""

from helpers import HomeTest, fridge
from fridgedoor.store import Hub

# Every reply the reviewers saw accepted as a yes in 1.0.0.
NOES = ["absolutely not", "definitely not", "please don't", "pls dont", "hell no", "I said no", "Sam says no",
        "I'd rather not", "nooo", "no", "yes... actually no", "ok but not yet", "I don't know", "I have no idea"]
UNCLEAR = ["ok", "OK", "okay", "k", "sure", "fine", "maybe", "hmm", "idk", "later", "ask me later", "?", "...", "lol",
           "what?", "I guess", "sure, after dinner", "👍", "👎", "🙂", "n", "y", "hold off", "forget it", "skip it",
           "nevermind", "sounds good", "yes?", "yes but after dinner", "okay remove Zoe instead"]
# And every one the re-check of 1.0.1 still saw accepted: a yes with a condition, a delay, a joke or mixed signals,
# a yes naming someone else, and a lookalike letter.
STRINGS_ATTACHED = ["yes, next week", "yes once we've exported", "yes once he moves out", "yes when he leaves",
                    "yes as long as he agrees", "yes, provided he agrees", "yes on Friday", "yes, in a minute",
                    "yes, do it in December", "yes, eventually", "yes, let me check with Ada first", "yes lol jk",
                    "yes jk", "yes (kidding)", "yes (joking)", "yes, sarcastically", "yeah right", "yes, I suppose",
                    "yes 👎", "👍 yes", "yes 👍", "yes, remove Zoe", "yes, remove Theo", "yes remove her",
                    "yes, n\u043e", "\u0443es", "y\u0435s", "yes, once the kids move out", "yes...", "ok yes",
                    "yes, I want it done"]
UNDER_18 = ["16", "yes, 16", "yes (16)", "sixteen", "maybe 16", "about 15", "nearly 18", "almost 18",
            "turning 18 next year", "grade 10", "in high school", "she's in grade 11", "teenager", "Sky is seventeen",
            "yes, she'll be 18 next month", "16yo", "yes, she's a tween",
            # The final check: a full stop or a decimal hid the age in 1.0.1's re-check fixes.
            "Yes, he's 16.", "yes she's 15.", "yes 17.", "yes, 12.", "yes, 16.5", "yes, 17.0", "yes, 17.9", "yes.16"]
NOT_SAID = ["he's my son", "my daughter", "yes, he's my son"]  # a family word with no adult age
# The re-check's teen answers that made a teen an adult in 1.0.1: now asked again (or refused as under 18 above).
NOT_PLAIN = ["yes, she's 18 in May", "yes, she's 18 (well, in May)", "yes, born 2010", "yes, born in 2009",
             "born in 2010", "yes, she was born in 2010", "yes, she's a junior", "yes, a sophomore",
             "yes, she's a high schooler", "yes, she's a freshman in college", "yes, my stepkid",
             "yes, 18 in a few weeks", "yes, 18 come spring", "yes, she's 18 as of next week",
             "yes, she's 18 this year",
             "yes, nearly an adult", "yes, 18ish", "yes, eighteen-ish", "yes, close enough", "yes, she's 18 in spirit",
             "yes, she's 216 months", "yes, she's XVII", "yes, she's legally an adult next year",
             "yes, Lee is 34 and has 2 kids", "yes, she's 45, mum of 3", "yes my daughter is 19"]


class OwnerYesTest(HomeTest):
    def setUp(self):
        super().setUp()
        self.setup_family("Ana, Luis, Rosa, Mateo (teen)", "GB")

    def members(self):
        return [m["name"] for m in Hub(self.home).household().members]

    def test_no_vague_or_negative_reply_changes_anything(self):
        code = self.err("needs_owner", "member", "remove", "Luis")["confirm"]
        for reply in NOES + UNCLEAR + STRINGS_ATTACHED + [s + "." for s in STRINGS_ATTACHED if s[-1].isalnum()]:
            with self.subTest(reply=reply):
                out = self.err("owner_declined" if reply in NOES else "unclear_answer", "member", "remove", "Luis",
                               "--owner-confirmed", reply, "--confirm", code)  # fmt: skip
                if reply not in NOES:
                    self.assertIn("Remove Luis", out["ask_owner"])  # ask again, with a code
                    self.assertTrue(out["confirm"])
        self.assertIn("Luis", self.members())
        delete = self.err("needs_owner", "household", "delete")["confirm"]
        for reply in ("k", "👎", "absolutely not", "sure", "yes once we've exported", "yes, next week", "yes lol jk"):
            self.err("owner_declined" if reply == "absolutely not" else "unclear_answer", "household", "delete",
                     "--owner-confirmed", reply, "--confirm", delete)  # fmt: skip
        self.assertTrue(Hub(self.home).household().path.exists())
        setting = self.err("needs_owner", "household", "settings", "--set", "reminders_outside_chat=yes")["confirm"]
        for reply in ("sure", "yes, once the kids move out", "yes, allow it next week"):
            self.err("unclear_answer", "household", "settings", "--set", "reminders_outside_chat=yes",
                     "--owner-confirmed", reply, "--confirm", setting)  # fmt: skip
        self.err("owner_declined", "household", "settings", "--set", "reminders_outside_chat=yes",
                 "--owner-confirmed", "hell no", "--confirm", setting)  # fmt: skip
        self.assertIsNone(Hub(self.home).household().settings.get("reminders_outside_chat"))

    def test_a_plain_yes_counts(self):
        for reply in ("yes", "Yes!", "YES.", "yes please", "Yes, remove Temp", "yes remove them", "yep", "yeah",
                      "yup", "confirm", "go ahead", "do it", "please go ahead", "please do it", "yes, please do it",
                      "yes, go ahead!", "Oui", "Sí"):  # fmt: skip
            with self.subTest(reply=reply):
                self.setup_more()
                self.confirmed("member", "remove", "Temp", words=reply)
                self.assertNotIn("Temp", self.members())
        delete = self.err("needs_owner", "household", "delete")["confirm"]
        self.ok("household", "delete", "--owner-confirmed", "yes, delete it", "--confirm", delete)
        self.assertFalse(Hub(self.home).exists())

    def test_a_yes_names_only_the_person_asked_about(self):
        self.ok("member", "add", "--name", "Luis Jr", "--role", "adult")
        code = self.err("needs_owner", "member", "remove", "Luis Jr")["confirm"]
        for reply in ("yes, remove Luis", "yes, remove Rosa", "yes, remove Luis Jr and Rosa"):
            self.err("unclear_answer", "member", "remove", "Luis Jr", "--owner-confirmed", reply, "--confirm", code)
        self.ok("member", "remove", "Luis Jr", "--owner-confirmed", "yes, remove Luis Jr", "--confirm", code)
        self.assertEqual(self.members(), ["Ana", "Luis", "Rosa", "Mateo"])

    def test_a_code_works_once(self):
        """The re-check turned a setting back on with an old code after the owner turned it off."""
        setting = ("household", "settings", "--set", "reminders_outside_chat=yes")
        code = self.err("needs_owner", *setting)["confirm"]
        self.ok(*setting, "--owner-confirmed", "yes", "--confirm", code)
        self.ok("household", "settings", "--set", "reminders_outside_chat=no")
        out = self.err("needs_owner", *setting, "--owner-confirmed", "yes", "--confirm", code)
        self.assertIn("already used", out["error"])
        self.assertTrue(out["confirm"] and out["confirm"] != code)  # asks afresh, with a new code
        self.assertIsNone(Hub(self.home).household().settings["reminders_outside_chat"])
        # A dry run doesn't use the code up; the real run then does.
        luis = self.err("needs_owner", "member", "remove", "Luis")["confirm"]
        self.ok("member", "remove", "Luis", "--owner-confirmed", "yes", "--confirm", luis, "--dry-run")
        self.ok("member", "remove", "Luis", "--owner-confirmed", "yes", "--confirm", luis)
        self.assertNotIn("Luis", self.members())
        # Used codes are forgotten once they'd have expired anyway.
        later = {"FRIDGE_NOW": "2026-10-21T09:00:00"}
        rosa = self.err("needs_owner", "member", "remove", "Rosa", env=later)["confirm"]
        self.ok("member", "remove", "Rosa", "--owner-confirmed", "yes", "--confirm", rosa, env=later)
        self.assertEqual(list(Hub(self.home).household().meta()["used_codes"]), [rosa])

    def setup_more(self):
        self.ok("member", "add", "--name", "Temp", "--role", "adult")

    def test_a_yes_only_counts_with_its_own_questions_code(self):
        self.err("needs_owner", "member", "remove", "Luis", "--owner-confirmed", "yes")  # nothing asked yet
        luis = self.err("needs_owner", "member", "remove", "Luis")["confirm"]
        rosa = self.err("needs_owner", "member", "remove", "Rosa")["confirm"]
        delete = self.err("needs_owner", "household", "delete")["confirm"]
        for code in (rosa, delete, luis[:-1] + ("0" if luis[-1] != "0" else "1"), "1234-abcdef0123"):
            self.err("needs_owner", "member", "remove", "Luis", "--owner-confirmed", "yes", "--confirm", code)
        late = {"FRIDGE_NOW": "2026-10-20T09:00:00"}  # the code is good for a day
        self.err("needs_owner", "member", "remove", "Luis", "--owner-confirmed", "yes", "--confirm", luis, env=late)
        self.assertEqual(self.members(), ["Ana", "Luis", "Rosa", "Mateo"])
        self.ok("member", "remove", "Luis", "--owner-confirmed", "yes", "--confirm", luis)
        self.assertNotIn("Luis", self.members())

    def test_turning_two_settings_on_needs_two_questions(self):
        self.err("usage", "household", "settings", "--set", "reminders_outside_chat=yes", "--set",
                 "sensitive_notes_in_groups=yes")  # fmt: skip
        self.confirmed("household", "settings", "--set", "sensitive_notes_in_groups=yes")
        self.ok("household", "settings", "--set", "sensitive_notes_in_groups=no")  # turning it off needs no question


class AdultCheckTest(HomeTest):
    def setUp(self):
        super().setUp()
        self.setup_family("Ana, Luis, Mateo (teen)", "GB")
        self.ok("member", "add", "--name", "Lee", "--role", "adult")
        self.ok("who", "chat", "g1", "--type", "group", "--minors", "no")

    def linked(self):
        chat = Hub(self.home).household().meta()["chats"]["g1"]
        return sorted(chat["participants"].values())

    def test_no_answer_that_says_or_suggests_under_18_lets_them_chat(self):
        code = self.err("needs_owner", "who", "link", "g1", "--participant", "@lee", "--member", "Lee")["confirm"]
        for reply in UNDER_18 + NOT_SAID + NOT_PLAIN + ["sure", "🙂", "ok", "idk", "I have no idea", "yes lol jk"]:
            with self.subTest(reply=reply):
                _, out = fridge(self.home, "who", "link", "g1", "--participant", "@lee", "--member", "Lee",
                                "--owner-confirmed", reply, "--confirm", code)  # fmt: skip
                expected = "minor_cannot_chat" if reply in UNDER_18 else (
                    "owner_declined" if reply == "I have no idea" else "unclear_answer")  # fmt: skip
                self.assertEqual(out["code"], expected, out)
        self.assertEqual(self.linked(), [])
        self.ok("who", "link", "g1", "--participant", "@lee", "--member", "Lee", "--owner-confirmed",
                "yes, Lee is 34", "--confirm", code)  # fmt: skip
        self.assertEqual(self.linked(), ["M4"])

    def test_punctuation_never_hides_an_age(self):
        """Every refused answer stays refused with a full stop, "!" or "..." after it, and the yes check reads the
        ages itself rather than trusting the under-18 check to have found them."""
        from fridgedoor import confirm

        code = self.err("needs_owner", "who", "link", "g1", "--participant", "@lee", "--member", "Lee")["confirm"]
        for reply in UNDER_18 + NOT_PLAIN:
            for end in ("", ".", "!", "...", " ."):
                with self.subTest(reply=reply + end):
                    self.assertFalse(confirm.adult_yes("Lee", reply + end))
                    _, out = fridge(self.home, "who", "link", "g1", "--participant", "@lee", "--member", "Lee",
                                    "--owner-confirmed", reply + end, "--confirm", code)  # fmt: skip
                    self.assertIn(out.get("code"), ("minor_cannot_chat", "unclear_answer"), out)
        for reply in ("Yes, she's 19.", "yes, Lee is 34!", "Yes.", "yes, eighteen."):
            self.assertTrue(confirm.adult_yes("Lee", reply), reply)
        self.assertEqual(self.linked(), [])

    def test_a_plain_yes_with_at_most_one_adult_age_counts(self):
        link = ("who", "link", "g1", "--participant", "@lee", "--member", "Lee")
        code = self.err("needs_owner", *link)["confirm"]
        for reply in ("yes", "Yes, she's 19.", "yes, Lee is 34", "yes, Lee's 40", "yes, eighteen", "yep, twenty-one",
                      "yes, they're 18 or older", "yes, he turned 18", "yes, over 18", "yes, an adult"):  # fmt: skip
            with self.subTest(reply=reply):
                self.ok(*link, "--owner-confirmed", reply, "--confirm", code, "--dry-run")
        for reply in ("yes, Luis is 34", "yes, she's 19 or 16", "yes, she's 19, 20", "yes, 150"):  # someone else,
            # two ages, not an age
            self.err("unclear_answer", *link, "--owner-confirmed", reply, "--confirm", code)
        self.assertEqual(self.linked(), [])

    def test_making_a_teen_an_adult_asks_the_same_question(self):
        out = self.err("needs_owner", "member", "access", "Mateo", "--role", "adult")
        self.assertIn("Is Mateo 18 or older?", out["ask_owner"])
        self.err("minor_cannot_chat", "member", "access", "Mateo", "--role", "adult", "--owner-confirmed",
                 "yes (16)", "--confirm", out["confirm"])  # fmt: skip
        self.err("unclear_answer", "member", "access", "Mateo", "--role", "adult", "--owner-confirmed", "sure",
                 "--confirm", out["confirm"])  # fmt: skip
        self.assertEqual(Hub(self.home).household().member("M3")["role"], "teen")
        self.ok("member", "access", "Mateo", "--role", "adult", "--owner-confirmed", "yes, he turned 18",
                "--confirm", out["confirm"])  # fmt: skip
        self.ok("member", "access", "Mateo", "--role", "teen")  # back again: the old yes doesn't make him an adult
        self.err("needs_owner", "member", "access", "Mateo", "--role", "adult", "--owner-confirmed",
                 "yes, he turned 18", "--confirm", out["confirm"])  # fmt: skip
        self.confirmed("member", "access", "Mateo", "--role", "adult", words="yes, he turned 18")
        self.ok("who", "chat", "mateo-dm", "--type", "direct", "--member", "Mateo")  # asked once already

    def test_the_reviewers_teen_cant_be_made_to_chat_or_read_the_budget(self):
        self.ok("member", "add", "--name", "Zoe", "--role", "teen")
        self.err("needs_owner", "member", "access", "Zoe", "--role", "adult")  # no silent promotion
        self.err("minor_cannot_chat", "who", "chat", "zoe-dm", "--type", "direct", "--member", "Zoe",
                 "--owner-confirmed", "sure")  # fmt: skip
        self.err("chat_not_linked", "budget", "month", "--chat", "zoe-dm")
