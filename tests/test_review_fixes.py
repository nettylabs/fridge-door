"""Should-fix items from an independent review of 1.0.0, numbered as in the review.
The owner's yes and the bin have their own files (test_owner_yes.py, test_bin.py)."""

from pathlib import Path

from helpers import HomeTest, fridge
from fridgedoor.store import Hub


def open_tasks(home, title):
    return [t for t in Hub(home).household().data("todos")["tasks"]
            if t["title"] == title and not t.get("completed_at")]  # fmt: skip


class ChoreUndoTest(HomeTest):
    """5. Undoing a repeating chore left its next one behind: a duplicate that then blocked ticking it off by name."""

    def setUp(self):
        super().setUp()
        self.setup_family("Jo, Sam, Mia (kid), Kit (kid)", "GB")

    def test_undo_takes_back_the_next_chore_it_made(self):
        self.ok("todo", "add", "Take out the bins", "--repeat", "weekly on mon", "--rotate", "Mia, Kit")
        self.ok("todo", "done", "Take out the bins", "--by", "Mia")
        out = self.ok("todo", "undo", "Take out the bins")
        self.assertIn("off the list again", out["summary"])
        self.assertEqual(len(open_tasks(self.home, "Take out the bins")), 1)
        self.ok("todo", "done", "Take out the bins", "--by", "Mia")  # not ambiguous any more

    def test_its_unread_turn_notice_goes_too(self):
        self.ok("todo", "add", "Dishes", "--repeat", "daily", "--rotate", "Jo, Sam")
        self.ok("todo", "done", "Dishes")

        def for_sam():
            return [n for n in Hub(self.home).household().data("notices")["notices"] if n["to"] == "M2"]

        self.assertEqual(len(for_sam()), 1)  # "Your turn: Dishes", not read yet
        self.ok("todo", "undo", "Dishes")
        self.assertEqual(for_sam(), [])

    def test_a_next_chore_someone_changed_stays(self):
        self.ok("todo", "add", "Water plants", "--repeat", "daily")
        self.ok("todo", "done", "Water plants")
        self.ok("todo", "edit", open_tasks(self.home, "Water plants")[0]["id"], "--notes", "the ferns too")
        out = self.ok("todo", "undo", "Water plants")
        self.assertIn("changed since", out["summary"])
        self.assertEqual(len(open_tasks(self.home, "Water plants")), 2)


class HouseholdCommandsTest(HomeTest):
    """6. Household add, list and switch skipped the identity check: a kid or another adult could add a household or
    switch the active one, which changes who direct-chat commands run as."""

    def setUp(self):
        super().setUp()
        self.setup_family()  # Ana (owner), Luis, Sofia (kid), Mateo (teen)

    def test_only_the_owner_adds_or_switches(self):
        add = ("household", "add", "--name", "Rosa's", "--members", "Luis (owner), Rosa", "--country", "CA")
        self.err("not_authorized", *add, "--as", "Luis")
        self.err("minor_cannot_chat", *add, "--as", "Sofia")
        self.err("not_authorized", "household", "switch", "Test home", "--as", "Luis")
        self.err("minor_cannot_chat", "household", "list", "--as", "Mateo")

    def test_the_owner_adds_one_as_its_owner_so_their_chat_stays_theirs(self):
        self.err("not_the_owner", "household", "add", "--name", "Rosa's", "--members", "Rosa, Bill", "--country", "CA")
        self.ok("household", "add", "--name", "Gran's", "--members", "Ana (owner), Gran", "--country", "PT",
                "--timezone", "Europe/Lisbon")  # fmt: skip
        self.assertEqual(self.ok("who", "am-i")["member"]["name"], "Ana")
        self.ok("household", "switch", "Test home")
        self.assertEqual(self.ok("who", "am-i")["household"]["name"], "Test home")

    def test_no_switch_to_a_household_where_direct_chats_are_someone_else(self):
        self.ok("household", "add", "--name", "Gran's", "--members", "Ana (owner), Gran", "--country", "PT",
                "--timezone", "Europe/Lisbon")  # fmt: skip
        self.confirmed("who", "speaker", "Gran", "--household", "Gran's")
        self.ok("household", "switch", "Test home", "--household", "Test home")
        self.err("not_the_owner", "household", "switch", "Gran's")


