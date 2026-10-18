"""Ingredient lines: parsing (fractions, ranges, to taste), units, merging within systems, scaling."""

import unittest
from fractions import Fraction as F

import helpers  # noqa: F401
from fridgedoor import ingredients as I
from fridgedoor import units


def p(line):
    return I.parse(line)


def merged(*lines):
    return {g["item"]: g["quantity"] for g in I.merge([p(line) for line in lines])}


class ParseTest(unittest.TestCase):
    def check(self, line, amount=None, unit=None, item=None, note=None, maximum=None):
        got = p(line)
        self.assertEqual((got["amount"], got["max"], got["unit"], got["item"], got["note"]),
                         (amount, maximum, unit, item, note), line)  # fmt: skip

    def test_fractions_mixed_numbers_and_unicode(self):
        self.check("1 1/2 cups flour, sifted", F(3, 2), "cup", "flour", "sifted")
        self.check("1½ cups milk", F(3, 2), "cup", "milk")
        self.check("1 ½ cups milk", F(3, 2), "cup", "milk")
        self.check("½ tsp salt", F(1, 2), "tsp", "salt")
        self.check("¾ c. sugar", F(3, 4), "cup", "sugar")
        self.check(".5 cup water", F(1, 2), "cup", "water")
        self.check("1.5kg chicken thighs", F(3, 2), "kg", "chicken thighs")

    def test_ranges_and_words(self):
        self.check("2-3 cloves garlic, minced", F(2), "clove", "garlic", "minced", F(3))
        self.check("2–3 cloves garlic", F(2), "clove", "garlic", None, F(3))
        self.check("2 to 3 tbsp olive oil", F(2), "tbsp", "olive oil", None, F(3))
        self.check("one or two onions", F(1), None, "onions", None, F(2))
        self.check("a pinch of salt", F(1), "pinch", "salt")
        self.check("a dozen eggs", F(12), None, "eggs")
        self.check("half a dozen eggs", F(6), None, "eggs")
        self.check("an apple", F(1), None, "apple")
        self.check("apple", None, None, "apple")  # "a" in "apple" is not a number

    def test_units_and_case_sensitive_spoons(self):
        self.check("1 T sugar", F(1), "tbsp", "sugar")
        self.check("1 t vanilla", F(1), "tsp", "vanilla")
        self.check("2 Tbsp. butter", F(2), "tbsp", "butter")
        self.check("200g butter, softened", F(200), "g", "butter", "softened")
        self.check("200 ml double cream", F(200), "ml", "double cream")
        self.check("8 oz cream cheese", F(8), "oz", "cream cheese")
        self.check("2 fl oz rum", F(2), "fl oz", "rum")
        self.check("1 lb ground beef", F(1), "lb", "ground beef")
        self.check("2 cups of flour", F(2), "cup", "flour")
        self.check("3 sprigs thyme", F(3), "sprig", "thyme")
        self.check("1 stick butter", F(1), "stick", "butter")

    def test_package_sizes_sizes_and_prep_words_become_notes(self):
        self.check("1 (14 oz) can diced tomatoes", F(1), "can", "tomatoes", "14 oz, diced")
        self.check("2 x 400g tins chopped tomatoes", F(2), "can", "tomatoes", "400g, chopped")  # a tin is a can
        self.check("2 garlic cloves, minced", F(2), "clove", "garlic", "minced")
        self.check("1 can (400g) chickpeas, drained", F(1), "can", "chickpeas", "400g, drained")
        self.check("½ cup (120 ml) double cream", F(1, 2), "cup", "double cream", "120 ml")
        self.check("3 large eggs", F(3), None, "eggs", "large")
        self.check("1/4 cup chopped parsley", F(1, 4), "cup", "parsley", "chopped")

    def test_to_taste_optional_and_juice_of(self):
        salt = p("salt to taste")
        self.assertEqual((salt["amount"], salt["item"], salt["to_taste"]), (None, "salt", True))
        self.assertTrue(p("Black pepper, as needed")["to_taste"])
        self.assertTrue(p("Optional: chilli flakes")["optional"])
        self.assertTrue(p("2 tbsp coriander (optional)")["optional"])
        juice = p("Juice of 1 lemon")
        self.assertEqual((juice["amount"], juice["item"], juice["note"]), (F(1), "lemon", "juice"))
        self.assertEqual(p("zest of an orange")["item"], "orange")

    def test_records_round_trip_as_text(self):
        rec = I.to_record(p("1 1/2 cups flour"))
        self.assertEqual(rec["amount"], "3/2")
        self.assertEqual(I.from_record(rec)["amount"], F(3, 2))


