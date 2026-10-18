"""To-dos and chores: privacy of personal lists, assignment notices, repeats, rotation, stars, and the rest."""

import datetime as dt
import unittest

from helpers import HomeTest
from fridgedoor import todos
from fridgedoor.store import Hub

TODAY = dt.date(2026, 10, 19)  # a Monday, matching HomeTest.NOW


class DueLabelTest(unittest.TestCase):
    """Ported describeDue cases."""

    def label(self, offset):
        return todos.describe_due((TODAY + dt.timedelta(days=offset)).isoformat(), TODAY)

    def test_labels(self):
        self.assertEqual(self.label(0), {"date": "2026-10-19", "label": "Today", "overdue": False})
        self.assertEqual(self.label(1)["label"], "Tomorrow")
        self.assertEqual((self.label(-1)["label"], self.label(-1)["overdue"]), ("Yesterday", True))
        self.assertEqual(self.label(2)["label"], "Wednesday")
        self.assertEqual(self.label(6)["label"], "Sunday")
        self.assertEqual(self.label(7)["label"], "26 Oct")
        self.assertEqual((self.label(-9)["label"], self.label(-9)["overdue"]), ("10 Oct", True))
        self.assertEqual(self.label(80)["label"], "7 Jan 2027")
        self.assertIsNone(todos.describe_due(None, TODAY))

    def test_priorities(self):
        got = [todos.parse_priority(p) for p in ("high", "LOW", "2", "!!", None, "urgent")]
        self.assertEqual(got, [3, 1, 2, 2, 0, 3])


class TreeTest(unittest.TestCase):
    def test_one_level_orphans_promoted_and_done_hidden_after_a_day(self):
        now = dt.datetime(2026, 10, 19, 12, tzinfo=dt.timezone.utc)
        tasks = [
            {"id": "T1", "title": "a"},
            {"id": "T2", "title": "sub", "parent": "T1"},
            {"id": "T3", "title": "orphan", "parent": "T99"},
            {"id": "T4", "title": "done", "completed_at": "2026-10-19T09:00:00+00:00"},
            {"id": "T5", "title": "old", "completed_at": "2026-10-17T09:00:00+00:00"},
        ]
        open_tasks, done, children = todos.build_tree(tasks, now)
        self.assertEqual([t["id"] for t in open_tasks], ["T1", "T3"])
        self.assertEqual([t["id"] for t in done], ["T4"])
        self.assertEqual([t["id"] for t in children["T1"]], ["T2"])


