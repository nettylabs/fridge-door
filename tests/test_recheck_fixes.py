"""The independent re-check of 1.0.1: each item it reopened or found, with the reviewers' own repro where there is one.
The owner's yes and its codes are in test_owner_yes.py."""

import json

from helpers import HomeTest
from fridgedoor.store import Hub

KIM = ("--chat", "dm-kim")


class HouseholdIdentityTest(HomeTest):
    """6 and 7: household list showed every household and called the speaker "you"; a household made with household
    add had no which-chat check and the owner's chat couldn't reach it; `who speaker` turned the check off."""

    def setUp(self):
        super().setUp()
        self.ok("setup", "--name", "Kim home", "--members", "Kim, Lee, Sky (16), Bo (kid)", "--country", "CA",
                "--timezone", "America/Toronto", *KIM)  # fmt: skip
        self.ok("household", "add", "--name", "Cabin", "--members", "Kim, Pat, Lee", "--country", "CA", "--timezone",
                "America/Toronto", *KIM)  # fmt: skip
        self.confirmed("who", "chat", "dm-lee", "--type", "direct", "--member", "Lee", "--household", "H1", *KIM)

    def whoami(self, *args):
        out = self.ok("who", "am-i", *args)
        return out["household"]["name"], out["member"]["name"]

    def test_household_list_shows_only_the_askers_households(self):
        out = self.ok("household", "list", "--chat", "dm-lee")  # a Lee is in Cabin too, but not this chat
        self.assertEqual([(h["name"], h["you"]) for h in out["households"]], [("Kim home", "Lee")])
        out = self.ok("household", "list", *KIM)
        self.assertEqual([(h["name"], h["you"], h["active"]) for h in out["households"]],
                         [("Kim home", "Kim", False), ("Cabin", "Kim", True)])  # fmt: skip

    def test_the_owners_chat_follows_them_into_a_household_they_add(self):
        self.assertEqual(self.whoami(*KIM), ("Cabin", "Kim"))  # household add moved this chat there
        self.assertEqual(self.whoami(*KIM, "--household", "Kim home"), ("Kim home", "Kim"))
        for args in (("--household", "H2"), ("--household", "H2", "--as", "Pat"), ("--as", "Kim")):
            self.err("which_chat", "who", "am-i", *args)  # the second household is covered too
        self.ok("household", "switch", "Kim home", *KIM)
        self.assertEqual(self.whoami(*KIM), ("Kim home", "Kim"))
        self.err("chat_not_linked", "household", "switch", "Cabin", "--chat", "dm-lee")  # Lee isn't in Cabin
        self.assertEqual(self.whoami("--chat", "dm-lee"), ("Kim home", "Lee"))

    def test_a_household_with_no_chats_of_its_own_is_covered_too(self):
        home = ("--home", str(self.home / "two"))  # made before any chat had an id
        self.ok("setup", "--name", "Home", "--members", "Ana, Luis", "--country", "GB", *home)
        self.ok("household", "add", "--name", "Gran's", "--members", "Ana, Gran", "--country", "GB", *home)
        self.ok("who", "chat", "ana-dm", "--type", "direct", "--household", "Home", *home)
        self.err("which_chat", "who", "am-i", "--household", "Gran's", *home)
        self.err("which_chat", "who", "am-i", "--household", "Gran's", "--as", "Gran", *home)

    def test_another_adults_chat_turns_the_check_on_too(self):
        home = ("--home", str(self.home / "luis"))  # the speaker (Ana) has no chat of her own registered
        self.ok("setup", "--name", "Home", "--members", "Ana, Luis", "--country", "GB", *home)
        self.confirmed("who", "chat", "luis-dm", "--type", "direct", "--member", "Luis", *home)
        self.err("which_chat", "household", "settings", "--set", "week_start=sunday", "--as", "Ana", *home)
        self.err("which_chat", "who", "am-i", *home)

    def test_the_speaker_cant_turn_the_check_off(self):
        self.ok("member", "add", "--name", "Max", "--role", "adult", "--household", "H1", *KIM)
        self.err("uses_chats", "who", "speaker", "Max", "--household", "H1", *KIM)
        self.err("which_chat", "household", "settings", "--set", "reminders_outside_chat=no", "--household", "H1",
                 "--as", "Kim")  # fmt: skip
        self.err("which_chat", "todo", "show", "--household", "H1", "--as", "Lee")

    def test_deleting_or_forgetting_a_chats_household_sends_it_back_to_the_other(self):
        code = self.err("needs_owner", "household", "delete", *KIM)["confirm"]
        self.ok("household", "delete", "--owner-confirmed", "yes", "--confirm", code, *KIM)
        self.assertEqual(self.whoami(*KIM), ("Kim home", "Kim"))
        self.ok("household", "add", "--name", "Boat", "--members", "Kim", "--country", "CA", "--timezone",
                "America/Halifax", *KIM)  # fmt: skip
        self.ok("who", "forget-chat", "dm-kim", *KIM)  # forgotten in Boat: still Kim's chat at home
        self.assertEqual(self.whoami(*KIM), ("Kim home", "Kim"))

    def test_a_chat_in_two_households_cant_be_given_to_a_group_or_another_household(self):
        self.err("chat_in_other_household", "who", "chat", "dm-lee", "--type", "direct", "--member", "Pat",
                 "--household", "Cabin", *KIM)  # fmt: skip
        self.err("chat_in_other_household", "who", "chat", "dm-kim", "--type", "group", "--minors", "no", *KIM)
        self.err("chat_in_other_household", "who", "chat", "dm-kim", "--type", "direct", "--member", "Pat", *KIM)
        self.ok("who", "chat", "dm-kim", "--type", "direct", *KIM)  # registering it again as Kim's is fine

    def test_without_chat_ids_the_list_is_still_only_your_own_households(self):
        home = self.home / "terminal"  # a platform with no chat ids
        self.ok("setup", "--name", "Ana home", "--members", "Ana, Luis", "--country", "GB", "--home", str(home))
        self.ok("household", "add", "--name", "Gran's", "--members", "Ana, Gran", "--country", "GB", "--home",
                str(home))  # fmt: skip
        listing = self.ok("household", "list", "--home", str(home))["households"]
        self.assertEqual([h["name"] for h in listing], ["Ana home", "Gran's"])
        listing = self.ok("household", "list", "--household", "Ana home", "--as", "Luis", "--home", str(home))
        self.assertEqual([(h["name"], h["you"]) for h in listing["households"]], [("Ana home", "Luis")])


