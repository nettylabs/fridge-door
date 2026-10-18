"""The Today summary: the ported selectors, sections per member, notices, and what a group chat may show."""

import datetime as dt
import unittest

from helpers import HomeTest
from fridgedoor import today

DAY = dt.date(2026, 10, 19)


def task(tid, assignee="M1", due="2026-10-19", **extra):
    return dict({"id": tid, "assignee": assignee, "due": due}, **extra)


class SelectorTest(unittest.TestCase):
    """Ported from the original Today selector tests."""

    def test_my_day_keeps_my_open_tasks_due_today_or_earlier(self):
        tasks = [task("T1"), task("T2", due="2026-10-18"), task("T3", due="2026-10-20")]
        self.assertEqual([t["id"] for t in today.my_day(tasks, "M1", DAY)], ["T2", "T1"])

    def test_orders_overdue_first_then_due_then_id(self):
        tasks = [task("T9"), task("T2"), task("T5", due="2026-10-01")]
        self.assertEqual([t["id"] for t in today.my_day(tasks, "M1", DAY)], ["T5", "T2", "T9"])

    def test_excludes_no_due_date_others_done_and_subtasks(self):
        tasks = [task("T1", due=None), task("T2", assignee="M2"), task("T3", completed_at="2026-10-19T07:00:00+00:00"),
                 task("T4", parent="T1"), task("T5")]  # fmt: skip
        self.assertEqual([t["id"] for t in today.my_day(tasks, "M1", DAY)], ["T5"])

    def test_unknown_member_gets_nothing_and_input_is_untouched(self):
        tasks = [task("T2"), task("T1")]
        self.assertEqual(today.my_day(tasks, "M9", DAY), [])
        self.assertEqual([t["id"] for t in tasks], ["T2", "T1"])

    def test_list_cards_drop_empty_lists_and_sort_busiest_first(self):
        lists = [{"id": "L1", "name": "b"}, {"id": "L2", "name": "a"}, {"id": "L3", "name": "c"},
                 {"id": "L4", "name": "a"}]  # fmt: skip
        cards = today.list_cards(lists, {"L1": 2, "L2": 2, "L3": 5})
        self.assertEqual([lst["id"] for lst, _ in cards], ["L3", "L2", "L1"])
        self.assertEqual(today.list_cards(lists, {}), [])

    def test_greeting_boundaries(self):
        self.assertEqual([today.greeting_for(h) for h in (4, 5, 11, 12, 16, 17, 23)],
                         ["Good evening", "Good morning", "Good morning", "Good afternoon", "Good afternoon",
                          "Good evening", "Good evening"])  # fmt: skip

    def test_dates_follow_the_household_format(self):
        self.assertEqual(today.friendly_date(DAY, {"date_format": "MM/DD/YYYY"}), "Monday, October 19")
        self.assertEqual(today.friendly_date(DAY, {"date_format": "DD/MM/YYYY"}), "Monday 19 October")