class MergeTest(unittest.TestCase):
    def test_same_system_adds_up_in_the_best_unit(self):
        self.assertEqual(merged("2 cups flour", "1 cup flour"), {"flour": "3 cups"})
        self.assertEqual(merged("3 tsp sugar"), {"sugar": "1 tbsp"})
        self.assertEqual(merged("1 tbsp sugar", "1 tsp sugar"), {"sugar": "4 tsp"})
        self.assertEqual(merged("1/2 cup milk", "1/4 cup milk", "2 tbsp milk"), {"milk": "7/8 cup"})
        self.assertEqual(merged("12 tbsp butter"), {"butter": "3/4 cup"})
        self.assertEqual(merged("5 tbsp butter"), {"butter": "5 tbsp"})
        self.assertEqual(merged("500 g mince", "750 g mince"), {"mince": "1.25 kg"})
        self.assertEqual(merged("1 l milk", "500 ml milk"), {"milk": "1.5 l"})
        self.assertEqual(merged("8 oz cream cheese", "8 oz cream cheese"), {"cream cheese": "1 lb"})

    def test_never_between_metric_and_us_or_weight_and_volume(self):
        self.assertEqual(merged("2 cups flour", "200 g flour"), {"flour": "2 cups + 200 g"})
        self.assertEqual(merged("1 cup sugar", "100 g sugar", "2 oz sugar"), {"sugar": "1 cup + 100 g + 2 oz"})
        self.assertEqual(merged("1 can tomatoes", "200 g tomatoes"), {"tomatoes": "1 can + 200 g"})
        self.assertEqual(merged("2 fl oz rum", "2 oz rum"), {"rum": "1/4 cup + 2 oz"})  # volume and weight apart

    def test_counts_ranges_and_to_taste(self):
        self.assertEqual(merged("3 eggs", "2 large eggs"), {"eggs": "5"})
        self.assertEqual(merged("2-3 cloves garlic", "1 clove garlic"), {"garlic": "3-4 cloves"})
        groups = I.merge([p("salt to taste"), p("Salt, to taste")])
        self.assertEqual((len(groups), groups[0]["quantity"], groups[0]["to_taste"]), (1, "", True))
        self.assertEqual(merged("2 cloves garlic", "1 head garlic"), {"garlic": "2 cloves + 1 head"})

    def test_plural_and_case_still_merge(self):
        self.assertEqual(merged("2 Tomatoes", "1 tomato"), {"Tomatoes": "3"})


class ScaleTest(unittest.TestCase):
    def test_scaling_is_exact(self):
        self.assertEqual(I.describe(I.scale(p("1/3 cup oil"), F(3))), "1 cup oil")
        self.assertEqual(I.describe(I.scale(p("250 g pasta"), F(6, 4))), "375 g pasta")
        self.assertEqual(I.describe(I.scale(p("3 eggs"), F(1, 2))), "1 1/2 eggs")
        self.assertEqual(I.describe(I.scale(p("2-3 cloves garlic"), F(2))), "4-6 cloves garlic")
        self.assertEqual(I.describe(I.scale(p("salt to taste"), F(2))), "salt (to taste)")


class UnitsTest(unittest.TestCase):
    def test_fraction_text_rounds_to_measurable_amounts(self):
        self.assertEqual(units.fraction_text(F(3, 2)), "1 1/2")
        self.assertEqual(units.fraction_text(F(1, 3)), "1/3")
        self.assertEqual(units.fraction_text(F(5, 16)), "1/3")  # 0.3125 -> nearest of halves/thirds/quarters/eighths
        self.assertEqual(units.fraction_text(F(4)), "4")

    def test_best_unit(self):
        self.assertEqual(units.best_unit(F(24), "volume", "us"), (F(1, 2), "cup"))
        self.assertEqual(units.best_unit(F(6), "volume", "us"), (F(2), "tbsp"))
        self.assertEqual(units.best_unit(F(2), "volume", "us"), (F(2), "tsp"))
        self.assertEqual(units.best_unit(F(24), "weight", "us"), (F(3, 2), "lb"))
        self.assertEqual(units.best_unit(F(1500), "weight", "metric"), (F(3, 2), "kg"))

    def test_amount_text(self):
        self.assertEqual(units.amount_text(F(3, 2), "cup"), "1 1/2 cups")
        self.assertEqual(units.amount_text(F(1), "cup"), "1 cup")
        self.assertEqual(units.amount_text(F(2), "clove", F(3)), "2-3 cloves")
        self.assertEqual(units.amount_text(F(3, 2), "kg"), "1.5 kg")
        self.assertEqual(units.amount_text(None, "cup"), "")


if __name__ == "__main__":
    unittest.main()