class OwnersChatTest(HomeTest):
    """7. With no --chat, every command ran as the owner, so an adult in an unregistered one-to-one chat could act as
    them. Once the owner's own chat is registered (setup --chat), every message must say which chat it came from."""

    def test_after_setup_with_a_chat_every_message_names_its_chat(self):
        out = self.ok("setup", "--members", "Ana, Luis", "--country", "GB", "--chat", "ana-dm")
        self.assertEqual(out["chat"], "ana-dm")
        self.err("which_chat", "who", "am-i")
        self.err("which_chat", "budget", "month", "--as", "Ana")  # not even with --as
        self.err("chat_not_linked", "budget", "month", "--chat", "luis-phone")  # a chat nobody registered
        self.assertEqual(self.ok("who", "am-i", "--chat", "ana-dm")["member"]["name"], "Ana")
        self.confirmed("member", "remove", "Luis", "--chat", "ana-dm")  # the owner, from her own chat

    def test_a_terminal_without_chat_ids_works_as_before(self):
        self.setup_family("Ana, Luis", "GB")
        self.assertEqual(self.ok("who", "am-i")["member"]["name"], "Ana")

    def test_registering_the_owners_own_chat_later_turns_it_on(self):
        self.setup_family("Ana, Luis", "GB")
        self.ok("who", "chat", "ana-dm", "--type", "direct")
        self.err("which_chat", "who", "am-i")
        self.ok("who", "am-i", "--chat", "ana-dm")

    def test_reminders_name_the_owners_registered_chat(self):
        self.ok("setup", "--members", "Ana, Luis", "--country", "GB", "--chat", "ana-dm")
        self.ok("member", "edit", "Ana", "--reminders", "on", "--chat", "ana-dm")
        self.ok("cal", "add", "Movie", "--date", "today", "--time", "20:00", "--remind", "1h", "--chat", "ana-dm")
        sent = self.ok("remind", "due", "--chat", "ana-dm", env={"FRIDGE_NOW": "2026-10-19T19:05:00"})["send"]
        self.assertEqual([(r["to"], r["chats"]) for r in sent], [("Ana", ["ana-dm"])])


class TimeZoneTest(HomeTest):
    """8 and 9. A computer with no time zone list ran every household on UTC without a word, and setup never asked
    which province or city, so a BC household got Toronto time."""

    def test_setup_asks_which_place_in_a_country_with_several_time_zones(self):
        out = self.err("needs_timezone", "setup", "--members", "Ana, Luis", "--country", "CA")
        self.assertIn("Which province, state or city", out["error"])
        self.assertIn({"timezone": "America/Vancouver", "where": "British Columbia"}, out["zones"])
        self.ok("setup", "--members", "Ana, Luis", "--country", "CA", "--timezone", "America/Vancouver")
        self.ok("setup", "--name", "Flat", "--members", "Jo", "--country", "GB", "--home", str(self.home / "gb"))

    def test_every_listed_zone_is_a_real_one(self):
        from fridgedoor import regions
        from fridgedoor.util import tz_known

        for country, zones in regions.ZONES.items():
            self.assertTrue(regions.defaults(country)["several_time_zones"], country)
            for tz, _ in zones:
                self.assertTrue(tz_known(tz), tz)

    def test_the_demo_can_use_the_persons_own_time_zone(self):
        out = self.ok("demo", "--region", "CA", "--timezone", "America/Vancouver")
        self.assertIn("Sample household ready", out["summary"])
        self.assertEqual(Hub(self.home).household().settings["timezone"], "America/Vancouver")


class NoTimeZoneListTest(HomeTest):
    """8. Python on Windows has no time zone list without the tzdata package: refuse with the fix, never guess UTC."""

    def setUp(self):
        import tempfile
        import zoneinfo

        super().setUp()
        self.setup_family("Jo, Sam", "GB")  # while this computer still has its list
        self.empty = tempfile.mkdtemp(prefix="no-tz-")
        zoneinfo.reset_tzpath(to=[self.empty])
        zoneinfo.ZoneInfo.clear_cache()

    def tearDown(self):
        import shutil
        import zoneinfo

        zoneinfo.reset_tzpath()
        zoneinfo.ZoneInfo.clear_cache()
        shutil.rmtree(self.empty, ignore_errors=True)
        super().tearDown()

    def test_commands_refuse_with_the_fix_instead_of_running_on_utc(self):
        out = self.err("no_tz_data", "today")
        self.assertIn("pip install tzdata", out["hint"])
        self.assertTrue(any("pip install tzdata" in m for m in self.ok("doctor")["setup"]["missing"]))
        other = str(self.home / "fresh")
        self.err("no_tz_data", "setup", "--members", "Ana", "--country", "GB", "--home", other)


