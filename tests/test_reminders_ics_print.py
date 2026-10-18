"""Reminders and quiet hours, .ics round trips and time zones, and printables."""

import re
import shutil
import tempfile
import unittest
from pathlib import Path

from helpers import HomeTest, fridge
from fridgedoor import ics, printables
from fridgedoor.store import Hub


class RemindersTest(HomeTest):
    NOW = "2026-10-19T08:00:00"

    def setUp(self):
        super().setUp()
        self.setup_family("Ana, Luis, Theo (kid)", "CA")
        for name in ("Ana", "Luis"):  # reminders are each adult's own yes
            self.ok("member", "edit", name, "--reminders", "on", "--as", name)

    def due(self, now, *args):
        return self.ok("remind", "due", *args, env={"FRIDGE_NOW": now})

    def test_event_reminders_go_to_adults_once(self):
        self.confirmed("who", "chat", "luis-dm", "--type", "direct", "--member", "Luis", words="yes")
        self.ok("cal", "add", "Dentist", "--date", "2026-10-20", "--time", "15:00", "--for", "Luis", "--remind", "1h")
        self.assertEqual(self.due("2026-10-20T13:30:00")["send"], [])  # not yet
        out = self.due("2026-10-20T14:05:00")
        self.assertEqual([(r["to"], r["chats"]) for r in out["send"]], [("Luis", ["luis-dm"])])
        self.assertIn("Dentist (Luis) in 55 minutes at 3pm", out["send"][0]["text"])  # worded when it's sent
        self.assertEqual(self.due("2026-10-20T14:10:00")["send"], [])  # never twice

    def test_kids_events_remind_the_adult_who_made_them(self):
        self.ok("cal", "add", "Piano", "--date", "2026-10-20", "--time", "16:00", "--for", "Theo", "--remind", "30m")
        out = self.due("2026-10-20T15:40:00")
        self.assertEqual([r["to"] for r in out["send"]], ["Ana"])

    def test_quiet_hours_hold_reminders_until_they_end(self):
        self.confirmed("who", "chat", "luis-dm", "--type", "direct", "--member", "Luis", words="yes")
        self.ok("member", "edit", "Luis", "--quiet-hours", "21:00-07:00", "--as", "Luis")
        self.ok("cal", "add", "Early flight", "--date", "2026-10-21", "--time", "09:00", "--for", "Luis",
                "--remind", "10h")  # fires 23:00 the night before  # fmt: skip
        out = self.due("2026-10-20T23:05:00")
        self.assertEqual(out["send"], [])
        self.assertEqual(out["held"][0]["until"][:16], "2026-10-21T07:00")
        out = self.due("2026-10-21T07:01:00")
        self.assertEqual([r["to"] for r in out["send"]], ["Luis"])

    def test_old_reminders_are_dropped_not_sent_late(self):
        self.ok("cal", "add", "Swim", "--date", "2026-10-19", "--time", "07:00", "--remind", "30m")
        out = self.due("2026-10-19T09:00:00")
        self.assertEqual(out["send"], [])
        self.assertEqual(len(out["dropped"]), 1)

    def test_private_events_and_bills_are_direct_chat_only(self):
        self.ok("who", "chat", "fam", "--type", "group", "--minors", "no")
        self.ok("who", "link", "fam", "--participant", "@ana", "--member", "Ana")
        self.confirmed("who", "link", "fam", "--participant", "@luis", "--member", "Luis", words="yes")
        self.ok("cal", "add", "Therapy", "--date", "2026-10-20", "--time", "12:00", "--private", "--remind", "1h")
        self.ok("budget", "category-defaults")
        self.ok("budget", "bill-add", "Rent", "--amount", "1800", "--due", "2026-10-25", "--remind", "3d")
        out = self.due("2026-10-22T09:30:00")
        bills = [r for r in out["send"] if r["kind"] == "bill"]
        self.assertEqual([(r["to"], r["chats"]) for r in bills], [("Ana", ["direct"])])  # never the group
        self.assertEqual(out["nowhere"], [{"to": "Luis", "member": "M2", "kind": "bill"}])  # no chat of his own yet
        out = self.due("2026-10-20T11:05:00")
        self.assertEqual([(r["to"], r["chats"]) for r in out["send"]], [("Ana", ["direct"])])

    def test_birthdays_remind_the_day_before(self):
        self.ok("cal", "birthday", "--name", "Gran", "--date", "1950-10-21")
        out = self.due("2026-10-20T08:30:00")
        self.assertIn("Gran's birthday", out["send"][0]["text"])

    def test_only_the_owner_runs_everyones_reminders_and_never_in_groups(self):
        self.err("not_authorized", "remind", "due", "--as", "Luis")
        self.ok("remind", "due", "--mine", "--as", "Luis")
        self.ok("who", "chat", "fam", "--type", "group", "--minors", "no")
        self.ok("who", "link", "fam", "--participant", "@ana", "--member", "Ana")
        self.err("direct_chat_only", "remind", "due", "--chat", "fam", "--from", "@ana")

    def test_outside_the_chat_needs_the_owners_ok(self):
        self.assertFalse(self.ok("remind", "due")["outside_chat_ok"])
        self.confirmed("household", "settings", "--set", "reminders_outside_chat=yes", words="yes, by email")
        self.assertTrue(self.ok("remind", "due")["outside_chat_ok"])