class TodoCommandsTest(HomeTest):
    def setUp(self):
        super().setUp()
        self.setup_family("Ana, Luis, Theo (kid), Lily (kid), Zoe (teen)")

    def data(self):
        return Hub(self.home).household().data("todos")

    def test_personal_lists_are_private(self):
        self.ok("todo", "add", "Book the dentist", "--mine")
        self.assertEqual(self.ok("todo", "show", "--mine")["lists"][0]["open"][0]["title"], "Book the dentist")
        luis = self.ok("todo", "show", "--as", "Luis")
        titles = [t["title"] for sec in luis["lists"] for t in sec["open"]]
        self.assertNotIn("Book the dentist", titles)
        self.err("not_found", "todo", "task", "Book the dentist", "--as", "Luis")
        self.ok("who", "chat", "fam", "--type", "group", "--minors", "no")
        self.ok("who", "link", "fam", "--participant", "@ana", "--member", "Ana")
        self.err("hidden_in_group", "todo", "show", "--mine", "--chat", "fam", "--from", "@ana")
        self.err("private_list", "todo", "add", "Secret", "--mine", "--assign", "Luis")

    def test_assigning_someone_leaves_a_notice_they_get_next_time(self):
        out = self.ok("todo", "add", "Fix the gate", "--assign", "Luis", "--due", "saturday")
        self.assertEqual(out["delivery"], "next_time_they_talk")
        self.assertIn("Don't message Luis", out["outside_chat"])
        out = self.ok("todo", "show", "--as", "Luis")
        self.assertEqual(out["pending_notices"], 1)
        notes = self.ok("notices", "list", "--as", "Luis")
        self.assertEqual(notes["notices"][0]["text"], "New task from Ana: Fix the gate, due Sat 2026-10-24")
        self.assertNotIn("pending_notices", self.ok("todo", "show", "--as", "Luis"))  # delivered once

    def test_no_notice_for_yourself_or_for_kids(self):
        out = self.ok("todo", "add", "Call the bank", "--assign", "Ana")
        self.assertNotIn("delivery", out)
        out = self.ok("todo", "add", "Feed the cat", "--assign", "Theo")
        self.assertEqual(out["delivery"], "fridge_sheet")
        self.assertEqual(Hub(self.home).household().data("notices")["notices"], [])

    def test_assigning_someone_in_the_group_tells_them_there(self):
        self.ok("who", "chat", "fam", "--type", "group", "--minors", "no")
        self.ok("who", "link", "fam", "--participant", "@ana", "--member", "Ana")
        self.ok("who", "link", "fam", "--participant", "@luis", "--member", "Luis", "--owner-confirmed", "yes")
        out = self.ok("todo", "add", "Fix the gate", "--assign", "Luis", "--chat", "fam", "--from", "@ana")
        self.assertEqual(out["delivery"], "in_this_chat")
        self.assertNotIn("pending_notices", self.ok("todo", "show", "--as", "Luis"))

    def test_rotation_stars_and_the_next_one_made_once(self):
        out = self.ok("todo", "add", "Take out the bins", "--repeat", "weekly on mon", "--rotate", "Theo, Lily, Zoe")
        self.assertEqual(out["task"]["assignee"], "Theo")
        out = self.ok("todo", "done", "bins")
        result = out["results"][0]
        self.assertEqual((result["star_to"], result["next"]["assignee"], result["next"]["id"]),
                         ("Theo", "Lily", "T1.20261026"))  # fmt: skip
        self.ok("todo", "done", "T1")  # the same task again: nothing new
        self.assertEqual(len([t for t in self.data()["tasks"] if t["title"] == "Take out the bins"]), 2)
        out = self.ok("todo", "done", "bins")  # asked twice by name: next week's isn't ticked off by accident
        self.assertEqual(out["results"][0]["status"], "already_done")
        self.ok("todo", "done", "T1.20261026")  # early on purpose, by id
        stars = {m["name"]: m["stars"] for m in self.ok("member", "list")["members"] if "stars" in m}
        self.assertEqual(stars, {"Theo": 1, "Lily": 1, "Zoe": 0})
        nxt = [t for t in self.data()["tasks"] if t["id"] == "T1.20261102"][0]
        self.assertEqual(Hub(self.home).household().member_name(nxt["assignee"]), "Zoe")

    def test_by_gives_the_star_to_whoever_did_it_and_undo_takes_it_back(self):
        self.ok("todo", "add", "Tidy the lounge", "--assign", "Theo")
        out = self.ok("todo", "done", "Tidy the lounge", "--by", "Lily")
        self.assertEqual(out["results"][0]["star_to"], "Lily")
        self.ok("todo", "undo", "Tidy the lounge")
        stars = {m["name"]: m["stars"] for m in self.ok("member", "list")["members"] if "stars" in m}
        self.assertEqual(stars["Lily"], 0)
        out = self.ok("todo", "done", "Tidy the lounge", "--by", "Luis")  # an adult: no star
        self.assertIsNone(out["results"][0]["star_to"])

    def test_rotation_skips_someone_who_left(self):
        self.ok("todo", "add", "Dishes", "--repeat", "daily", "--rotate", "Theo, Lily, Zoe")
        self.ok("member", "remove", "Lily", "--owner-confirmed", "yes")
        out = self.ok("todo", "done", "Dishes")
        self.assertEqual(out["results"][0]["next"]["assignee"], "Zoe")

    def test_subtasks_one_level_and_the_checklist_repeats_unticked(self):
        self.ok("todo", "add", "Clean the bathroom", "--repeat", "weekly")
        self.ok("todo", "add", "Sink", "--parent", "Clean the bathroom")
        self.ok("todo", "add", "Mirror", "--parent", "Clean the bathroom")
        self.err("too_deep", "todo", "add", "Taps", "--parent", "Sink")
        self.ok("todo", "done", "Sink")
        out = self.ok("todo", "task", "Clean the bathroom")
        self.assertEqual(out["task"]["progress"], "1/2")
        self.ok("todo", "done", "Clean the bathroom")
        nxt = [t for t in self.data()["tasks"] if t.get("parent") == "T1.20261026"]
        self.assertEqual(sorted((t["title"], t["completed_at"]) for t in nxt), [("Mirror", None), ("Sink", None)])
        out = self.ok("todo", "delete", "T1.20261026")
        self.assertIn("2 subtasks", out["summary"])

    def test_counted_and_ending_repeats_stop(self):
        self.ok("todo", "add", "Antibiotics", "--repeat", "daily", "--times", "2")
        out = self.ok("todo", "done", "Antibiotics")
        self.assertIn("next", out["results"][0])
        out = self.ok("todo", "done", out["results"][0]["next"]["id"])
        self.assertNotIn("next", out["results"][0])
        self.ok("todo", "add", "Clinic", "--repeat", "weekly", "--until", "2026-10-25")
        out = self.ok("todo", "done", "Clinic")
        self.assertNotIn("next", out["results"][0])

    def test_rotation_needs_a_repeat_and_no_repeat_clears_it(self):
        self.err("bad_rotation", "todo", "add", "Dishes", "--rotate", "Theo, Lily")
        self.err("bad_rotation", "todo", "add", "Dishes", "--repeat", "daily", "--rotate", "Theo")
        self.ok("todo", "add", "Dishes", "--repeat", "daily", "--rotate", "Theo, Lily")
        out = self.ok("todo", "edit", "Dishes", "--no-repeat")
        self.assertNotIn("rotation", out["task"])
        self.assertNotIn("repeats", out["task"])

    def test_changing_the_rotation_keeps_the_current_turn(self):
        self.ok("todo", "add", "Dishes", "--repeat", "daily", "--rotate", "Theo, Lily")
        self.ok("todo", "done", "Dishes")  # now Lily's turn
        out = self.ok("todo", "edit", "T1.20261020", "--rotate", "Zoe, Lily, Theo")
        self.assertEqual((out["task"]["assignee"], out["task"]["rotation"]), ("Lily", ["Zoe", "Lily", "Theo"]))

    def test_assignee_must_be_able_to_see_todos(self):
        self.ok("member", "access", "Luis", "--set", "todos=none")
        self.err("cannot_see_todos", "todo", "add", "Fix it", "--assign", "Luis")

    def test_show_sorts_overdue_first_and_counts_done_today(self):
        self.ok("todo", "add", "Later", "--due", "+5")
        self.ok("todo", "add", "Late", "--due", "-2")
        self.ok("todo", "add", "Whenever")
        self.ok("todo", "add", "Soon", "--due", "today", "--priority", "high")
        self.ok("todo", "done", "Whenever")
        out = self.ok("todo", "show", "--list", "Household Tasks")
        section = out["lists"][0]
        self.assertEqual([t["title"] for t in section["open"]], ["Late", "Soon", "Later"])
        self.assertEqual(section["done_count"], 1)
        self.assertIn("Late — ⚠️ 2026-10-17", out["text"])  # overdue is flagged, in the household's date format

    def test_photos_are_file_references(self):
        self.ok("todo", "add", "Fix the gate")
        self.err("no_file", "todo", "photo", "Fix the gate", "--add", str(self.home / "nope.jpg"))
        photo = self.home / "gate.jpg"
        photo.write_bytes(b"\xff\xd8\xff")
        self.ok("todo", "photo", "Fix the gate", "--add", str(photo))
        out = self.ok("todo", "photo", "Fix the gate", "--add", str(photo))  # once only
        self.assertEqual(out["photos"], [str(photo)])
        self.assertEqual(self.ok("todo", "photo", "Fix the gate", "--remove", str(photo))["photos"], [])

    def test_finished_tasks_clear_after_the_retention_period_but_stars_stay(self):
        self.ok("todo", "add", "Feed the cat", "--assign", "Theo")
        self.ok("todo", "done", "Feed the cat")
        later = {"FRIDGE_NOW": "2027-02-01T08:00:00"}
        self.ok("todo", "add", "Something new", env=later)
        titles = [t["title"] for t in self.data()["tasks"]]
        self.assertEqual(titles, ["Something new"])
        stars = {m["name"]: m["stars"] for m in self.ok("member", "list")["members"] if "stars" in m}
        self.assertEqual(stars["Theo"], 1)

    def test_custom_lists_and_protected_defaults(self):
        out = self.ok("todo", "list-new", "--name", "Garden", "--icon", "🌱")
        self.assertEqual(out["list"]["icon"], "🌱")
        self.ok("todo", "add", "Weed the beds", "--list", "Garden")
        self.err("protected", "todo", "list-delete", "Household Tasks")
        self.ok("todo", "list-delete", "Garden")
        self.err("not_found", "todo", "add", "x", "--list", "Garden")
        self.ok("todo", "list-restore", "Garden")
        self.assertEqual(self.ok("todo", "lists")["lists"][0]["name"], "My Tasks")  # your own list first

    def test_chore_chart(self):
        self.ok("todo", "add", "Feed the cat", "--assign", "Theo", "--due", "today")
        self.ok("member", "stars", "Theo", "--add", "2")
        chart = {c["member"]: c for c in self.ok("todo", "chores")["chart"]}
        self.assertEqual(chart["Theo"]["stars"], 2)
        self.assertEqual(chart["Theo"]["tasks"][0]["title"], "Feed the cat")
        self.assertNotIn("stars", chart["Ana"])

    def test_dry_run_saves_nothing(self):
        self.ok("todo", "add", "Ghost", "--dry-run")
        self.assertEqual(self.data()["tasks"], [])

    def test_kids_cannot_tick_off_their_own_chores(self):
        self.ok("todo", "add", "Feed the cat", "--assign", "Theo")
        self.err("minor_cannot_chat", "todo", "done", "Feed the cat", "--as", "Theo")


if __name__ == "__main__":
    unittest.main()