class DemoTest(HomeTest):
    """10 and 16. demo without --home filled the real data folder, and its Today always looked empty."""

    def test_the_demo_needs_a_folder_of_its_own(self):
        real = self.home / "real"
        _, out = fridge(None, "demo", "--region", "CA", env={"FRIDGE_HOME": str(real)})
        self.assertEqual(out.get("code"), "needs_home", out)
        self.assertFalse(real.exists())

    def test_each_demos_today_has_something_on_it_and_meals_keep_their_weekday(self):
        for region in ("CA", "GB", "AU", "US"):
            for now in ("2026-10-18T09:00:00", "2026-10-21T19:00:00"):  # a Sunday morning, a Wednesday evening
                with self.subTest(region=region, now=now):
                    home, env = self.home / f"{region}-{now[:10]}", {"FRIDGE_NOW": now}
                    self.assertEqual(fridge(home, "demo", "--region", region, env=env)[0], 0)
                    sections = fridge(home, "today", env=env)[1]["sections"]
                    self.assertNotIn("Nothing on the calendar.", sections["events"]["lines"])
                    self.assertTrue(sections["tasks"]["lines"])
        plan = Hub(self.home / "CA-2026-10-18").household().data("mealplan")["plan"]
        self.assertIn("breakfast", plan["2026-10-24"])  # Saturday pancakes on the Saturday, made on a Sunday


class GroupWithKidsTest(HomeTest):
    def setUp(self):
        super().setUp()
        self.setup_family("Ana, Luis, Theo (kid)", "GB")
        self.ok("who", "chat", "fam", "--type", "group", "--minors", "yes")
        self.ok("who", "link", "fam", "--participant", "@ana", "--member", "Ana")
        self.group = ("--chat", "fam", "--from", "@ana")


class PrintoutFolderTest(GroupWithKidsTest):
    """11. Printouts and calendar files for different people and chats shared one folder and file name, so one could
    overwrite another, and the owner's calendar file with private events sat with the household's printouts."""

    def test_each_chat_gets_its_own_files(self):
        mine = self.ok("print", "week")["files"][0]
        kids = self.ok("print", "week", *self.group)["files"][0]
        self.assertIn("/output/private/M1/", mine)
        self.assertIn("/output/chats/fam-", kids)
        self.assertTrue(Path(mine).exists() and Path(kids).exists())

    def test_calendar_files_are_each_persons_own(self):
        self.ok("cal", "add", "Therapy", "--date", "friday", "--private")
        self.assertIn("/output/private/M1/", self.ok("ics", "export")["file"])
        self.assertIn("/output/private/M2/", self.ok("ics", "export", "--as", "Luis")["file"])

    def test_forgetting_a_chat_removes_its_printouts(self):
        kids = self.ok("print", "week", *self.group)["files"][0]
        self.ok("who", "forget-chat", "fam")
        self.assertFalse(Path(kids).exists())


class KidGroupChoresTest(GroupWithKidsTest):
    """14. A group chat with kids in it showed every household to-do; it shows only chores now."""

    def test_only_chores_show_there(self):
        self.ok("todo", "add", "Fix the gate", "--assign", "Luis", "--due", "today")
        self.ok("todo", "add", "Book the dentist")
        self.ok("todo", "add", "Dishes", "--repeat", "daily", "--rotate", "Theo, Luis")
        self.ok("todo", "add", "Bins", "--repeat", "weekly")
        self.ok("todo", "add", "Feed the cat", "--assign", "Theo", "--due", "today")
        shown = self.ok("todo", "show", *self.group)["text"]
        for title in ("Dishes", "Bins", "Feed the cat"):
            self.assertIn(title, shown)
        for title in ("Fix the gate", "Book the dentist"):
            self.assertNotIn(title, shown)
        self.err("not_found", "todo", "done", "Fix the gate", *self.group)
        self.assertNotIn("Fix the gate", self.ok("todo", "chores", *self.group)["text"])
        self.assertIn("Fix the gate", self.ok("todo", "show")["text"])  # a parent's own chat still has everything