class IcsTest(HomeTest):
    def setUp(self):
        super().setUp()
        self.setup_family("Ana, Luis, Lily (kid)", "CA", "Home", "--timezone", "America/Toronto")
        self.other = Path(tempfile.mkdtemp(prefix="fridge-ics-"))

    def tearDown(self):
        shutil.rmtree(self.other, ignore_errors=True)
        super().tearDown()

    def test_round_trip_keeps_times_repeats_skips_and_moves(self):
        self.ok("cal", "add", "Soccer", "--date", "tuesday", "--time", "17:30", "--end", "19:00", "--for", "Lily",
                "--repeat", "weekly", "--remind", "1h", "--location", "North field")  # fmt: skip
        self.ok("cal", "skip", "Soccer", "--on", "2026-10-27")
        self.ok("cal", "edit", "Soccer", "--on", "2026-11-03", "--time", "18:00")
        self.ok("cal", "add", "Camping", "--date", "2026-11-06", "--until-date", "2026-11-08")
        self.ok("cal", "add", "Therapy", "--date", "thursday", "--time", "12:00", "--private")
        exported = self.ok("ics", "export")
        text = Path(exported["file"]).read_bytes().decode("utf-8")  # keep the CRLF line ends as written
        self.assertEqual(exported["events"], 3)
        self.assertIn("BEGIN:VTIMEZONE", text)
        self.assertIn("DTSTART;TZID=America/Toronto:20261020T173000", text)
        self.assertIn("EXDATE;TZID=America/Toronto:20261027T173000", text)
        self.assertIn("RECURRENCE-ID;TZID=America/Toronto:20261103T173000", text)
        self.assertIn("DTEND;VALUE=DATE:20261109", text)  # all-day ends are exclusive
        self.assertTrue(all(len(line.encode()) <= 75 for line in text.split("\r\n")))
        # Into a second household in the same time zone: the same calendar comes out.
        fridge(self.other, "setup", "--members", "Bo", "--country", "CA", "--timezone", "America/Toronto")
        code, out = fridge(self.other, "ics", "import", exported["file"])
        self.assertEqual((code, len(out["added"])), (0, 3))
        code, mine = fridge(self.other, "cal", "agenda", "--days", "21")
        got = {(o["date"], o["time"], o["title"]) for o in mine["occurrences"]}
        self.assertIn(("2026-10-20", "17:30", "Soccer"), got)
        self.assertNotIn(("2026-10-27", "17:30", "Soccer"), got)
        self.assertIn(("2026-11-03", "18:00", "Soccer"), got)
        self.assertIn(("2026-11-06", None, "Camping"), got)
        self.assertTrue(any(o["title"] == "Therapy" for o in mine["occurrences"]))  # private comes in as private

    def test_reimporting_updates_instead_of_duplicating(self):
        self.ok("cal", "add", "Book club", "--date", "friday", "--time", "19:00")
        path = Path(self.ok("ics", "export")["file"])
        fridge(self.other, "setup", "--members", "Bo", "--country", "CA", "--timezone", "America/Toronto")
        fridge(self.other, "ics", "import", str(path))
        code, out = fridge(self.other, "ics", "import", str(path))
        self.assertEqual((out["added"], out["updated"], out["unchanged"]), ([], [], ["Book club"]))
        # A note added here survives a re-import of a file that changed the time only.
        fridge(self.other, "cal", "edit", "Book club", "--notes", "Bring the wine")
        path.write_bytes(path.read_bytes().replace(b"T190000", b"T193000"))
        code, out = fridge(self.other, "ics", "import", str(path))
        self.assertEqual(out["updated"], ["Book club"])
        self.assertIn("time changed", out["text"])
        event = Hub(self.other).household().data("calendar")["events"][0]
        self.assertEqual((event["time"], event["notes"]), ("19:30", "Bring the wine"))

    def write_ics(self, name, *items):
        body = "".join(f"BEGIN:VEVENT\r\nUID:{uid}\r\nSUMMARY:{title}\r\nDTSTART;VALUE=DATE:20261024\r\n"
                       + ("CLASS:PRIVATE\r\n" if private else "") + "END:VEVENT\r\n" for uid, title, private in items)
        path = self.home / f"{name}.ics"
        path.write_text("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n" + body + "END:VCALENDAR\r\n", encoding="utf-8")
        return str(path)

    def event(self, title):
        return next(e for e in Hub(self.home).household().data("calendar")["events"] if e["title"] == title)

    def test_imports_only_change_events_the_person_could_change_by_hand(self):
        self.ok("ics", "import", self.write_ics("ana", ("u1", "Therapy", True), ("u2", "School term", False),
                                                ("u3", "Swim club", False), ("u4", "Gift shopping", False)))  # fmt: skip
        self.ok("cal", "edit", "Gift shopping", "--visibility", "members", "--for", "Ana, Luis")
        # Ana's private event: a file that reuses its UID makes Luis his own event and leaves hers alone.
        out = self.ok("ics", "import", self.write_ics("l1", ("u1", "Changed", False)), "--as", "Luis")
        self.assertEqual((out["added"], out["updated"]), (["Changed"], []))
        self.assertEqual((self.event("Therapy")["visibility"], self.event("Therapy")["owner"]), ("private", "M1"))
        # A private import never writes into Ana's shared event (everyone who sees hers would see it).
        out = self.ok("ics", "import", self.write_ics("l2", ("u2", "My copy", False)), "--private", "--as", "Luis")
        self.assertEqual((out["added"], out["updated"]), (["My copy"], []))
        self.assertEqual(self.event("School term")["visibility"], "household")
        # A shared re-import updates a shared event, but who made it and who sees it stay as they were.
        out = self.ok("ics", "import", self.write_ics("l3", ("u3", "Swim club moved", False),
                                                      ("u4", "Gift shopping!", False)), "--as", "Luis")  # fmt: skip
        self.assertEqual(out["updated"], ["Swim club moved", "Gift shopping!"])
        self.assertEqual((self.event("Swim club moved")["owner"], self.event("Gift shopping!")["visibility"]),
                         ("M1", "members"))  # fmt: skip

    def test_a_file_this_household_exported_is_recognised(self):
        self.ok("cal", "add", "Book club", "--date", "friday", "--time", "19:00")
        self.ok("cal", "add", "Therapy", "--date", "thursday", "--time", "12:00", "--private")
        path = self.ok("ics", "export")["file"]
        out = self.ok("ics", "import", path)
        self.assertEqual((out["added"], sorted(out["already"])), ([], ["Book club", "Therapy"]))
        self.assertIn("2 already in the calendar", out["summary"])
        # Luis can't see Ana's private event, so from her file it comes in as a new event of his own.
        out = self.ok("ics", "import", path, "--as", "Luis")
        self.assertEqual((out["added"], out["already"]), (["Therapy"], ["Book club"]))
        # Two homes never share UIDs, even though both have an event E1.
        fridge(self.other, "setup", "--members", "Bo", "--country", "CA", "--timezone", "America/Toronto")
        fridge(self.other, "cal", "add", "Book club", "--date", "friday", "--time", "19:00")
        code, theirs = fridge(self.other, "ics", "export")

        def uids(file):
            return set(re.findall(r"UID:(\S+)", Path(file).read_text(encoding="utf-8")))

        self.assertEqual(code, 0)
        self.assertFalse(uids(path) & uids(theirs["file"]))

    def test_utc_and_other_zones_convert_to_the_household_time(self):
        cal = ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:a1\r\nSUMMARY:Call with Gran\r\n"
               "DTSTART:20261020T213000Z\r\nDTEND:20261020T220000Z\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nUID:a2\r\n"
               "SUMMARY:London meeting\r\nDTSTART;TZID=Europe/London:20261029T090000\r\nDURATION:PT1H\r\n"
               "END:VEVENT\r\nBEGIN:VEVENT\r\nUID:a3\r\nSUMMARY:Cancelled thing\r\nSTATUS:CANCELLED\r\n"
               "DTSTART:20261021T100000Z\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n")  # fmt: skip
        path = self.home / "in.ics"
        path.write_text(cal, encoding="utf-8")
        out = self.ok("ics", "import", str(path))
        self.assertEqual((len(out["added"]), out["skipped"]), (2, ["Cancelled thing"]))
        agenda = self.ok("cal", "agenda", "--days", "14")["occurrences"]
        occ = {o["title"]: (o["date"], o["time"], o["end_time"]) for o in agenda}
        self.assertEqual(occ["Call with Gran"], ("2026-10-20", "17:30", "18:00"))  # EDT is UTC-4
        self.assertEqual(occ["London meeting"], ("2026-10-29", "05:00", "06:00"))  # BST+1 -> EDT-4: 5 hours

    def test_folded_lines_escapes_and_bad_files(self):
        long_title = "A very long event title " * 5
        cal = ("BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:b1\r\nSUMMARY:" + long_title[:60] + "\r\n " + long_title[60:]
               + "\r\nLOCATION:Hall\\, Room 2\\; back door\r\nDTSTART;VALUE=DATE:20261025\r\nEND:VEVENT\r\n"
               "END:VCALENDAR\r\n")  # fmt: skip
        path = self.home / "fold.ics"
        path.write_text(cal, encoding="utf-8")
        self.ok("ics", "import", str(path))
        event = Hub(self.home).household().data("calendar")["events"][-1]
        self.assertEqual(event["title"], long_title.strip())
        self.assertEqual(event["location"], "Hall, Room 2; back door")
        bad = self.home / "bad.ics"
        bad.write_text("hello", encoding="utf-8")
        self.err("bad_file", "ics", "import", str(bad))

    def test_vtimezone_rules(self):
        lines = ics.vtimezone("Europe/London", 2026)
        self.assertIn("RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU", lines)
        self.assertIn("TZOFFSETTO:+0100", lines)
        self.assertEqual(ics.vtimezone("UTC", 2026), [])
        fixed = ics.vtimezone("Asia/Kolkata", 2026)
        self.assertIn("TZOFFSETTO:+0530", fixed)


