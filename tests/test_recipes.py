"""Recipes: import from saved pages, adding by hand or photo, scaling, cook mode, pantry and the grocery review."""

import json
import unittest

from helpers import HomeTest
from fridgedoor import importer
from fridgedoor.store import Hub
from fridgedoor.util import ToolError

PAGE = """<html><head><title>Weeknight Chili</title>
<script type="application/ld+json">
{"@context": "https://schema.org", "@graph": [
  {"@type": "WebPage", "name": "Weeknight Chili | Example Kitchen"},
  {"@type": ["Recipe", "NewsArticle"], "name": "Weeknight Chili &amp; Rice",
   "recipeYield": ["4", "4 servings"], "prepTime": "PT15M", "cookTime": "PT45M", "totalTime": "PT1H",
   "recipeIngredient": ["500 g ground beef", "1 onion, chopped", "2 cloves garlic", "1 (400 g) can kidney beans",
                        "<b>salt</b> to taste"],
   "recipeInstructions": [
     {"@type": "HowToSection", "name": "Chili", "itemListElement": [
        {"@type": "HowToStep", "text": "Brown the beef."}, {"@type": "HowToStep", "text": "Add the rest."}]},
     {"@type": "HowToStep", "text": "Serve with rice."}],
   "keywords": "dinner, easy, Mexican", "recipeCategory": "Main course",
   "image": {"@type": "ImageObject", "url": "https://example.com/chili.jpg"},
   "url": "https://example.com/chili"}
]}
</script></head><body>...</body></html>"""


class ImporterTest(unittest.TestCase):
    def test_graph_sections_times_yields_and_entities(self):
        r = importer.from_html(PAGE)
        self.assertEqual(r["title"], "Weeknight Chili & Rice")
        self.assertEqual((r["servings"], r["prep_min"], r["cook_min"], r["total_min"]), (4, 15, 45, 60))
        self.assertEqual(r["ingredients"][-1], "salt to taste")  # tags stripped
        self.assertEqual(r["steps"], ["Chili: Brown the beef.", "Add the rest.", "Serve with rice."])
        self.assertEqual(r["tags"], ["dinner", "easy", "mexican", "main course"])
        self.assertNotIn("image_url", r)  # the page's image link isn't kept (never shown; can carry tracking)
        self.assertEqual(r["source_url"], "https://example.com/chili")

    def test_plain_recipe_with_string_instructions(self):
        page = ('<script type="application/ld+json">{"@type": "Recipe", "name": "Toast", "recipeYield": "Serves 2",'
                '"recipeIngredient": ["2 slices bread"], "recipeInstructions": "Toast the bread.\\nButter it."}'
                "</script>")  # fmt: skip
        r = importer.from_html(page, url="https://example.org/toast")
        self.assertEqual((r["servings"], r["steps"], r["source_url"]), (2, ["Toast the bread.", "Butter it."],
                                                                         "https://example.org/toast"))  # fmt: skip

    def test_durations(self):
        self.assertEqual(importer.minutes("PT1H30M"), 90)
        self.assertEqual(importer.minutes("P0DT0H45M"), 45)
        self.assertEqual(importer.minutes("PT90M"), 90)
        self.assertIsNone(importer.minutes("half an hour"))
        self.assertIsNone(importer.minutes(None))

    def test_pages_without_recipe_data_explain_what_to_do(self):
        with self.assertRaises(ToolError) as cm:
            importer.from_html("<html><script type='application/ld+json'>{\"@type\": \"WebPage\"}</script></html>")
        self.assertEqual(cm.exception.code, "no_recipe_data")
        self.assertIn("recipe add", cm.exception.hint)
        with self.assertRaises(ToolError):
            importer.from_html("<script type='application/ld+json'>{not json</script>")


