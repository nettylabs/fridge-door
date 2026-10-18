"""Shopping and grocery lists: quick add, aisle sorting and learning, suggestions (ported cases), list access."""

import datetime as dt
import unittest
from pathlib import Path

from helpers import HomeTest
from fridgedoor import seed_aisles, shopping
from fridgedoor.seed_aisles import SEED, item_key
from fridgedoor.store import Hub

NOW = dt.datetime(2026, 10, 19, 12, 0, tzinfo=dt.timezone.utc)


def row(times, days_ago=None, qty=None, name=None):
    out = {"times": times, "last_qty": qty, "name": name}
    if days_ago is not None:
        out["last_at"] = (NOW - dt.timedelta(days=days_ago)).isoformat()
    return out


class QuickAddTest(unittest.TestCase):
    def test_only_a_trailing_x_number_is_a_quantity(self):
        self.assertEqual(shopping.parse_quick("milk x2"), ("milk", "2"))
        self.assertEqual(shopping.parse_quick("  eggs   X12 "), ("eggs", "12"))
        self.assertEqual(shopping.parse_quick("water ×6"), ("water", "6"))
        self.assertEqual(shopping.parse_quick("7up"), ("7up", None))
        self.assertEqual(shopping.parse_quick("2 lbs carrots"), ("carrots", "2 lbs"))  # an amount said first
        self.assertEqual(shopping.parse_quick("500g mince"), ("mince", "500 g"))
        self.assertEqual(shopping.parse_quick("2 loaves of bread"), ("bread", "2 loaves"))
        self.assertEqual(shopping.parse_quick("12 eggs"), ("eggs", "12"))
        self.assertEqual(shopping.parse_quick("a dozen eggs"), ("eggs", "a dozen"))
        self.assertEqual(shopping.parse_quick("an onion"), ("onion", None))
        self.assertEqual(shopping.parse_quick("box x1000"), ("box x1000", None))  # more than 3 digits stays literal
        self.assertEqual(shopping.parse_quick("x2"), ("x2", None))

    def test_quantity_labels(self):
        self.assertEqual(shopping.qty_label("2"), "x2")
        self.assertEqual(shopping.qty_label("2 lbs"), "2 lbs")
        self.assertEqual(shopping.qty_label(None), "")


class ItemKeyAndSeedTest(unittest.TestCase):
    def test_item_key_is_case_space_and_plural_agnostic(self):
        self.assertEqual(item_key(" Eggs "), item_key("egg"))
        self.assertEqual(item_key("Cookies"), item_key("cookie"))
        self.assertEqual(item_key("berries"), item_key("berry"))
        self.assertEqual(item_key("tomatoes"), item_key("tomato"))
        self.assertEqual(item_key("peaches"), item_key("peach"))
        self.assertEqual(item_key("Zoë's  Cheese"), "zoe's cheese")
        for word in ("hummus", "swiss", "glass", "gas", "pie"):
            self.assertEqual(item_key(word), word)

    def test_seed_is_big_consistent_and_collision_free(self):
        self.assertGreaterEqual(len(SEED), 300)
        for key, aisle in SEED.items():
            self.assertEqual(item_key(key), key, f"{key} isn't a fixed point")
            self.assertIn(aisle, shopping.CANONICAL_AISLES)
        seen = {}
        for aisle, items in seed_aisles._RAW.items():
            for item in items:
                key = item_key(item)
                self.assertNotIn(key, seen, f"{item} collides with {seen.get(key)}")
                seen[key] = item

    def test_british_and_australian_names(self):
        for item, aisle in (("courgettes", "Produce"), ("capsicum", "Produce"), ("crisps", "Snacks"),
                            ("nappies", "Baby"), ("washing-up liquid", "Household"), ("prawns", "Seafood"),
                            ("mince", "Meat"), ("tinned tomatoes", "Canned")):  # fmt: skip
            self.assertEqual(shopping.categorize(item, {}), aisle, item)