class RoutinesTest(HomeTest):
    """S-A: once the owner's chat was registered, the SKILL's routines (no --chat) stopped with which_chat."""

    def setUp(self):
        super().setUp()
        self.setup_family("Pat, Sam", "GB", "Flat", "--chat", "pat-dm")

    def test_the_routines_run_with_the_chat_they_belong_to(self):
        self.err("which_chat", "remind", "due")
        self.err("which_chat", "today")
        self.ok("member", "edit", "Pat", "--reminders", "on", "--chat", "pat-dm")
        self.ok("cal", "add", "Dentist", "--date", "today", "--time", "10:00", "--remind", "1h", "--chat", "pat-dm")
        out = self.ok("remind", "due", "--chat", "pat-dm", env={"FRIDGE_NOW": "2026-10-19T09:05:00"})
        self.assertEqual([(r["to"], r["chats"]) for r in out["send"]], [("Pat", ["pat-dm"])])
        self.assertIn("Dentist", self.ok("today", "--chat", "pat-dm")["text"])

    def test_the_skill_says_so(self):
        from helpers import ROOT

        skill = (ROOT / "skills" / "fridge-door" / "SKILL.md").read_text(encoding="utf-8")
        reference = (ROOT / "skills" / "fridge-door" / "references" / "today-reminders-printables.md").read_text(
            encoding="utf-8")
        for text in (skill, reference):
            self.assertIn("--chat <their chat id> today", text)
            self.assertIn("--chat <the owner's chat id> remind due", text)


