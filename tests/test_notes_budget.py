"""Notes (privacy and sensitive notes) and the budget (exact money, bills, goals, access)."""

from decimal import Decimal

from helpers import HomeTest
from fridgedoor import money


class NotesTest(HomeTest):
    def setUp(self):
        super().setUp()
        self.setup_family("Ana, Luis, Theo (kid)", "GB")
        self.ok("note", "add", "Wifi", "--body", "Network: Flat-5G", "--pin", "--sensitive")
        self.ok("note", "add", "Sitter instructions", "--body", "Bedtime 8pm", "--folder", "Kids", "--pin")
        self.ok("note", "add", "My diary", "--body", "Secret", "--private")

    def titles(self, *args):
        return [n["title"] for n in self.ok("note", "list", *args)["notes"]]

    def test_pinned_first_private_only_for_the_author(self):
        self.assertEqual(self.titles(), ["Wifi", "Sitter instructions", "My diary"])
        self.assertEqual(self.titles("--as", "Luis"), ["Wifi", "Sitter instructions"])
        self.err("not_found", "note", "show", "My diary", "--as", "Luis")

    def test_sensitive_notes_stay_out_of_group_chats_unless_the_owner_allows(self):
        self.ok("who", "chat", "pair", "--type", "group", "--minors", "no")
        self.ok("who", "link", "pair", "--participant", "@ana", "--member", "Ana")
        group = ("--chat", "pair", "--from", "@ana")
        out = self.ok("note", "list", *group)
        self.assertEqual([n["title"] for n in out["notes"]], ["Sitter instructions"])
        self.assertIn("1 sensitive note not shown", out["summary"])
        self.err("hidden_in_group", "note", "show", "Wifi", *group)  # says why, so nobody makes a second Wifi note
        self.err("exists", "note", "add", "Wifi", "--body", "again", *group)
        self.confirmed("household", "settings", "--set", "sensitive_notes_in_groups=yes", words="yes, fine")
        self.assertIn("Wifi", [n["title"] for n in self.ok("note", "list", *group)["notes"]])

    def test_a_group_never_learns_what_someones_private_notes_are_called(self):
        self.ok("who", "chat", "pair", "--type", "group", "--minors", "no")
        self.ok("who", "link", "pair", "--participant", "@ana", "--member", "Ana")
        self.err("exists", "note", "add", "My diary")  # her own chat: a clash with her own note
        self.ok("note", "add", "My diary", "--body", "Ours", "--chat", "pair", "--from", "@ana")

    def test_notes_never_show_in_a_chat_with_kids(self):
        self.ok("who", "chat", "fam", "--type", "group", "--minors", "yes")
        self.ok("who", "link", "fam", "--participant", "@ana", "--member", "Ana")
        self.err("hidden_in_group", "note", "list", "--chat", "fam", "--from", "@ana")  # kids: notes none

    def test_checklists_folders_tags_and_edits(self):
        self.ok("note", "add", "Packing", "--item", "tent", "--item", "sleeping bags", "--tag", "#Trips")
        out = self.ok("note", "check", "Packing", "1", "sleeping")
        self.assertEqual(out["progress"], "2/2")
        self.ok("note", "edit", "Packing", "--add-item", "torch", "--untag", "trips")
        shown = self.ok("note", "show", "Packing")["note"]
        self.assertEqual((shown["tags"], len(shown["checklist"])), ([], 3))
        self.assertEqual(self.titles("--folder", "kids"), ["Sitter instructions"])
        self.assertEqual(self.titles("--search", "bedtime"), ["Sitter instructions"])
        self.ok("note", "edit", "Sitter instructions", "--append", "Allergic to peanuts")
        self.assertIn("peanuts", self.ok("note", "show", "Sitter instructions")["note"]["body"])
        self.err("not_authorized", "note", "edit", "Wifi", "--private", "--as", "Luis")  # only the author

    def test_removing_a_member_deletes_their_private_notes(self):
        self.ok("note", "add", "Luis's list", "--private", "--as", "Luis")
        out = self.confirmed("member", "remove", "Luis", words="yes")
        self.assertIn("deleted 1 private note", out["changes"])