class CategorizeTest(unittest.TestCase):
    def test_household_correction_beats_the_seed_and_other_is_learned(self):
        self.assertEqual(shopping.categorize("Milk", {}), "Dairy")
        self.assertEqual(shopping.categorize("milk", {"milk": "Fridge"}), "Fridge")
        self.assertEqual(shopping.categorize("milk", {"milk": "Other"}), "Other")
        self.assertIsNone(shopping.categorize("zaatar", {}))
        self.assertEqual(shopping.categorize("zaatar", {}, seed={"zaatar": "Spices"}), "Spices")

    def test_aisle_matching_ignores_case_and_spaces(self):
        lst = {"aisles": [{"id": "A1", "name": "Dairy"}, {"id": "A2", "name": " Fresh Produce "}]}
        self.assertEqual(shopping.match_aisle("dairy", lst), "A1")
        self.assertEqual(shopping.match_aisle("fresh produce", lst), "A2")
        self.assertIsNone(shopping.match_aisle("Frozen", lst))
        self.assertIsNone(shopping.match_aisle(None, lst))
        self.assertIsNone(shopping.match_aisle("Other", lst))  # "Other" only matches a literal Other aisle


class SuggestTest(unittest.TestCase):
    """Ported from the original suggest tests."""

    def names(self, results):
        return [r["name"] for r in results]

    def test_empty_input_suggests_nothing(self):
        self.assertEqual(shopping.suggest("  ", {"milk": row(3)}, now=NOW), [])

    def test_prefix_and_contains_both_match(self):
        history = {"milk": row(2, 30), "oat milk": row(1, 30)}
        self.assertEqual(self.names(shopping.suggest("mil", history, now=NOW, seed={})), ["milk", "oat milk"])

    def test_typed_plurals_match_singular_keys(self):
        self.assertEqual(self.names(shopping.suggest("eggs", {"egg": row(1, 30)}, now=NOW, seed={})), ["egg"])

    def test_times_bought_with_a_recency_boost(self):
        history = {"bread": row(3, 30), "bagel": row(2, 3)}  # 2 x 1.5 = 3 ties with 3, prefix both, then name
        self.assertEqual(self.names(shopping.suggest("b", history, now=NOW, seed={})), ["bagel", "bread"])
        history = {"bread": row(4, 30), "bagel": row(2, 3)}
        self.assertEqual(self.names(shopping.suggest("b", history, now=NOW, seed={})), ["bread", "bagel"])

    def test_prefix_beats_contains_on_equal_score_then_name(self):
        history = {"ice cream": row(2, 30), "rice": row(2, 30), "iced tea": row(2, 30)}
        got = self.names(shopping.suggest("ice", history, now=NOW, seed={}))
        self.assertEqual(got, ["ice cream", "iced tea", "rice"])

    def test_caps_at_six(self):
        history = {f"a{i}": row(1, 30) for i in range(10)}
        self.assertEqual(len(shopping.suggest("a", history, now=NOW, seed={})), 6)

    def test_excludes_items_already_on_the_list(self):
        history = {"milk": row(5, 1), "mints": row(1, 1)}
        self.assertEqual(self.names(shopping.suggest("m", history, exclude=["Milk"], now=NOW, seed={})), ["mints"])

    def test_carries_the_remembered_quantity(self):
        out = shopping.suggest("mil", {"milk": row(3, 1, qty="2")}, now=NOW, seed={})
        self.assertEqual(out[0]["qty"], "2")

    def test_seed_fills_free_slots_prefix_first_then_contains_alphabetically(self):
        seed = {"banana": "Produce", "bagel": "Bakery", "kebab": "Meat", "cabbage": "Produce"}
        out = shopping.suggest("ba", {}, now=NOW, seed=seed)
        self.assertEqual(self.names(out), ["bagel", "banana", "cabbage", "kebab"])

    def test_history_outranks_seed_and_dedupes(self):
        seed = {"banana": "Produce", "bagel": "Bakery"}
        out = shopping.suggest("ba", {"cabbage": row(1, 30)}, now=NOW, seed=seed)
        self.assertEqual(self.names(out), ["cabbage", "bagel", "banana"])
        out = shopping.suggest("ba", {"banana": row(1, 30)}, exclude=["bagel"], now=NOW, seed=seed)
        self.assertEqual(self.names(out), ["banana"])

    def test_no_seed_when_history_fills_the_limit(self):
        history = {f"ba{i}": row(1, 30) for i in range(6)}
        out = shopping.suggest("ba", history, now=NOW, seed={"bagel": "Bakery"})
        self.assertNotIn("bagel", self.names(out))


