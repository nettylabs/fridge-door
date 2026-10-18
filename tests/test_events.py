"""The calendar: events, repeats, one-date changes, visibility, birthdays, busy evenings and views."""

import unittest

from helpers import HomeTest
from fridgedoor import events
from fridgedoor.store import Hub
from fridgedoor.util import ToolError


class HelpersTest(unittest.TestCase):
    def test_type_guessing(self):
        cases = {"Dentist": "health", "Soccer practice": "sports", "Parent-teacher night": "school",
                 "Flight to Lisbon": "travel", "Gran's birthday": "birthday", "Haircut": "appointment",
                 "Rent due date": "bill", "Book club": "other"}  # fmt: skip
        for title, kind in cases.items():
            self.assertEqual(events.guess_type(title), kind, title)

    def test_reminders(self):
        self.assertEqual(events.parse_reminders("30m, 1h, 1d"), [30, 60, 1440])
        self.assertEqual(events.parse_reminders("2 days before and at start"), [0, 2880])
        with self.assertRaises(ToolError):
            events.parse_reminders("soonish")


class CalendarTest(HomeTest):
    def setUp(self):
        super().setUp()
        self.setup_family("Ana, Luis, Theo (kid), Lily (kid)", "US")

    def agenda(self, *args):
        return self.ok("cal", "agenda", *args)["occurrences"]

    def test_timed_all_day_and_multi_day_events(self):
        out = self.ok("cal", "add", "Dentist", "--date", "friday", "--time", "3:30pm", "--minutes", "45",
                      "--for", "Theo")  # fmt: skip
        event = out["event"]
        self.assertEqual((event["time"], event["end_time"], event["type"]), ("15:30", "16:15", "health"))
        self.assertIn("3:30pm", out["summary"])  # 12-hour clock in the US
        self.ok("cal", "add", "Camping trip", "--date", "2026-10-23", "--until-date", "2026-10-25")
        occ = [o for o in self.agenda("--days", "10") if o["title"] == "Camping trip"]
        self.assertEqual((occ[0]["all_day"], occ[0]["end_date"]), (True, "2026-10-25"))
        self.assertTrue(self.ok("cal", "day", "2026-10-24")["occurrences"])  # still shows on its middle day

    def test_repeats_start_on_the_first_matching_day(self):
        out = self.ok("cal", "add", "Soccer", "--date", "monday", "--time", "17:30", "--repeat", "weekly on tue")
        self.assertEqual(out["event"]["date"], "2026-10-20")
        self.assertIn("moved to the first date", out["summary"])
        dates = [o["date"] for o in self.agenda("--days", "21") if o["title"] == "Soccer"]
        self.assertEqual(dates, ["2026-10-20", "2026-10-27", "2026-11-03"])

    def test_one_date_changes_skips_and_ending_a_series(self):
        self.ok("cal", "add", "Swim", "--date", "tuesday", "--time", "17:00", "--repeat", "weekly")
        self.ok("cal", "edit", "Swim", "--on", "2026-10-27", "--time", "18:00")
        self.ok("cal", "skip", "Swim", "--on", "2026-11-03")
        occs = {o["date"]: o["time"] for o in self.agenda("--days", "28") if o["title"] == "Swim"}
        self.assertEqual(occs, {"2026-10-20": "17:00", "2026-10-27": "18:00", "2026-11-10": "17:00"})
        self.ok("cal", "skip", "Swim", "--on", "2026-11-03", "--undo")
        self.ok("cal", "delete", "Swim", "--from-date", "2026-11-04")
        dates = [o["date"] for o in self.agenda("--days", "60") if o["title"] == "Swim"]
        self.assertEqual(dates, ["2026-10-20", "2026-10-27", "2026-11-03"])
        self.err("not_found", "cal", "skip", "Swim", "--on", "2026-10-21")

    def test_private_and_selected_member_events(self):
        self.ok("cal", "add", "Therapy", "--date", "thursday", "--time", "12:00", "--private")
        self.ok("cal", "add", "Gift planning", "--date", "saturday", "--for", "Ana, Luis", "--only")
        mine = {o["title"] for o in self.agenda("--days", "7")}
        self.assertEqual(mine, {"Therapy", "Gift planning"})
        luis = {o["title"] for o in self.agenda("--days", "7", "--as", "Luis")}
        self.assertEqual(luis, {"Gift planning"})
        self.err("not_found", "cal", "edit", "Therapy", "--time", "13:00", "--as", "Luis")
        self.ok("who", "chat", "parents", "--type", "group", "--minors", "no")
        self.ok("who", "link", "parents", "--participant", "@ana", "--member", "Ana")
        self.confirmed("who", "link", "parents", "--participant", "@luis", "--member", "Luis", words="yes")
        group = {o["title"] for o in self.agenda("--days", "7", "--chat", "parents", "--from", "@ana")}
        self.assertEqual(group, {"Gift planning"})  # private stays out; both parents are on the gift planning

    def test_only_the_creator_changes_who_sees_an_event(self):
        self.ok("cal", "add", "Gift planning", "--date", "saturday", "--for", "Ana, Luis", "--only")
        self.err("not_authorized", "cal", "edit", "Gift planning", "--visibility", "household", "--as", "Luis")
        self.err("not_authorized", "cal", "edit", "Gift planning", "--for", "Ana, Luis, Theo", "--as", "Luis")
        self.ok("cal", "edit", "Gift planning", "--time", "10:00", "--as", "Luis")  # other changes are fine
        self.ok("cal", "edit", "Gift planning", "--visibility", "household")  # Ana made it

    def test_calendar_never_shows_in_a_chat_with_kids(self):
        self.ok("cal", "add", "Dentist", "--date", "friday")
        self.ok("who", "chat", "fam", "--type", "group", "--minors", "yes")
        self.ok("who", "link", "fam", "--participant", "@ana", "--member", "Ana")
        self.err("hidden_in_group", "cal", "agenda", "--chat", "fam", "--from", "@ana")  # kids: calendar none

    def test_member_filter(self):
        self.ok("cal", "add", "Soccer", "--date", "tuesday", "--for", "Lily")
        self.ok("cal", "add", "Dentist", "--date", "tuesday", "--for", "Theo")
        self.ok("cal", "add", "Therapy", "--date", "tuesday", "--private")
        self.ok("cal", "add", "Family dinner", "--date", "tuesday")
        titles = {o["title"] for o in self.agenda("--days", "3", "--for", "Lily")}
        self.assertEqual(titles, {"Soccer", "Family dinner"})

    def test_birthdays_repeat_and_kids_keep_only_day_and_month(self):
        out = self.ok("cal", "birthday", "--name", "Grandma Rosa", "--date", "1948-10-25")
        self.assertIn("turns 78", out["summary"])
        out = self.ok("cal", "birthday", "--member", "Theo", "--date", "2018-03-14")  # the year isn't kept
        self.assertIn("Only the day and month are kept", out["summary"])
        self.assertNotIn("turns", out["summary"])
        self.assertIsNone(Hub(self.home).household().data("calendar")["events"][-1]["birthday"]["year"])
        self.ok("cal", "birthday", "--name", "Leap Lou", "--date", "2000-02-29")
        upcoming = self.ok("cal", "birthdays", "--days", "10")["birthdays"]
        self.assertEqual([(b["title"], b.get("turns")) for b in upcoming], [("Grandma Rosa's birthday", 78)])
        lou = self.ok("cal", "show", "Leap Lou")["event"]
        self.assertEqual(lou["next"][0], "2027-02-28")  # leap-day birthdays land on Feb 28 in other years

    def test_busy_evenings(self):
        self.ok("cal", "add", "Hockey", "--date", "wednesday", "--time", "17:30", "--end", "19:00")
        self.ok("cal", "add", "Breakfast meeting", "--date", "thursday", "--time", "08:00")
        self.ok("cal", "add", "Late film", "--date", "friday", "--time", "21:00")
        self.assertEqual(self.ok("cal", "busy")["busy"], {"2026-10-21": ["Hockey"]})

    def test_editing_series_fields_and_deleting(self):
        self.ok("cal", "add", "Swim", "--date", "tuesday", "--time", "17:00", "--repeat", "weekly")
        self.ok("cal", "edit", "Swim", "--location", "Community pool", "--remind", "1h")
        shown = self.ok("cal", "show", "Swim")["event"]
        got = (shown["location"], shown["reminders"], shown["repeats"])
        self.assertEqual(got, ("Community pool", [60], "weekly on Tue"))
        self.ok("cal", "delete", "Swim")
        self.assertEqual(self.agenda("--days", "14"), [])

    def test_views(self):
        self.ok("cal", "add", "Swim", "--date", "tuesday", "--time", "17:00", "--repeat", "weekly")
        week = self.ok("cal", "week")
        self.assertEqual((week["from"], week["to"]), ("2026-10-18", "2026-10-24"))  # US weeks start on Sunday
        self.assertIn("Tue Oct 20", week["text"])  # US date order
        month = self.ok("cal", "month", "2026-11")
        self.assertEqual(len(month["occurrences"]), 4)

    def test_kids_cannot_add_events(self):
        self.err("minor_cannot_chat", "cal", "add", "Party", "--as", "Theo")


if __name__ == "__main__":
    unittest.main()