class TimeZoneTest(HomeTest):
    """9: a country without defaults quietly ran on UTC once the currency was given."""

    def setup(self, *args):
        return self.err("needs_timezone", "setup", "--members", "Jo", *args)

    def test_a_country_with_several_zones_and_no_defaults_asks(self):
        out = self.setup("--country", "RU", "--currency", "RUB")
        self.assertIn("Europe/Moscow", [z["timezone"] for z in out["zones"]])
        self.assertIn("Russia has several time zones", out["error"])
        for country, currency in (("KZ", "KZT"), ("EC", "USD"), ("PF", "XPF"), ("MN", "MNT")):
            self.setup("--country", country, "--currency", currency)
        out = self.err("needs_currency", "setup", "--members", "Jo", "--country", "Russia")  # both in one question
        self.assertIn("the currency and the time zone", out["error"])
        self.assertTrue(out["zones"])
        self.ok("setup", "--members", "Jo", "--country", "RU", "--currency", "RUB", "--timezone", "Asia/Omsk")

    def test_a_country_with_one_zone_gets_it(self):
        out = self.ok("setup", "--members", "Jo", "--country", "Kuwait", "--currency", "KWD", "--dry-run")
        self.assertEqual(out["household"]["settings"]["timezone"], "Asia/Kuwait")
        out = self.ok("setup", "--members", "Jo", "--country", "CI", "--currency", "XOF", "--dry-run")
        self.assertEqual(out["household"]["settings"]["timezone"], "Africa/Abidjan")

    def test_a_country_the_database_doesnt_list_asks_for_the_zone(self):
        out = self.setup("--country", "XK", "--currency", "EUR")
        self.assertIn("Region/City", out["hint"])

    def test_doctor_flags_a_household_left_on_plain_utc(self):
        self.ok("setup", "--members", "Jo", "--country", "RU", "--currency", "RUB", "--timezone", "UTC")
        self.assertIn("plain UTC", self.ok("doctor")["summary"])
        self.ok("household", "settings", "--set", "timezone=Europe/Moscow")
        self.assertEqual(self.ok("doctor")["setup"]["missing"], [])


class MemberAgeTest(HomeTest):
    """N-2: member add --name "Max (17)" made an adult called "Max (17)"."""

    def setUp(self):
        super().setUp()
        self.setup_family("Dana, Lou", "GB")

    def test_an_age_in_brackets_picks_the_role_as_in_setup(self):
        out = self.ok("member", "add", "--name", "Max (17)")
        self.assertEqual((out["member"]["name"], out["member"]["role"]), ("Max", "teen"))
        self.assertEqual(self.ok("member", "add", "--name", "Ivy (9)")["member"]["role"], "kid")
        self.assertEqual(self.ok("member", "add", "--name", "Gran (70)")["member"]["role"], "adult")
        self.err("bad_role", "member", "add", "--name", "Kit (15)", "--role", "adult")
        self.err("bad_name", "member", "add", "--name", "Kit 15")
        self.err("bad_name", "member", "edit", "Lou", "--name", "Lou (40)")
        self.assertEqual(self.ok("setup", "--members", "Ana, Max (17)", "--country", "GB", "--dry-run",
                                 "--home", str(self.home / "other"))["household"]["members"][1]["role"], "teen")

    def test_kids_and_teens_never_get_the_budget(self):
        self.ok("member", "add", "--name", "Theo (8)")
        self.ok("member", "add", "--name", "Max (15)")
        self.err("minor_details", "member", "access", "Theo", "--set", "budget=view")
        self.err("minor_details", "member", "access", "Max", "--set", "budget=edit")
        self.ok("member", "access", "Theo", "--set", "calendar=view")


