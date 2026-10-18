"""Setup, households, settings, transactions, export and the activity log."""

import json
import unittest
import zipfile

from helpers import HomeTest, fridge
from fridgedoor import members, regions
from fridgedoor.store import Hub
from fridgedoor.util import ToolError


class ParseMembersTest(unittest.TestCase):
    def test_first_person_is_the_owner_and_tags_pick_roles(self):
        self.assertEqual(
            members.parse_member_list("Ana, Luis, Sofia (kid), Mateo (teen)"),
            [("Ana", "owner"), ("Luis", "adult"), ("Sofia", "kid"), ("Mateo", "teen")],
        )

    def test_ages_only_pick_the_role(self):
        people = members.parse_member_list("Dana, Max (7), Ruby (14), Gran (70)")
        self.assertEqual([r for _, r in people], ["owner", "kid", "teen", "adult"])
        self.assertEqual([n for n, _ in people], ["Dana", "Max", "Ruby", "Gran"])

    def test_and_ampersand_and_marked_owner(self):
        people = members.parse_member_list("Tom and Priya (owner)")
        self.assertEqual(people, [("Tom", "adult"), ("Priya", "owner")])
        self.assertEqual(members.parse_member_list("Kai & Jess"), [("Kai", "owner"), ("Jess", "adult")])

    def test_a_kid_listed_first_cannot_be_the_owner(self):
        with self.assertRaises(ToolError):
            members.parse_member_list("Mia (kid), Dana")

    def test_unknown_tags_are_refused(self):
        with self.assertRaises(ToolError):
            members.parse_member_list("Ana (boss)")


class RegionsTest(unittest.TestCase):
    def test_country_names_and_codes(self):
        self.assertEqual(regions.country_code("uk"), "GB")
        self.assertEqual(regions.country_code("Australia"), "AU")
        self.assertEqual(regions.country_code("de"), "DE")
        self.assertEqual(regions.country_code("XK"), "XK")  # a real code we have no defaults for
        with self.assertRaises(ToolError):
            regions.country_code("Narnia")

    def test_defaults(self):
        us, gb, jp = regions.defaults("US"), regions.defaults("GB"), regions.defaults("JP")
        self.assertEqual(
            (us["currency"], us["week_start"], us["units"], us["paper"]), ("USD", "sunday", "us", "letter")
        )
        self.assertEqual((gb["currency"], gb["week_start"], gb["date_format"]), ("GBP", "monday", "DD/MM/YYYY"))
        self.assertEqual(jp["currency"], "JPY")
        self.assertFalse(regions.defaults("XK")["known"])


class SetupTest(HomeTest):
    def test_family_setup_in_one_step(self):
        out = self.setup_family()
        self.assertEqual(out["household"]["name"], "Test home")
        self.assertEqual([m["role"] for m in out["members"]], ["owner", "adult", "kid", "teen"])
        self.assertEqual(out["settings"]["currency"], "CAD")
        self.assertIn("Sofia and Mateo take part through you", out["summary"])
        names = sorted(lst["name"] for lst in out["lists"])
        self.assertEqual(names, ["Groceries", "Household Tasks", "My Tasks (Ana)", "My Tasks (Luis)"])  # per adult
        self.assertEqual(out["settings"]["timezone"], "America/Toronto")
        out = self.ok("household", "add", "--name", "Gran's", "--members", "Ana (owner), Rosa, Theo (kid)", "--country",
                      "PT", "--timezone", "Europe/Lisbon")  # fmt: skip
        self.assertIn("Theo takes part through you", out["summary"])

    def test_solo_setup_needs_only_a_name_and_country(self):
        out = self.ok("setup", "--members", "Jo", "--country", "GB")
        self.assertEqual(out["household"]["name"], "Jo's home")
        self.assertEqual(len(out["members"]), 1)
        self.assertEqual(out["settings"]["timezone"], "Europe/London")
        self.assertEqual(out["notes"], [])

    def test_explicit_choices_override_country_defaults(self):
        out = self.setup_family("Kai, Jess", "AU", "Flat 4", "--timezone", "Australia/Perth", "--week-start", "sunday",
                                "--units", "us")  # fmt: skip
        s = out["settings"]
        self.assertEqual((s["timezone"], s["week_start"], s["units"], s["currency"]),
                         ("Australia/Perth", "sunday", "us", "AUD"))  # fmt: skip

    def test_unknown_country_needs_a_currency(self):
        self.err("needs_currency", "setup", "--members", "Ana", "--country", "XK")
        out = self.ok("setup", "--members", "Ana", "--country", "XK", "--currency", "eur",
                      "--timezone", "Europe/Belgrade")  # fmt: skip
        self.assertEqual(out["settings"]["currency"], "EUR")

    def test_bad_timezone_and_currency_are_refused(self):
        self.err("bad_timezone", "setup", "--members", "Ana", "--country", "GB", "--timezone", "Mars/Olympus")
        self.err("bad_currency", "setup", "--members", "Ana", "--country", "GB", "--currency", "pounds")

    def test_dry_run_saves_nothing(self):
        out = self.ok("setup", "--members", "Ana, Luis", "--country", "GB", "--dry-run")
        self.assertTrue(out["dry_run"])
        self.assertFalse(Hub(self.home).exists())

    def test_setup_twice_is_refused(self):
        self.setup_family()
        self.err("already_set_up", "setup", "--members", "Bo", "--country", "GB")

    def test_commands_before_setup_explain_what_to_do(self):
        out = self.err("not_initialized", "member", "list")
        self.assertIn("setup", out["hint"])

    def test_doctor(self):
        code, out = fridge(self.home, "doctor")
        self.assertFalse(out["initialized"])
        self.setup_family()
        out = self.ok("doctor")
        self.assertTrue(out["initialized"])
        self.assertEqual(out["setup"]["missing"], [])
        self.assertEqual(out["speaker"], "Ana")