class RemindersOptInTest(HomeTest):
    """13. Reminders went to other members' chats without their yes. Now each adult turns their own on."""

    def setUp(self):
        super().setUp()
        self.setup_family("Ana, Luis", "GB", "Test home", "--chat", "ana-dm")
        self.confirmed("who", "chat", "luis-dm", "--type", "direct", "--member", "Luis", "--chat", "ana-dm")
        self.ok("cal", "add", "Movie", "--date", "today", "--time", "20:00", "--remind", "1h", "--for", "Ana, Luis",
                "--chat", "ana-dm")  # fmt: skip

    def due(self):
        return self.ok("remind", "due", "--chat", "ana-dm", env={"FRIDGE_NOW": "2026-10-19T19:05:00"})

    def test_nobody_gets_reminders_they_didnt_ask_for(self):
        out = self.due()
        self.assertEqual(out["send"], [])
        self.assertIn("Nobody has turned reminders on", out["summary"])
        self.err("not_their_own", "member", "edit", "Luis", "--reminders", "on", "--chat", "ana-dm")  # not even the
        self.ok("member", "edit", "Luis", "--reminders", "on", "--chat", "luis-dm")  # owner, for him
        self.assertEqual([r["to"] for r in self.due()["send"]], ["Luis"])  # Ana hasn't said yes

    def test_the_owner_can_turn_someones_off_and_a_reminder_request_says_when_theyre_off(self):
        self.ok("member", "edit", "Luis", "--reminders", "on", "--chat", "luis-dm")
        self.ok("member", "edit", "Luis", "--reminders", "off", "--chat", "ana-dm")
        self.assertFalse(self.ok("member", "show", "Luis", "--chat", "ana-dm")["member"]["reminders"])
        out = self.ok("cal", "add", "Dentist", "--date", "friday", "--time", "15:00", "--remind", "1h",
                      "--chat", "ana-dm")  # fmt: skip
        self.assertIn("Reminders are off for you", out["hint"])


class BrowserPrinterTest(HomeTest):
    """Nice-to-have from the review: the browser printer took `landscape` but never used it."""

    def test_a_landscape_sheet_asks_the_browser_for_landscape(self):
        from fridgedoor import render

        seen = {}

        def fake_run(cmd, **_):
            page = Path(cmd[-1].replace("file://", ""))
            seen["html"] = page.read_text(encoding="utf-8")
            Path(next(c for c in cmd if c.startswith("--print-to-pdf=")).split("=", 1)[1]).write_bytes(b"%PDF-1.4")
            return type("Done", (), {"stderr": ""})()

        real, render.subprocess.run = render.subprocess.run, fake_run
        try:
            render.browser_pdf("<html><head></head><body>Zoë</body></html>", self.home / "sheet.pdf", "chrome", True)
        finally:
            render.subprocess.run = real
        self.assertIn("@page { size: landscape; }", seen["html"])


class NiceToHaveTest(HomeTest):
    """The smaller points from the reviewers' reports."""

    def setUp(self):
        super().setUp()
        self.setup_family("Ana, Luis, Theo (kid)", "CA")

    def test_list_delete_and_restore_take_the_name_either_way(self):
        self.ok("shop", "new", "--name", "Hardware", "--kind", "shopping")
        self.ok("shop", "delete", "Hardware")
        self.ok("shop", "restore", "--list", "Hardware")
        self.ok("shop", "delete", "--list", "Hardware")
        self.ok("shop", "restore", "Hardware")

    def test_a_birthday_is_added_once(self):
        self.ok("cal", "birthday", "--member", "Theo", "--date", "14 March")
        self.err("exists", "cal", "birthday", "--member", "Theo", "--date", "14 March")
        self.ok("cal", "birthday", "--name", "Gran", "--date", "1950-06-02")
        self.err("exists", "cal", "birthday", "--name", "gran", "--date", "1950-06-02")

    def test_thousands_with_a_decimal_point_are_read_but_bare_commas_still_ask(self):
        self.ok("budget", "spend", "1,234.56", "--category", "Housing")
        self.assertEqual(Hub(self.home).household().data("budget")["expenses"][-1]["amount"], "1234.56")
        self.err("bad_number", "budget", "spend", "1,500", "--category", "Housing")

    def test_any_countrys_name_works(self):
        out = self.err("needs_currency", "setup", "--members", "Ana", "--country", "Kuwait", "--home",
                       str(self.home / "kw"))  # fmt: skip
        self.assertIn("Kuwait", out["error"])

    def test_household_delete_previews_without_the_owners_yes(self):
        out = self.ok("household", "delete", "--dry-run")
        self.assertIn("Would delete Test home", out["summary"])
        self.assertTrue(Hub(self.home).household().path.exists())

    def test_a_time_the_clocks_skip_gets_a_warning(self):
        out = self.ok("cal", "add", "Early start", "--date", "2027-03-14", "--time", "02:30")
        self.assertIn("doesn't exist", out["warning"])
        self.assertNotIn("warning", self.ok("cal", "add", "Late start", "--date", "2027-03-14", "--time", "09:30"))

    def test_a_strange_household_folder_in_the_index_is_refused(self):
        import json

        hub = self.home / "hub.json"
        data = json.loads(hub.read_text())
        data["households"][0]["folder"] = "../../elsewhere"
        hub.write_text(json.dumps(data))
        self.err("bad_data", "household", "show")
