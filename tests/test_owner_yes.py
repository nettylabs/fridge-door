"""The owner's yes (an independent review of 1.0.0): only a clear yes to the exact question counts, tied to it by
the question's confirmation code, and the 18-or-older question refuses any answer that says or suggests under 18."""

from helpers import HomeTest, fridge
from fridgedoor.store import Hub

# Every reply the reviewers saw accepted as a yes in 1.0.0.
NOES = ["absolutely not", "definitely not", "please don't", "pls dont", "hell no", "I said no", "Sam says no",
        "I'd rather not", "nooo", "no", "yes... actually no", "ok but not yet", "I don't know", "I have no idea"]
UNCLEAR = ["ok", "OK", "okay", "k", "sure", "fine", "maybe", "hmm", "idk", "later", "ask me later", "?", "...", "lol",
           "what?", "I guess", "sure, after dinner", "👍", "👎", "🙂", "n", "y", "hold off", "forget it", "skip it",
           "nevermind", "sounds good", "yes?", "yes but after dinner", "okay remove Zoe instead"]
UNDER_18 = ["16", "yes, 16", "yes (16)", "sixteen", "maybe 16", "about 15", "nearly 18", "almost 18",
            "turning 18 next year", "grade 10", "in high school", "she's in grade 11", "teenager", "Sky is seventeen",
            "yes, she'll be 18 next month", "16yo"]
NOT_SAID = ["he's my son", "my daughter", "yes, he's my son"]  # a family word with no adult age


class OwnerYesTest(HomeTest):
    def setUp(self):
        super().setUp()
        self.setup_family("Ana, Luis, Rosa, Mateo (teen)", "GB")

    def members(self):
        return [m["name"] for m in Hub(self.home).household().members]

    def test_no_vague_or_negative_reply_changes_anything(self):
        code = self.err("needs_owner", "member", "remove", "Luis")["confirm"]
        for reply in NOES + UNCLEAR:
            with self.subTest(reply=reply):
                out = self.err("owner_declined" if reply in NOES else "unclear_answer", "member", "remove", "Luis",
                               "--owner-confirmed", reply, "--confirm", code)  # fmt: skip
                if reply in UNCLEAR:
                    self.assertIn("Remove Luis", out["ask_owner"])  # ask again, with a code
                    self.assertTrue(out["confirm"])
        self.assertIn("Luis", self.members())
        delete = self.err("needs_owner", "household", "delete")["confirm"]
        for reply in ("k", "👎", "absolutely not", "sure"):
            self.err("owner_declined" if reply == "absolutely not" else "unclear_answer", "household", "delete",
                     "--owner-confirmed", reply, "--confirm", delete)  # fmt: skip
        self.assertTrue(Hub(self.home).household().path.exists())
        setting = self.err("needs_owner", "household", "settings", "--set", "reminders_outside_chat=yes")["confirm"]
        self.err("unclear_answer", "household", "settings", "--set", "reminders_outside_chat=yes",
                 "--owner-confirmed", "sure", "--confirm", setting)  # fmt: skip
        self.err("owner_declined", "household", "settings", "--set", "reminders_outside_chat=yes",
                 "--owner-confirmed", "hell no", "--confirm", setting)  # fmt: skip
        self.assertIsNone(Hub(self.home).household().settings.get("reminders_outside_chat"))

    def test_a_clear_yes_counts(self):
        for reply in ("yes", "Yes!", "YES, remove him", "yes please", "yep", "yeah", "confirm", "go ahead", "do it",
                      "yes 👍", "yes, I want it done"):  # fmt: skip
            with self.subTest(reply=reply):
                self.setup_more()
                self.confirmed("member", "remove", "Temp", words=reply)
                self.assertNotIn("Temp", self.members())

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
        for reply in UNDER_18 + NOT_SAID + ["sure", "🙂", "ok", "idk", "I have no idea"]:
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
        self.ok("who", "chat", "mateo-dm", "--type", "direct", "--member", "Mateo")  # asked once already

    def test_the_reviewers_teen_cant_be_made_to_chat_or_read_the_budget(self):
        self.ok("member", "add", "--name", "Zoe", "--role", "teen")
        self.err("needs_owner", "member", "access", "Zoe", "--role", "adult")  # no silent promotion
        self.err("minor_cannot_chat", "who", "chat", "zoe-dm", "--type", "direct", "--member", "Zoe",
                 "--owner-confirmed", "sure")  # fmt: skip
        self.err("chat_not_linked", "budget", "month", "--chat", "zoe-dm")