def is_pdf(path) -> bool:
    data = Path(path).read_bytes()
    return data.startswith(b"%PDF-1.4") and data.rstrip().endswith(b"%%EOF") and b"startxref" in data


class PrintablesTest(HomeTest):
    def setUp(self):
        super().setUp()
        fridge(self.home, "demo", "--region", "CA", env={"FRIDGE_NOW": self.NOW})

    def test_every_printable_is_a_valid_file(self):
        for args in (("print", "week", "--format", "both"), ("print", "calendar"), ("print", "calendar", "--week",
                     "today"), ("print", "list"), ("print", "recipe", "Weeknight chili", "--servings", "6"),
                     ("print", "budget")):  # fmt: skip
            out = self.ok(*args)
            for path in out["files"]:
                self.assertTrue(Path(path).is_file(), path)
                if path.endswith(".pdf"):
                    self.assertTrue(is_pdf(path), path)
                else:
                    self.assertIn("<!doctype html>", Path(path).read_text(encoding="utf-8"))

    def test_the_budget_report_stays_in_the_persons_own_folder(self):
        path = self.ok("print", "budget")["files"][0]
        self.assertIn("/private/M1/", path)  # not with the fridge sheet and lists everyone may be sent

    def test_long_names_wrap_instead_of_being_cut_off(self):
        sheet = printables.Sheet("letter", True, "Test")
        title = "5:30pm Soccer practice at the north field (Lily)"
        lines = sheet.lines(title, "F1", 7.5, 100, 3)
        self.assertEqual((len(lines) > 1, " ".join(lines)), (True, title))
        self.assertTrue(sheet.lines(title * 3, "F1", 7.5, 100, 2)[-1].endswith("…"))
        cell = printables._chore_lines(sheet, ["Book the winter tyre swap"], 60, 4)
        self.assertEqual([box for box, _ in cell], [True, False])  # one chore on two lines, one tick box
        crowded = printables._chore_lines(sheet, ["Bins", "Dishes", "Laundry", "Lawn", "Recycling"], 60, 4)
        self.assertEqual(crowded[-1], (False, "+2 more"))

    def test_the_fridge_sheet_leaves_out_private_things(self):
        self.ok("cal", "add", "Secret therapy", "--date", "today", "--time", "12:00", "--private")
        self.ok("cal", "add", "Gift planning", "--date", "today", "--for", "Ada, Marc", "--only")
        out = self.ok("print", "week", "--format", "html")
        page = Path(out["files"][0]).read_text(encoding="utf-8")
        self.assertNotIn("Secret therapy", page)
        self.assertNotIn("Gift planning", page)
        self.assertNotIn("Wifi", page)  # sensitive note
        self.assertIn("Sitter instructions", page)  # pinned, shared, not sensitive
        self.assertNotIn("Mortgage", page)  # no budget on the fridge
        self.assertIn("Take out the bins", page)
        mine = Path(self.ok("print", "calendar", "--mine", "--format", "html")["files"][0]).read_text(encoding="utf-8")
        self.assertIn("Secret therapy", mine)

    def test_the_fridge_sheet_only_has_what_the_person_may_see(self):
        self.ok("member", "access", "Marc", "--set", "calendar=none", "--set", "meal_plan=none", "--set", "todos=none",
                "--set", "notes=none")  # fmt: skip
        texts = ("Soccer", "Dinner", "Unload the dishwasher", "Sitter instructions", "Stars")
        owners = Path(self.ok("print", "week", "--format", "html")["files"][0]).read_text(encoding="utf-8")
        self.assertTrue(all(text in owners for text in texts))
        out = self.ok("print", "week", "--format", "html", "--as", "Marc")
        self.assertIn("(0 events, 0 chore rows)", out["summary"])
        page = Path(out["files"][0]).read_text(encoding="utf-8")
        self.assertFalse([text for text in texts if text in page])

    def test_budget_report_is_private(self):
        self.ok("who", "chat", "fam", "--type", "group", "--minors", "yes")
        self.err("hidden_in_group", "print", "budget", "--chat", "family-chat", "--from", "@ada")

    def test_pdf_text_has_no_emoji(self):
        out = self.ok("print", "list")
        data = Path(out["files"][0]).read_bytes()
        self.assertIsNone(re.search(rb"\xf0\x9f", data))


if __name__ == "__main__":
    unittest.main()