class GroupingTest(unittest.TestCase):
    def test_store_order_other_last_and_empty_aisles_hidden(self):
        lst = {"aisles": [{"id": "A1", "name": "Produce"}, {"id": "A2", "name": "Bakery"},
                          {"id": "A3", "name": "Dairy"}]}  # fmt: skip
        items = [{"id": "I1", "aisle": "A3"}, {"id": "I2", "aisle": None}, {"id": "I3", "aisle": "A1"},
                 {"id": "I4", "aisle": "A9"}]  # fmt: skip
        groups = shopping.group_by_aisle(lst, items)
        self.assertEqual([g["aisle"] for g in groups], ["Produce", "Dairy", "Other"])
        self.assertEqual([i["id"] for i in groups[-1]["items"]], ["I2", "I4"])

    def test_a_list_without_aisles_has_one_untitled_group(self):
        groups = shopping.group_by_aisle({"aisles": []}, [{"id": "I1", "aisle": None}])
        self.assertEqual(groups, [{"aisle": None, "items": [{"id": "I1", "aisle": None}]}])


class ShopCommandsTest(HomeTest):
    def setUp(self):
        super().setUp()
        self.setup_family("Ana, Luis, Sofia (kid)", "GB")

    def test_add_files_items_and_avoids_duplicates(self):
        out = self.ok("shop", "add", "milk x2", "courgettes, crumpets", "zaatar")
        self.assertEqual([r["item"]["aisle"] for r in out["results"]], ["Dairy", "Produce", "Bakery", "Other"])
        self.assertEqual(out["results"][0]["item"]["qty"], "2")
        out = self.ok("shop", "add", "Milk")
        self.assertEqual(out["results"][0]["status"], "already_on_list")
        self.assertIn("--again", out["hint"])
        out = self.ok("shop", "add", "milk", "--again")
        self.assertEqual(out["results"][0]["status"], "added")

    def test_cross_off_records_history_and_readd_brings_back_the_quantity(self):
        self.ok("shop", "add", "milk x2", "eggs")
        out = self.ok("shop", "cross", "milk", "bread")
        self.assertEqual([r["status"] for r in out["results"]], ["crossed", "not_found"])
        history = Hub(self.home).household().data("shopping")["history"]
        self.assertEqual((history["milk"]["times"], history["milk"]["last_qty"]), (1, "2"))
        out = self.ok("shop", "add", "milk")  # re-adding uncrosses with the remembered quantity
        self.assertEqual((out["results"][0]["status"], out["results"][0]["item"]["qty"]), ("uncrossed", "2"))
        self.ok("shop", "cross", "milk")
        out = self.ok("shop", "readd", "milk")
        self.assertEqual((out["status"], out["item"]["qty"]), ("uncrossed", "2"))
        self.ok("shop", "cross", "milk")
        self.ok("shop", "clear")
        out = self.ok("shop", "readd", "milk")  # gone from the list: back from history, last quantity
        self.assertEqual((out["status"], out["item"]["qty"]), ("added", "2"))
        self.assertEqual(Hub(self.home).household().data("shopping")["history"]["milk"]["times"], 3)  # crossed 3x

    def test_uncross_all_reuses_the_list(self):
        self.ok("shop", "add", "a1", "a2", "a3")
        self.ok("shop", "cross", "a1", "a2")
        out = self.ok("shop", "uncross", "--all")
        self.assertEqual(out["uncrossed"], 2)
        self.assertEqual(self.ok("shop", "show")["list"]["open"], 3)

    def test_moving_an_item_teaches_the_aisle(self):
        self.ok("shop", "add", "zaatar")
        out = self.ok("shop", "item", "zaatar", "--aisle", "pantry")
        self.assertEqual(out["learned_aisle"], "Pantry")
        self.ok("shop", "remove", "zaatar")
        out = self.ok("shop", "add", "Zaatar")
        self.assertEqual(out["results"][0]["item"]["aisle"], "Pantry")
        self.ok("shop", "item", "zaatar", "--aisle", "Other")  # "Other" beats the bundled guess next time too
        self.assertEqual(Hub(self.home).household().data("shopping")["overrides"]["zaatar"], "Other")
        self.err("no_such_aisle", "shop", "item", "zaatar", "--aisle", "Spices")

    def test_aisle_order_editing(self):
        self.ok("shop", "aisles", "--add", "Bulk", "--before", "Pantry")
        aisles = self.ok("shop", "aisles", "--move", "Frozen", "--after", "Beverages")["aisles"]
        self.assertLess(aisles.index("Bulk"), aisles.index("Pantry"))
        self.assertEqual(aisles.index("Frozen"), aisles.index("Beverages") + 1)
        aisles = self.ok("shop", "aisles", "--order", "Bakery,Produce")["aisles"]
        self.assertEqual(aisles[:2], ["Bakery", "Produce"])
        self.assertEqual(aisles[-1], "Other")
        self.ok("shop", "add", "milk")
        self.ok("shop", "aisles", "--delete", "Dairy")
        self.assertEqual(self.ok("shop", "show")["groups"][-1]["aisle"], "Other")
        self.ok("shop", "aisles", "--rename", "Deli", "--to", "Deli & Cheese")
        self.assertIn("Deli & Cheese", self.ok("shop", "aisles")["aisles"])

    def test_store_lists_and_share(self):
        out = self.ok("shop", "new", "--name", "Hardware", "--kind", "shopping", "--store", "Corner Hardware")
        self.assertEqual(out["list"]["kind"], "shopping")
        self.ok("shop", "add", "nails", "light bulbs", "--list", "hardware")
        show = self.ok("shop", "show", "--list", "Hardware")
        self.assertEqual([g["aisle"] for g in show["groups"]], ["Household", "Other"])  # store lists have aisles
        out = self.ok("shop", "share", "--list", "Hardware", "--file")
        self.assertIn("☐ Nails", out["text"])
        self.assertTrue(Path(out["file"]).is_file())

    def test_delete_restore_and_the_protected_grocery_list(self):
        self.ok("shop", "new", "--name", "Party", "--kind", "shopping")
        self.ok("shop", "delete", "--list", "Party")
        self.assertNotIn("Party", [x["name"] for x in self.ok("shop", "lists")["lists"]])
        self.ok("shop", "restore", "Party")
        self.assertIn("Party", [x["name"] for x in self.ok("shop", "lists")["lists"]])
        self.err("protected", "shop", "delete", "--list", "Groceries")

    def test_access_follows_the_list_kind(self):
        self.ok("shop", "new", "--name", "Pharmacy", "--kind", "shopping")
        self.ok("member", "access", "Luis", "--set", "shopping_lists=none", "--set", "grocery=view")
        lists = [x["name"] for x in self.ok("shop", "lists", "--as", "Luis")["lists"]]
        self.assertEqual(lists, ["Groceries"])
        self.err("not_authorized", "shop", "add", "milk", "--as", "Luis")
        self.err("not_found", "shop", "show", "--list", "Pharmacy", "--as", "Luis")

    def test_group_chats_with_kids_never_show_shopping_lists(self):
        self.ok("shop", "new", "--name", "Pharmacy", "--kind", "shopping")
        self.ok("who", "chat", "fam", "--type", "group", "--minors", "yes")
        self.ok("who", "link", "fam", "--participant", "@ana", "--member", "Ana")
        group = ("--chat", "fam", "--from", "@ana")
        self.assertEqual([x["name"] for x in self.ok("shop", "lists", *group)["lists"]], ["Groceries"])
        self.err("hidden_in_group", "shop", "show", "--list", "Pharmacy", *group)
        self.ok("shop", "add", "bread", *group)  # the grocery list is fine to show to everyone

    def test_two_shoppers_see_each_others_changes(self):
        self.ok("shop", "add", "milk", "eggs", "bread")
        self.ok("shop", "cross", "milk")
        self.ok("shop", "cross", "eggs", "--as", "Luis")
        out = self.ok("shop", "show", "--crossed")
        self.assertEqual({i["name"]: i["crossed_by"] for i in out["crossed"]}, {"eggs": "Luis", "milk": "Ana"})

    def test_suggest_command_uses_history_then_common_items(self):
        self.ok("shop", "add", "mangoes")
        self.ok("shop", "cross", "mangoes")
        out = self.ok("shop", "suggest", "man")
        self.assertEqual(out["suggestions"][0]["name"], "Mangoes")
        self.assertEqual(out["suggestions"][0]["from"], "history")


if __name__ == "__main__":
    unittest.main()