class BudgetTest(HomeTest):
    def setUp(self):
        super().setUp()
        self.setup_family("Ana, Luis, Mateo (teen)", "CA")
        self.ok("budget", "category-defaults")
        self.ok("budget", "category-edit", "Groceries", "--monthly", "800")

    def test_exact_totals_and_over_budget(self):
        self.ok("budget", "spend", "254.20", "--category", "Groceries")
        out = self.ok("budget", "spend", "612.15", "--category", "groceries", "--by", "Luis")
        self.assertIn("$866.35 of $800.00", out["summary"])
        self.assertIn("over budget", out["summary"])
        month = self.ok("budget", "month")
        self.assertEqual(Decimal(month["spent"]), Decimal("866.35"))
        self.assertIn("$866.35 of $800.00 in the categories with a budget ($66.35 over)", month["summary"])
        self.assertEqual(month["over"], ["Groceries"])
        for _ in range(3):  # a third of a cent never goes missing
            self.ok("budget", "spend", "0.10", "--category", "Fun")
        self.assertEqual(Decimal(self.ok("budget", "expenses", "--category", "Fun")["total"]), Decimal("0.30"))

    def test_ambiguous_or_bad_amounts_are_refused(self):
        for amount in ("1,500", "1.234,50", "-5", "0", "lots"):
            self.err("bad_number", "budget", "spend", amount, "--category", "Groceries")

    def test_zero_decimal_currencies(self):
        self.ok("household", "settings", "--set", "currency=JPY")
        out = self.ok("budget", "spend", "1235", "--category", "Groceries")
        self.assertEqual(out["expense"]["amount_text"], "¥1,235")
        self.err("bad_number", "budget", "spend", "1234.6", "--category", "Groceries")  # asked, not rounded

    def test_bills_paid_upcoming_and_on_the_calendar(self):
        self.ok("budget", "bill-add", "Rent", "--amount", "1800", "--due", "2026-11-01", "--repeat", "monthly",
                "--category", "Housing")  # fmt: skip
        self.ok("budget", "bill-add", "Hydro", "--amount", "141.80", "--due", "2026-10-22", "--repeat", "monthly")
        bills = self.ok("budget", "bills")["bills"]
        self.assertEqual([(b["name"], b["due"]) for b in bills], [("Hydro", "2026-10-22"), ("Rent", "2026-11-01")])
        out = self.ok("budget", "bill-paid", "Hydro")
        self.assertIn("Next due Sun 2026-11-22", out["summary"])  # the household writes YYYY-MM-DD
        self.assertIn("already recorded", self.ok("budget", "bill-paid", "Hydro", "--due", "2026-10-22")["summary"])
        self.assertEqual([b["name"] for b in self.ok("budget", "bills")["bills"]], ["Rent"])
        layer = [o["title"] for o in self.ok("cal", "agenda", "--days", "14", "--layers", "bills")["occurrences"]]
        self.assertEqual(layer, ["Hydro due ($141.80) ✓ paid", "Rent due ($1,800.00)"])
        today = self.ok("today", env={"FRIDGE_NOW": "2026-10-28T08:00:00"})
        self.assertIn("Rent $1,800.00 — due 2026-11-01", today["sections"]["bills"]["lines"])

    def test_the_bills_layer_needs_the_persons_own_budget_access(self):
        self.ok("budget", "bill-add", "Rent", "--amount", "1800", "--due", "2026-10-25", "--repeat", "monthly")

        def layer(*who):
            return [o["title"] for o in self.ok("cal", "agenda", "--layers", "bills", *who)["occurrences"]]

        self.assertEqual(layer(), ["Rent due ($1,800.00)"])
        self.ok("member", "access", "Luis", "--set", "budget=none")
        self.assertEqual(layer("--as", "Luis"), [])

    def test_savings_goals(self):
        self.ok("budget", "goal-add", "Holiday fund", "--target", "3000", "--by", "2027-07-01")
        self.ok("budget", "goal-save", "Holiday fund", "150", "--by", "Luis")
        out = self.ok("budget", "goal-save", "Holiday fund", "-50")
        self.assertEqual((out["goal"]["saved_text"], out["goal"]["percent"]), ("$100.00", 3))
        self.err("bad_number", "budget", "goal-save", "Holiday fund", "-500")
        goals = self.ok("budget", "goals")["goals"]
        self.assertIn("per_month_text", goals[0])

    def test_trend_and_categories(self):
        self.ok("budget", "spend", "100", "--category", "Groceries", "--date", "2026-09-10")
        self.ok("budget", "spend", "50", "--category", "Groceries")
        trend = self.ok("budget", "trend", "--months", "3")["months"]
        self.assertEqual([(m["month"], m["total_text"]) for m in trend],
                         [("2026-08", "$0.00"), ("2026-09", "$100.00"), ("2026-10", "$50.00")])  # fmt: skip
        self.err("in_use", "budget", "category-delete", "Groceries")
        self.ok("budget", "category-delete", "Groceries", "--move-to", "Other")

    def test_adults_only_by_default(self):
        self.err("minor_cannot_chat", "budget", "month", "--as", "Mateo")
        self.ok("member", "access", "Luis", "--set", "budget=none")
        self.err("not_authorized", "budget", "month", "--as", "Luis")
        self.ok("who", "chat", "fam", "--type", "group", "--minors", "yes")
        self.ok("who", "link", "fam", "--participant", "@ana", "--member", "Ana")
        self.err("hidden_in_group", "budget", "month", "--chat", "fam", "--from", "@ana")

    def test_receipts_are_file_paths_and_dry_runs_save_nothing(self):
        receipt = self.home / "receipt.jpg"
        receipt.write_bytes(b"\xff\xd8\xff")
        out = self.ok("budget", "spend", "38", "--category", "Eating out", "--receipt", str(receipt), "--dry-run")
        self.assertEqual(out["expense"]["receipt"], str(receipt))
        self.assertEqual(self.ok("budget", "expenses")["expenses"], [])
        self.err("no_file", "budget", "spend", "38", "--category", "Eating out", "--receipt", str(self.home / "x.jpg"))


class MoneyDisplayTest(HomeTest):
    def test_symbols_codes_and_separators(self):
        cad = money.currency_display({"currency": "CAD"})
        self.assertEqual(money.fmt("1234.5", cad), "$1,234.50")
        self.assertEqual(money.fmt("1234.5", cad, code=True), "$1,234.50 CAD")
        eur = money.currency_display({"currency": "EUR"})
        self.assertEqual(money.fmt("1234.5", eur), "1.234,50 €")
        self.assertEqual(money.fmt("-12", money.currency_display({"currency": "GBP"})), "-£12.00")
        self.assertEqual(money.fmt("1", money.currency_display({"currency": "KWD"})), "KWD 1.000")
        self.assertEqual(money.fmt("5", money.currency_display({"currency": "USD", "currency_display": "never"}),
                                   code=True), "$5.00")  # fmt: skip
