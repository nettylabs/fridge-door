"""The meal plan: busy nights, leftovers, the week's grocery list and its exact updates, ideas, Today."""

from helpers import HomeTest
from fridgedoor.store import Hub


class MealPlanTest(HomeTest):
    def setUp(self):
        super().setUp()
        self.setup_family("Ana, Luis, Theo (kid)", "CA")
        self.ok("recipe", "add", "--title", "Chili", "--servings", "4", "--prep", "15", "--cook", "45",
                "--ingredient", "500 g ground beef", "--ingredient", "1 onion, chopped",
                "--ingredient", "1 (400 g) can kidney beans", "--ingredient", "salt to taste")  # fmt: skip
        self.ok("recipe", "add", "--title", "Quesadillas", "--servings", "4", "--prep", "10", "--cook", "10",
                "--ingredient", "8 tortillas", "--ingredient", "1 onion",
                "--ingredient", "1 can black beans")  # fmt: skip

    def items(self, crossed=False):
        out = self.ok("shop", "show", "--crossed")
        open_items = {i["name"]: i["qty"] for g in out["groups"] for i in g["items"]}
        if crossed:
            return open_items, {i["name"]: i["qty"] for i in out.get("crossed", [])}
        return open_items

    def test_a_long_cook_on_a_busy_night_is_refused_unless_said_so(self):
        self.ok("cal", "add", "Hockey", "--date", "wednesday", "--time", "17:30", "--end", "19:00")
        out = self.err("busy_night", "meal", "plan", "wednesday", "--recipe", "Chili")
        self.assertEqual(out["quick"], ["Quesadillas"])
        self.ok("meal", "plan", "wednesday", "--recipe", "Quesadillas")  # quick: fine
        self.ok("meal", "plan", "wednesday", "--recipe", "Chili", "--replace", "--anyway")
        nights = {n["date"]: n for n in self.ok("meal", "nights")["nights"]}
        self.assertTrue(nights["2026-10-21"]["conflict"])

    def test_week_view_text_and_leftovers(self):
        self.ok("meal", "plan", "monday", "--recipe", "Chili", "--servings", "6")
        self.ok("meal", "plan", "tuesday", "--leftovers-of", "monday")
        self.ok("meal", "plan", "friday", "--text", "Eating out")
        out = self.ok("meal", "week")
        self.assertIn("Tue 2026-10-20: Dinner: Leftover Chili from Mon", out["text"])
        today = self.ok("today", env={"FRIDGE_NOW": "2026-10-20T08:00:00"})
        self.assertIn("Leftover Chili from Mon — still good?", today["text"])
        self.assertEqual(today["text"].count("Leftover Chili"), 1)  # one line, not the meal and then the question
        self.err("not_found", "meal", "plan", "thursday", "--leftovers-of", "wednesday")

    def test_the_weeks_list_merges_meals_and_skips_the_pantry(self):
        self.ok("pantry", "set", "kidney beans", "--status", "in")
        self.ok("meal", "plan", "monday", "--recipe", "Chili")
        self.ok("meal", "plan", "wednesday", "--recipe", "Quesadillas")
        review = self.ok("meal", "to-list", "--dry-run")
        self.assertEqual([n["item"] for n in review["plan"]["pantry"]], ["kidney beans"])
        self.assertEqual([n["item"] for n in review["plan"]["check"]], ["salt"])
        self.assertEqual(self.items(), {})
        self.ok("meal", "to-list")
        self.assertEqual(self.items(), {"onion": "2", "tortillas": "8", "ground beef": "500 g", "black beans": "1 can"})

    def test_swapping_a_meal_changes_only_its_share(self):
        self.ok("meal", "plan", "monday", "--recipe", "Chili")
        self.ok("meal", "plan", "wednesday", "--recipe", "Quesadillas")
        self.ok("shop", "add", "milk x2")
        self.ok("meal", "to-list")
        out = self.ok("meal", "swap", "wednesday", "--recipe", "Chili")
        self.assertIn("took off tortillas, black beans", out["summary"])
        self.assertEqual(self.items(), {"onion": "2", "ground beef": "1 kg", "kidney beans": "2 cans", "milk": "2"})

    def test_crossed_off_items_are_never_touched(self):
        self.ok("meal", "plan", "monday", "--recipe", "Chili")
        self.ok("meal", "to-list")
        self.ok("shop", "cross", "ground beef")
        self.ok("meal", "remove", "monday")
        open_items, crossed = self.items(crossed=True)
        self.assertEqual(open_items, {})
        self.assertEqual(crossed, {"ground beef": "500 g"})
        self.ok("meal", "plan", "monday", "--recipe", "Chili")  # planned again: the bought beef isn't re-added...
        open_items, crossed = self.items(crossed=True)
        self.assertIn("ground beef", open_items)  # ...for a different meal entry it is, since that one needs its own

    def test_bought_items_stay_bought_for_the_same_meal(self):
        self.ok("meal", "plan", "monday", "--recipe", "Chili")
        self.ok("meal", "to-list")
        self.ok("shop", "cross", "ground beef")
        self.ok("meal", "plan", "thursday", "--text", "Pizza night")  # any change re-syncs the week
        self.ok("meal", "to-list")
        open_items, crossed = self.items(crossed=True)
        self.assertNotIn("ground beef", open_items)
        self.assertEqual(crossed, {"ground beef": "500 g"})

    def test_hand_added_items_stay_when_meals_go(self):
        self.ok("shop", "add", "onion")
        self.ok("meal", "plan", "monday", "--recipe", "Chili")
        self.ok("meal", "to-list")
        self.ok("meal", "remove", "monday")
        self.assertEqual(self.items(), {"onion": None})

    def test_removing_a_meal_clears_its_leftovers_and_swaps_carry_them(self):
        self.ok("meal", "plan", "monday", "--recipe", "Chili")
        self.ok("meal", "plan", "tuesday", "--leftovers-of", "monday")
        self.ok("meal", "swap", "monday", "--recipe", "Quesadillas")
        self.assertIn("Leftover Quesadillas from Mon", self.ok("meal", "week")["text"])
        out = self.ok("meal", "remove", "monday")
        self.assertIn("Also cleared its leftovers", out["summary"])
        self.assertIn("Tue 2026-10-20: nothing planned", self.ok("meal", "week")["text"])

    def test_ideas_prefer_what_the_pantry_covers_and_quick_ones_on_busy_nights(self):
        self.ok("pantry", "set", "tortillas, onion, black beans", "--status", "in")
        ideas = self.ok("meal", "ideas")["ideas"]
        self.assertEqual(ideas[0]["title"], "Quesadillas")
        self.assertIn("you have 3 of 3", ideas[0]["why"])

    def test_ideas_leave_out_the_pantry_for_people_who_cannot_see_it(self):
        self.ok("pantry", "set", "tortillas, onion, black beans", "--status", "in")
        self.ok("member", "access", "Luis", "--set", "grocery=none")
        ideas = self.ok("meal", "ideas", "--as", "Luis")["ideas"]
        self.assertFalse(any("you have" in idea["why"] for idea in ideas))

    def test_meals_show_on_the_calendar_and_in_today(self):
        self.ok("meal", "plan", "monday", "--recipe", "Chili")
        week = self.ok("cal", "week", "--layers", "meals")
        self.assertIn("Dinner: Chili", [o["title"] for o in week["occurrences"]])
        self.err("bad_layer", "cal", "week", "--layers", "weather")
        today = self.ok("today")
        self.assertEqual(today["sections"]["dinner"]["lines"], ["Chili (serves 4)"])

    def test_the_weeks_list_needs_everyone_in_the_chat_to_see_recipes(self):
        self.ok("meal", "plan", "monday", "--recipe", "Chili")
        self.ok("member", "access", "Luis", "--set", "recipes=none")
        self.ok("who", "chat", "pair", "--type", "group", "--minors", "no")
        self.ok("who", "link", "pair", "--participant", "@ana", "--member", "Ana")
        self.ok("who", "link", "pair", "--participant", "@luis", "--member", "Luis", "--owner-confirmed", "yes")
        self.err("hidden_in_group", "meal", "to-list", "--chat", "pair", "--from", "@ana")

    def test_meal_plan_access(self):
        self.ok("member", "access", "Luis", "--set", "meal_plan=view")
        self.ok("meal", "week", "--as", "Luis")
        self.err("not_authorized", "meal", "plan", "monday", "--text", "Soup", "--as", "Luis")
        self.assertEqual(Hub(self.home).household().data("mealplan")["plan"], {})