class HouseholdTest(HomeTest):
    def setUp(self):
        super().setUp()
        self.setup_family()

    def test_add_list_and_switch_households(self):
        out = self.ok(
            "household", "add", "--name", "Grandma's", "--members", "Ana (owner), Rosa, Leo", "--country", "PT",
            "--timezone", "Atlantic/Azores",
        )
        self.assertIn("now the active household", out["summary"])
        listing = self.ok("household", "list")["households"]
        self.assertEqual([h["name"] for h in listing], ["Test home", "Grandma's"])
        self.assertEqual([h["active"] for h in listing], [False, True])
        self.assertEqual(self.ok("member", "list")["members"][1]["name"], "Rosa")
        self.ok("household", "switch", "test")
        self.assertEqual(self.ok("member", "list")["members"][1]["name"], "Luis")
        # --household reaches the other one without switching
        out = self.ok("member", "list", "--household", "Grandma's")
        self.assertEqual(out["members"][2]["name"], "Leo")

    def test_households_keep_separate_data(self):
        self.ok("household", "add", "--name", "Second", "--members", "Ana (owner), Bo", "--country", "NZ")
        first, second = (Hub(self.home).household(h) for h in ("Test home", "Second"))
        self.assertNotEqual(first.path, second.path)
        self.assertEqual(second.settings["currency"], "NZD")
        self.assertEqual(len(first.members), 4)

    def test_duplicate_household_names_are_refused(self):
        self.err("exists", "household", "add", "--name", "Test home", "--members", "Ana (owner), Bo", "--country",
                 "GB")  # fmt: skip

    def test_rename_and_settings_are_owner_only(self):
        self.err("not_authorized", "household", "rename", "--to", "Ours", "--as", "Luis")
        self.ok("household", "rename", "--to", "The Garcias")
        self.assertEqual(Hub(self.home).household().name, "The Garcias")
        self.err("not_authorized", "household", "settings", "--set", "week_start=monday", "--as", "Luis")
        out = self.ok("household", "settings", "--set", "week_start=monday", "--set", "quiet_hours=22:00-06:30")
        self.assertEqual(out["settings"]["week_start"], "monday")
        self.assertEqual(out["settings"]["quiet_hours"], {"start": "22:00", "end": "06:30"})
        self.assertEqual(self.ok("household", "settings", "--as", "Luis")["settings"]["week_start"], "monday")

    def test_bad_settings_are_refused(self):
        for item, code in (("week_start=someday", "bad_setting"), ("timezone=Nowhere/Land", "bad_timezone"),
                           ("retention_days=2", "bad_setting"), ("colour=blue", "bad_setting")):  # fmt: skip
            self.err(code, "household", "settings", "--set", item)

    def test_reminders_outside_the_chat_need_the_owners_words(self):
        out = self.err("needs_owner", "household", "settings", "--set", "reminders_outside_chat=yes")
        self.assertIn("outside this chat", out["ask_owner"])
        out = self.confirmed("household", "settings", "--set", "reminders_outside_chat=yes", words="yes, email")
        self.assertEqual(out["settings"]["reminders_outside_chat"]["owner_said"], "yes, email")

    def test_delete_needs_the_owners_words(self):
        out = self.err("needs_owner", "household", "delete")
        self.assertIn("can't be undone", out["ask_owner"])
        self.err("not_authorized", "household", "delete", "--owner-confirmed", "yes", "--as", "Luis")
        self.confirmed("household", "delete", words="yes, delete it")
        self.assertFalse(Hub(self.home).exists())

    def test_export_zips_the_household(self):
        out = self.ok("export")
        with zipfile.ZipFile(out["file"]) as zf:
            names = zf.namelist()
        self.assertIn("H1/household.json", names)
        self.assertIn("H1/todos.json", names)
        self.assertFalse(any(n.endswith(".lock") for n in names))

    def test_activity_log_keeps_ids_not_names_and_prunes_itself(self):
        self.ok("member", "add", "--name", "Grandma Rosa")
        hh = Hub(self.home).household()
        log = (hh.path / "activity.jsonl").read_text(encoding="utf-8")
        self.assertNotIn("Grandma Rosa", log)
        self.assertIn('"member": "M5"', log)
        # Entries older than the retention period go the next time anything is written.
        old = json.dumps({"ts": "2026-01-01T00:00:00+00:00", "action": "old"}) + "\n"
        (hh.path / "activity.jsonl").write_text(old + log, encoding="utf-8")
        self.ok("member", "edit", "Ana", "--color", "teal")
        self.assertNotIn('"old"', (hh.path / "activity.jsonl").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
