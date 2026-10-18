"""Access rules: presets, levels, module mapping and what a group chat may show."""

import unittest

import helpers  # noqa: F401  (puts the toolkit on sys.path)
from fridgedoor import access
from fridgedoor.access import Viewer
from fridgedoor.util import ToolError


def member(mid, role, **levels):
    return {"id": mid, "name": mid, "role": role, "access": dict(access.preset(role), **levels)}


class PresetTest(unittest.TestCase):
    def test_presets_are_exactly_the_original_role_table(self):
        everything = {m: "edit" for m in access.MODULES}
        self.assertEqual(access.PRESETS["owner"], everything)
        self.assertEqual(access.PRESETS["adult"], everything)
        self.assertEqual(
            access.PRESETS["teen"],
            {"calendar": "view", "todos": "edit", "shopping_lists": "edit", "grocery": "edit", "recipes": "view",
             "meal_plan": "view", "notes": "view", "budget": "none"},
        )  # fmt: skip
        self.assertEqual(
            access.PRESETS["kid"],
            {"calendar": "none", "todos": "edit", "shopping_lists": "none", "grocery": "view", "recipes": "none",
             "meal_plan": "none", "notes": "none", "budget": "none"},
        )  # fmt: skip

    def test_eight_modules_and_level_order(self):
        self.assertEqual(len(access.MODULES), 8)
        self.assertEqual(set(access.MODULE_LABELS), set(access.MODULES))
        self.assertEqual(access.LEVELS, ("none", "view", "edit"))

    def test_can_compares_levels_and_treats_missing_as_none(self):
        kid = member("K", "kid")
        self.assertTrue(access.can(kid, "grocery", "view"))
        self.assertFalse(access.can(kid, "grocery", "edit"))
        self.assertTrue(access.can(kid, "todos", "edit"))
        broken = {"id": "B", "name": "B", "role": "adult", "access": {"calendar": "edit"}}
        self.assertFalse(access.can(broken, "budget", "view"))
        self.assertTrue(access.can(broken, "budget", "none"))

    def test_kid_sees_grocery_lists_but_not_shopping_lists(self):
        kid = member("K", "kid")
        self.assertEqual(access.LIST_KIND_MODULE["grocery"], "grocery")
        self.assertEqual(access.LIST_KIND_MODULE["shopping"], "shopping_lists")
        self.assertTrue(access.can(kid, access.LIST_KIND_MODULE["grocery"], "view"))
        self.assertFalse(access.can(kid, access.LIST_KIND_MODULE["shopping"], "view"))

    def test_validate_access_needs_exactly_eight_valid_modules(self):
        good = access.preset("teen")
        self.assertEqual(access.validate_access(good), good)
        for bad in ({}, dict(good, budget="admin"), dict(good, garage="edit"), {k: good[k] for k in list(good)[:7]}):
            with self.assertRaises(ToolError) as cm:
                access.validate_access(bad)
            self.assertEqual(cm.exception.code, "bad_permissions")

    def test_module_aliases(self):
        self.assertEqual(access.module_name("groceries"), "grocery")
        self.assertEqual(access.module_name("Meal plan"), "meal_plan")
        self.assertEqual(access.module_name("chores"), "todos")
        with self.assertRaises(ToolError):
            access.module_name("garage")


class ViewerTest(unittest.TestCase):
    def setUp(self):
        self.ana = member("M1", "owner")
        self.luis = member("M2", "adult", budget="none")

    def test_direct_chat_sees_what_the_member_sees(self):
        viewer = Viewer(self.luis)
        self.assertTrue(viewer.sees("calendar"))
        self.assertFalse(viewer.sees("budget"))
        self.assertTrue(viewer.sees_private_of("M2"))
        self.assertFalse(viewer.sees_private_of("M1"))

    def test_group_shows_only_what_everyone_present_may_see(self):
        viewer = Viewer(self.ana, [self.ana, self.luis], group=True)
        self.assertTrue(viewer.can_act("budget", "edit"))  # Ana may still change it...
        self.assertFalse(viewer.sees("budget"))  # ...but the group reply can't show it
        with self.assertRaises(ToolError) as cm:
            viewer.require_sees("budget")
        self.assertEqual(cm.exception.code, "hidden_in_group")
        self.assertFalse(viewer.sees_private_of("M1"))

    def test_private_things_never_show_in_a_group_even_with_one_linked_member(self):
        viewer = Viewer(self.ana, [self.ana], group=True)
        self.assertEqual(viewer.audience_ids(), {"M1"})
        self.assertFalse(viewer.sees_private_of("M1"))

    def test_selected_members_need_everyone_present_selected(self):
        viewer = Viewer(self.ana, [self.ana, self.luis], group=True)
        self.assertTrue(viewer.sees_selected(["M1", "M2"]))
        self.assertFalse(viewer.sees_selected(["M1"]))

    def test_minors_present_means_kid_level(self):
        viewer = Viewer(self.ana, [self.ana], group=True, minors_present=True)
        self.assertEqual(len(viewer.audience), 2)
        self.assertTrue(viewer.sees("grocery"))
        for module in ("calendar", "shopping_lists", "recipes", "meal_plan", "notes", "budget"):
            self.assertFalse(viewer.sees(module), module)
        self.assertFalse(viewer.sees_selected(["M1"]))

    def test_require_reports_the_level_and_how_to_change_it(self):
        viewer = Viewer(self.luis)
        with self.assertRaises(ToolError) as cm:
            viewer.require("budget", "view", "see the budget")
        self.assertEqual(cm.exception.code, "not_authorized")
        self.assertIn("budget=view", cm.exception.hint)
        with self.assertRaises(ToolError):
            viewer.require_owner("add members")


if __name__ == "__main__":
    unittest.main()