class RecipeCommandsTest(HomeTest):
    def setUp(self):
        super().setUp()
        self.setup_family("Ana, Luis, Theo (kid)", "CA")

    def add_chili(self):
        return self.ok("recipe", "add", "--title", "Chili", "--servings", "4", "--prep", "15", "--cook", "45",
                       "--ingredient", "500 g ground beef", "--ingredient", "1 onion, chopped",
                       "--ingredient", "2 cups chopped tomatoes", "--ingredient", "1 tbsp chili powder",
                       "--ingredient", "salt to taste", "--step", "Brown the beef", "--step", "Simmer",
                       "--tag", "Dinner")  # fmt: skip

    def test_import_a_saved_page(self):
        page = self.home / "chili.html"
        page.write_text(PAGE, encoding="utf-8")
        out = self.ok("recipe", "import", str(page))
        self.assertEqual(out["recipe"]["servings"], 4)
        self.assertEqual(out["recipe"]["ingredients"][0], "500 g ground beef")
        self.err("exists", "recipe", "import", str(page))
        self.ok("recipe", "import", str(page), "--again")
        self.err("no_file", "recipe", "import", str(self.home / "missing.html"))

    def test_add_from_a_photo_lists_what_to_check(self):
        spec = {"title": "Gran's scones", "servings": 8, "ingredients": ["2 cups flour", "1/2 cup butter"],
                "steps": ["Rub in the butter", "Bake 12 minutes"], "unclear": ["oven temperature smudged"]}  # fmt: skip
        out = self.ok("recipe", "add", "--spec", json.dumps(spec), "--source", "photo")
        self.assertIn("oven temperature smudged", out["ask"])
        out = self.ok("recipe", "edit", "Gran's scones", "--checked")
        self.assertEqual(out["recipe"]["unclear"], [])

    def test_show_scales_exactly(self):
        self.add_chili()
        out = self.ok("recipe", "show", "Chili", "--servings", "6")
        self.assertEqual(out["recipe"]["ingredients"][:3], ["750 g ground beef", "1 1/2 onions (chopped)",
                                                            "3 cups tomatoes (chopped)"])  # fmt: skip
        self.ok("recipe", "add", "--title", "Toast", "--ingredient", "2 slices bread")
        self.err("no_servings", "recipe", "show", "Toast", "--servings", "4")

    def test_edit_ingredients_and_tags(self):
        self.add_chili()
        out = self.ok("recipe", "edit", "Chili", "--set-ingredient", "4=2 tsp cumin", "--remove-ingredient", "5",
                      "--untag", "dinner", "--tag", "spicy")  # fmt: skip
        self.assertEqual(out["recipe"]["ingredients"][-1], "2 tsp cumin")
        self.assertEqual(out["recipe"]["tags"], ["spicy"])
        self.err("usage", "recipe", "edit", "Chili", "--set-ingredient", "9=salt")

    def test_to_list_review_pantry_check_at_home_and_merge(self):
        self.add_chili()
        self.ok("pantry", "set", "chili powder", "--status", "in", "--staple")
        self.ok("pantry", "set", "cumin", "--staple")  # a staple with no status: check at home
        self.ok("shop", "add", "onion x2")
        review = self.ok("recipe", "to-list", "Chili", "--dry-run")
        plan = review["plan"]
        self.assertEqual([n["item"] for n in plan["add"]], ["ground beef", "tomatoes"])
        self.assertEqual([n["item"] for n in plan["covered"]], ["onion"])  # added by hand: its amount is theirs
        self.assertEqual([n["item"] for n in plan["pantry"]], ["chili powder"])
        self.assertEqual([n["item"] for n in plan["check"]], ["salt"])  # "to taste": check at home
        self.assertEqual(self.ok("shop", "show")["list"]["open"], 1)  # a dry run changes nothing
        self.ok("recipe", "to-list", "Chili", "--servings", "8", "--skip", "tomatoes")
        items = {i["name"]: i["qty"] for g in self.ok("shop", "show")["groups"] for i in g["items"]}
        self.assertEqual(items, {"onion": "2", "ground beef": "1 kg"})  # the typed "x2" is left as it was

    def test_buying_marks_the_pantry_in(self):
        self.ok("pantry", "set", "rice", "--status", "out", "--staple")
        self.ok("shop", "add", "rice")
        self.ok("shop", "cross", "rice")
        rows = {r["item"]: r["status"] for r in self.ok("pantry", "show")["pantry"]}
        self.assertEqual(rows["rice"], "in")

    def test_old_pantry_staples_need_checking_again(self):
        self.add_chili()
        self.ok("pantry", "set", "chili powder", "--status", "in", "--staple")
        later = {"FRIDGE_NOW": "2026-12-01T08:00:00"}
        plan = self.ok("recipe", "to-list", "Chili", "--dry-run", env=later)["plan"]
        self.assertIn("chili powder", [n["item"] for n in plan["check"]])

    def test_cook_mode_step_by_step(self):
        self.add_chili()
        out = self.ok("recipe", "cook", "Chili", "--servings", "2")
        self.assertEqual(out["step"], 0)
        self.assertIn("250 g ground beef", out["ingredients"])
        self.assertEqual(self.ok("recipe", "cook", "--next")["text"], "Step 1 of 2: Brown the beef")
        self.assertIn("last step", self.ok("recipe", "cook", "--next")["text"])
        self.assertEqual(self.ok("recipe", "cook", "--back")["step"], 1)
        self.ok("recipe", "cook", "--stop", "--done")
        self.err("not_cooking", "recipe", "cook", "--next")
        data = Hub(self.home).household().data("recipes")["recipes"][0]
        self.assertEqual(data["cooked"], ["2026-10-19"])

    def test_cook_mode_checks_access_every_step(self):
        self.add_chili()
        self.ok("recipe", "cook", "Chili", "--as", "Luis")
        self.ok("member", "access", "Luis", "--set", "recipes=none")
        self.err("not_authorized", "recipe", "cook", "--next", "--as", "Luis")
        self.ok("member", "access", "Luis", "--set", "recipes=view")
        self.err("not_authorized", "recipe", "cook", "--stop", "--done", "--as", "Luis")

    def test_the_pantry_stays_hidden_from_people_without_grocery_access(self):
        self.add_chili()
        self.ok("pantry", "set", "chili powder", "--status", "in")
        self.ok("shop", "new", "--name", "Market", "--kind", "shopping")
        self.ok("member", "access", "Luis", "--set", "grocery=none")
        self.err("not_authorized", "pantry", "show", "--as", "Luis")
        plan = self.ok("recipe", "to-list", "Chili", "--list", "Market", "--dry-run", "--as", "Luis")["plan"]
        self.assertEqual(plan["pantry"], [])  # can't learn what's in the pantry this way
        self.assertIn("chili powder", [n["item"] for n in plan["check"]])  # a spoonful: checked at home

    def test_list_search_and_quick(self):
        self.add_chili()
        self.ok("recipe", "add", "--title", "Omelette", "--prep", "5", "--cook", "5", "--ingredient", "3 eggs")
        self.assertEqual([r["title"] for r in self.ok("recipe", "list", "--quick")["recipes"]], ["Omelette"])
        self.assertEqual([r["title"] for r in self.ok("recipe", "list", "--search", "beef")["recipes"]], ["Chili"])
        self.assertEqual([r["title"] for r in self.ok("recipe", "list", "--tag", "dinner")["recipes"]], ["Chili"])

    def test_access(self):
        self.add_chili()
        self.ok("member", "access", "Luis", "--set", "recipes=view")
        self.ok("recipe", "show", "Chili", "--as", "Luis")
        self.err("not_authorized", "recipe", "edit", "Chili", "--servings", "2", "--as", "Luis")
        self.ok("member", "access", "Luis", "--set", "recipes=none")
        self.err("not_authorized", "recipe", "list", "--as", "Luis")


if __name__ == "__main__":
    unittest.main()
