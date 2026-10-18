"""The bin (an independent review of 1.0.0: only lists could be restored). Deleted tasks, events, notes, recipes
and budget items can be restored for the retention period, with the same privacy they had before."""

import json
import zipfile

from helpers import HomeTest
from fridgedoor.store import Hub


class BinTest(HomeTest):
    def setUp(self):
        super().setUp()
        self.setup_family("Ana, Luis, Theo (kid)", "GB")

    def data(self, module):
        return Hub(self.home).household().data(module)

    def titles(self, module, key, field="title"):
        return [r[field] for r in self.data(module)[key]]

    def test_tasks_events_notes_and_recipes_come_back(self):
        self.ok("todo", "add", "Fix the gate", "--due", "friday")
        self.ok("todo", "add", "Buy hinges", "--parent", "Fix the gate")
        out = self.ok("todo", "delete", "Fix the gate")
        self.assertIn("in the bin for 90 days", out["summary"])
        self.assertEqual(out["undo"], 'fridge bin restore "Fix the gate"')
        self.assertNotIn("Buy hinges", self.titles("todos", "tasks"))
        self.ok("cal", "add", "Dentist", "--date", "friday", "--time", "15:00")
        self.ok("cal", "delete", "Dentist")
        self.ok("note", "add", "Wifi", "--body", "pw")
        self.ok("note", "delete", "Wifi")
        self.ok("recipe", "add", "--title", "Pancakes", "--servings", "4", "--ingredient", "2 eggs")
        self.ok("recipe", "delete", "Pancakes")
        shown = {i["name"] for i in self.ok("bin", "show")["items"]}
        self.assertEqual(shown, {"Fix the gate", "Dentist", "Wifi", "Pancakes"})
        self.ok("bin", "restore", "Fix the gate", "--dry-run")
        self.assertNotIn("Fix the gate", self.titles("todos", "tasks"))  # a dry run restores nothing
        for name in ("Fix the gate", "Dentist", "Wifi", "Pancakes"):
            self.ok("bin", "restore", name)
        self.assertTrue({"Fix the gate", "Buy hinges"} <= set(self.titles("todos", "tasks")))  # with its subtask
        self.assertIn("Dentist", self.titles("calendar", "events"))
        self.assertIn("Wifi", self.titles("notes", "notes"))
        self.assertIn("Pancakes", self.titles("recipes", "recipes"))
        self.assertEqual(self.ok("bin", "show")["items"], [])

    def test_budget_items_come_back_with_their_links(self):
        self.ok("budget", "bill-add", "Broadband", "--amount", "32.99", "--due", "2026-10-18", "--repeat", "monthly")
        self.ok("budget", "bill-paid", "Broadband")
        paid = self.data("budget")["expenses"][-1]["id"]
        self.ok("budget", "expense-delete", paid)

        def broadband():
            return next(b for b in self.data("budget")["bills"] if b["name"] == "Broadband")

        self.assertEqual(broadband()["paid"], {})
        out = self.ok("bin", "restore", paid)
        self.assertIn("Broadband is marked paid again", out["summary"])
        self.assertEqual(list(broadband()["paid"].values()), [paid])
        self.ok("budget", "category-add", "Pets", "--monthly", "50")
        self.ok("budget", "bill-add", "Vet plan", "--amount", "20", "--due", "2026-11-01", "--category", "Pets")
        self.ok("budget", "category-delete", "Pets")
        self.ok("budget", "goal-add", "Holiday", "--target", "1000")
        self.ok("budget", "goal-delete", "Holiday")
        self.ok("budget", "bill-delete", "Broadband")
        for name in ("Pets", "Holiday", "Broadband"):
            self.ok("bin", "restore", name)
        budget = self.data("budget")
        pets = next(c for c in budget["categories"] if c["name"] == "Pets")
        self.assertEqual(next(b for b in budget["bills"] if b["name"] == "Vet plan")["category"], pets["id"])
        self.assertIn("Holiday", [g["name"] for g in budget["goals"]])
        self.assertIn("Broadband", [b["name"] for b in budget["bills"]])

    def test_someone_elses_private_things_stay_theirs_in_the_bin(self):
        self.ok("cal", "add", "Therapy", "--date", "friday", "--private", "--as", "Luis")
        self.ok("cal", "delete", "Therapy", "--as", "Luis")
        self.ok("note", "add", "Diary", "--body", "x", "--private", "--as", "Luis")
        self.ok("note", "delete", "Diary", "--as", "Luis")
        self.ok("todo", "add", "Call the bank", "--mine", "--as", "Luis")
        self.ok("todo", "delete", "Call the bank", "--as", "Luis")
        self.assertEqual(self.ok("bin", "show")["items"], [])  # Ana sees none of it
        self.err("not_found", "bin", "restore", "Therapy")
        self.assertEqual(len(self.ok("bin", "show", "--as", "Luis")["items"]), 3)
        with zipfile.ZipFile(self.ok("export")["file"]) as zf:  # the owner's export leaves them out
            files = {n.split("/")[-1]: json.loads(zf.read(n)) for n in zf.namelist() if n.endswith(".json")}
        for name in ("calendar.json", "notes.json", "todos.json"):
            self.assertEqual(files[name]["bin"], [], name)
        self.confirmed("member", "remove", "Luis")  # and removing Luis clears them for good
        for module in ("calendar", "notes", "todos"):
            self.assertEqual(self.data(module)["bin"], [], module)

    def test_a_removed_member_is_taken_off_shared_things_in_the_bin(self):
        self.ok("todo", "add", "Bins", "--assign", "Luis")
        self.ok("todo", "delete", "Bins")
        self.confirmed("member", "remove", "Luis")
        entry = self.data("todos")["bin"][0]
        self.assertIsNone(entry["records"][0]["assignee"])

    def test_not_in_a_group_chat_with_kids(self):
        self.ok("who", "chat", "fam", "--type", "group", "--minors", "yes")
        self.ok("who", "link", "fam", "--participant", "@ana", "--member", "Ana")
        self.err("hidden_in_group", "bin", "show", "--chat", "fam", "--from", "@ana")

    def test_things_leave_the_bin_after_the_retention_period(self):
        self.ok("note", "add", "Old", "--body", "x")
        self.ok("note", "delete", "Old")
        later = {"FRIDGE_NOW": "2027-01-18T08:00:00"}  # 91 days on
        self.assertEqual(self.ok("bin", "show", env=later)["items"], [])
        self.ok("note", "add", "New", "--body", "y", env=later)  # the next save of the notes file empties it
        self.assertEqual(self.data("notes")["bin"], [])

    def test_a_restore_that_would_clash_asks_for_a_rename_first(self):
        self.ok("note", "add", "Wifi", "--body", "old")
        self.ok("note", "delete", "Wifi")
        self.ok("note", "add", "Wifi", "--body", "new")
        self.err("exists", "bin", "restore", "Wifi")

    def test_a_task_whose_list_is_gone_comes_back_on_household_tasks(self):
        self.ok("todo", "list-new", "--name", "Garden")
        self.ok("todo", "add", "Weed the beds", "--list", "Garden")
        self.ok("todo", "delete", "Weed the beds")
        self.ok("todo", "list-delete", "Garden")
        out = self.ok("bin", "restore", "Weed the beds")
        self.assertIn("Household Tasks", out["summary"])