class ChildDetailsTest(HomeTest):
    """N-D / N-7: the child-details check missed teacher, class, IEP, dentist, an address, ID numbers and "the
    kids"."""

    def setUp(self):
        super().setUp()
        self.setup_family("Ana, Theo (kid), Lily (kid)", "GB")

    def test_more_kinds_of_child_details_need_a_sensitive_or_private_note(self):
        for title, body in (("School", "Theo's teacher is Mrs Lee"), ("Room", "Lily's class is room 4"),
                            ("IEP", "Theo IEP meeting"), ("Teeth", "Theo - ped dentist"),
                            ("Soccer", "Theo's soccer practice address 123 Main St"),
                            ("Food", "the kids have peanut allergies"), ("Bed", "Theo wets the bed"),
                            ("Shots", "Lily's vaccination record"), ("ID", "Theo's passport is in the drawer")):
            with self.subTest(body=body):
                self.err("child_details", "note", "add", title, "--body", body)
        self.ok("note", "add", "Food", "--body", "the kids have peanut allergies", "--sensitive")
        self.ok("note", "add", "Chores", "--body", "Theo feeds the cat, Lily waters the plants")

    def test_family_words_only_count_where_there_are_kids(self):
        self.ok("setup", "--members", "Jo, Sam", "--country", "GB", "--home", str(self.home / "flat"))
        self.ok("note", "add", "Visit", "--body", "my son's dentist is near the station", "--home",
                str(self.home / "flat"))  # fmt: skip


class KidGroupListsTest(HomeTest):
    """N-9: in a kid group, `todo lists` counted the tasks it hides."""

    def test_the_count_matches_what_the_chat_sees(self):
        self.setup_family("Ana, Theo (kid)", "GB")
        self.ok("todo", "add", "Call the accountant")
        self.ok("todo", "add", "Feed the cat", "--assign", "Theo")
        self.ok("who", "chat", "fam", "--type", "group", "--minors", "yes")
        self.ok("who", "link", "fam", "--participant", "@ana", "--member", "Ana")
        lists = self.ok("todo", "lists", "--chat", "fam", "--from", "@ana")["lists"]
        self.assertEqual(next(lst["open"] for lst in lists if lst["name"] == "Household Tasks"), 1)


class ClockTest(HomeTest):
    """N-4: a test clock with no offset counted as UTC for codes but local time elsewhere."""

    def test_a_code_lasts_a_day_of_the_households_own_time(self):
        self.setup_family("Ana, Luis", "CA", "Home", "--timezone", "America/Vancouver")
        code = self.err("needs_owner", "member", "remove", "Luis")["confirm"]  # 8am in Vancouver is 3pm UTC
        nearly = {"FRIDGE_NOW": "2026-10-20T14:30:00+00:00"}  # 23.5 hours on
        self.ok("member", "remove", "Luis", "--owner-confirmed", "yes", "--confirm", code, "--dry-run", env=nearly)
        late = {"FRIDGE_NOW": "2026-10-20T08:01:00"}  # 24 hours and a minute on, Vancouver time
        self.err("needs_owner", "member", "remove", "Luis", "--owner-confirmed", "yes", "--confirm", code, env=late)
        earlier = {"FRIDGE_NOW": "2026-10-19T07:40:00"}  # the clock set back 20 minutes
        self.ok("member", "remove", "Luis", "--owner-confirmed", "yes", "--confirm", code, "--dry-run", env=earlier)


class DataFileTest(HomeTest):
    def test_used_codes_are_kept_only_until_they_expire(self):
        self.setup_family("Ana, Luis, Rosa", "GB")
        self.confirmed("member", "remove", "Luis")
        meta = json.loads((Hub(self.home).household().path / "household.json").read_text(encoding="utf-8"))
        self.assertEqual(len(meta["used_codes"]), 1)
        later = {"FRIDGE_NOW": "2026-10-21T08:00:00"}
        self.confirmed("member", "remove", "Rosa", env=later)
        meta = json.loads((Hub(self.home).household().path / "household.json").read_text(encoding="utf-8"))
        self.assertEqual(len(meta["used_codes"]), 1)  # Luis's is gone: it would have expired anyway