class TodayCommandTest(HomeTest):
    def setUp(self):
        super().setUp()
        self.setup_family("Ana, Luis, Theo (kid)", "GB")
        self.ok("todo", "add", "Fix the gate", "--assign", "Luis", "--due", "yesterday")
        self.ok("todo", "add", "Call the bank", "--mine", "--due", "today")
        self.ok("todo", "add", "Water the plants", "--due", "today")
        self.ok("todo", "add", "Feed the cat", "--assign", "Theo", "--due", "today")
        self.ok("shop", "new", "--name", "Pharmacy", "--kind", "shopping")
        self.ok("shop", "add", "milk", "eggs")
        self.ok("shop", "add", "plasters", "--list", "Pharmacy")

    def test_my_today(self):
        out = self.ok("today")
        self.assertTrue(out["summary"].startswith("Good morning, Ana — Monday 19 October"))
        self.assertEqual([t["title"] for t in out["sections"]["tasks"]["items"]], ["Call the bank"])
        self.assertEqual(out["sections"]["tasks"]["unassigned"], ["Water the plants"])
        self.assertEqual([c["name"] for c in out["sections"]["lists"]["items"]], ["Groceries", "Pharmacy"])

    def test_notices_arrive_once(self):
        out = self.ok("today", "--as", "Luis")
        self.assertEqual(out["sections"]["notices"]["lines"], ["New task from Ana: Fix the gate, due Sun 18 Oct"])
        self.assertTrue(out["sections"]["tasks"]["items"][0]["due"]["overdue"])
        self.assertNotIn("notices", self.ok("today", "--as", "Luis")["sections"])

    def test_members_choose_their_sections(self):
        self.ok("member", "edit", "Ana", "--today-sections", "lists")
        self.assertEqual(list(self.ok("today")["sections"]), ["lists"])

    def test_a_kids_day_seen_by_a_parent(self):
        self.ok("cal", "add", "Swimming", "--date", "today", "--time", "16:00", "--for", "Theo")
        self.ok("meal", "plan", "today", "--text", "Fish fingers")
        out = self.ok("today", "--for", "Theo")
        self.assertEqual(out["summary"], "Theo's day — Monday 19 October")
        self.assertEqual([t["title"] for t in out["sections"]["tasks"]["items"]], ["Feed the cat"])
        self.assertEqual([c["name"] for c in out["sections"]["lists"]["items"]], ["Groceries"])  # kids: grocery only
        # Theo never reads this: a parent does, so Theo's events and dinner are there too.
        self.assertEqual([o["title"] for o in out["sections"]["events"]["items"]], ["Swimming"])
        self.assertIn("Fish fingers", out["sections"]["dinner"]["lines"][0])
        # In a group chat with kids present, the calendar and meals stay out as usual.
        self.ok("who", "chat", "fam", "--type", "group", "--minors", "yes")
        self.ok("who", "link", "fam", "--participant", "@ana", "--member", "Ana")
        group = self.ok("today", "--for", "Theo", "--chat", "fam", "--from", "@ana")
        self.assertFalse({"events", "dinner"} & set(group["sections"]))

    def test_group_chat_with_kids_shows_only_kid_safe_things(self):
        self.ok("who", "chat", "fam", "--type", "group", "--minors", "yes")
        self.ok("who", "link", "fam", "--participant", "@ana", "--member", "Ana")
        out = self.ok("today", "--chat", "fam", "--from", "@ana")
        self.assertEqual(out["sections"]["tasks"]["items"], [])  # her private task stays out of the group
        self.assertEqual([c["name"] for c in out["sections"]["lists"]["items"]], ["Groceries"])

    def test_notices_stay_out_of_group_chats(self):
        self.ok("who", "chat", "fam", "--type", "group", "--minors", "no")
        self.ok("who", "link", "fam", "--participant", "@luis", "--member", "Luis", "--owner-confirmed", "yes")
        out = self.ok("today", "--chat", "fam", "--from", "@luis")
        self.assertEqual(out["sections"]["notices"]["items"], [])
        self.assertIn("direct chat", out["sections"]["notices"]["lines"][0])
        self.assertNotIn("Fix the gate", out["text"].split("New for you")[-1])
        out = self.ok("notices", "list", "--chat", "fam", "--from", "@luis")
        self.assertEqual(out["count"], 1)
        self.assertNotIn("notices", out)
        self.assertIn("direct chat", self.ok("shop", "show", "--chat", "fam", "--from", "@luis")["notices_hint"])
        out = self.ok("today", "--as", "Luis")  # still new: read now, in a direct chat
        self.assertEqual(out["sections"]["notices"]["lines"], ["New task from Ana: Fix the gate, due Sun 18 Oct"])

    def test_notices_hide_when_access_is_taken_away(self):
        self.ok("member", "access", "Luis", "--set", "todos=none")
        out = self.ok("notices", "list", "--as", "Luis")
        self.assertEqual(out["notices"], [])
        self.assertNotIn("notices", self.ok("today", "--as", "Luis")["sections"])

    def test_another_day(self):
        out = self.ok("today", "--date", "tomorrow")
        self.assertEqual(out["date"], "2026-10-20")


if __name__ == "__main__":
    unittest.main()
