"""Members: owner-only changes, the last owner, access levels, colours, minimal kid profiles, erasing."""

import unittest

from helpers import HomeTest
from fridgedoor import members
from fridgedoor.store import Hub
from fridgedoor.util import ToolError


class MemberRulesTest(unittest.TestCase):
    def test_kid_and_teen_names_are_first_names_or_nicknames(self):
        self.assertEqual(members.check_name([], "  Mia ", "kid"), "Mia")
        self.assertEqual(members.check_name([], "Mary-Jane", "kid"), "Mary-Jane")  # a double name, hyphenated
        for bad in ("Mia Garcia", "Mia Garcia Lopez", "Little Joe", "Mia 9", "mia@example.com"):
            with self.assertRaises(ToolError) as cm:
                members.check_name([], bad, "kid")
            self.assertEqual(cm.exception.code, "minor_details")
        self.assertEqual(members.check_name([], "Rosa Maria Garcia", "adult"), "Rosa Maria Garcia")

    def test_names_are_unique_ignoring_case_and_accents(self):
        roster = [{"id": "M1", "name": "Zoë"}]
        with self.assertRaises(ToolError) as cm:
            members.check_name(roster, "zoe", "adult")
        self.assertEqual(cm.exception.code, "already_member")

    def test_palette_colours(self):
        self.assertEqual(members.color_hex("teal"), "#2E9E8F")
        self.assertEqual(members.color_hex("#2e9e8f"), "#2E9E8F")
        self.assertEqual(members.color_name("#2E9E8F"), "teal")
        self.assertEqual(members.next_color([{"color": "#D9534F"}]), "#E67E22")
        with self.assertRaises(ToolError):
            members.color_hex("sparkly")


class MemberCommandsTest(HomeTest):
    def setUp(self):
        super().setUp()
        self.setup_family()

    def test_add_is_owner_only_and_adults_get_a_personal_list(self):
        self.err("not_authorized", "member", "add", "--name", "Rosa", "--as", "Luis")
        out = self.ok("member", "add", "--name", "Grandma Rosa")
        self.assertEqual(out["member"]["role"], "adult")
        self.assertEqual(out["lists"], ["My Tasks"])
        out = self.ok("member", "add", "--name", "Mia", "--role", "kid", "--color", "pink")
        self.assertEqual((out["member"]["stars"], out["member"]["color_name"]), (0, "pink"))
        self.assertEqual(out["lists"], [])
        self.assertIn("take part through the adults", out["summary"])

    def test_kid_profiles_hold_only_a_first_name_colour_and_stars(self):
        self.err("minor_details", "member", "add", "--name", "Mia Garcia Lopez", "--role", "kid")
        kid = Hub(self.home).household().member("M3")
        self.assertEqual(set(kid), {"id", "name", "role", "access", "color", "joined_at", "stars"})

    def test_members_edit_themselves_owner_edits_anyone(self):
        out = self.ok("member", "edit", "Luis", "--color", "indigo", "--as", "Luis")
        self.assertEqual(out["member"]["color_name"], "indigo")
        self.err("not_authorized", "member", "edit", "Ana", "--color", "red", "--as", "Luis")
        self.ok("member", "edit", "Sofia", "--name", "Sofi")
        self.err("minor_cannot_chat", "member", "edit", "Sofi", "--quiet-hours", "20:00-07:00")

    def test_quiet_hours_and_today_sections(self):
        out = self.ok("member", "edit", "Luis", "--quiet-hours", "22:30-06:00", "--today-sections", "tasks, events",
                      "--as", "Luis")  # fmt: skip
        self.assertEqual(out["member"]["quiet_hours"], {"start": "22:30", "end": "06:00"})
        self.assertEqual(out["member"]["today_sections"], ["events", "tasks"])
        self.err("bad_section", "member", "edit", "Luis", "--today-sections", "weather", "--as", "Luis")
        out = self.ok("member", "edit", "Luis", "--quiet-hours", "none", "--as", "Luis")
        self.assertIsNone(out["member"]["quiet_hours"])

    def test_roles_and_access_are_owner_only(self):
        self.err("not_authorized", "member", "access", "Sofia", "--set", "grocery=edit", "--as", "Luis")
        out = self.ok("member", "access", "Sofia", "--set", "grocery=edit", "--set", "calendar=view")
        self.assertEqual((out["member"]["access"]["grocery"], out["member"]["access"]["calendar"]), ("edit", "view"))
        out = self.ok("member", "access", "Sofia", "--reset")
        self.assertEqual(out["member"]["access"]["grocery"], "view")
        self.err("bad_permissions", "member", "access", "Sofia", "--set", "grocery=admin")
        self.err("bad_permissions", "member", "access", "Sofia", "--set", "garage=edit")
        self.err("bad_permissions", "member", "access", "Sofia", "--set", "grocery")

    def test_a_new_role_resets_access_to_its_preset(self):
        out = self.confirmed("member", "access", "Mateo", "--role", "adult", words="yes, he turned 18")
        self.assertEqual(out["member"]["access"]["budget"], "edit")
        self.assertEqual(out["lists"], ["My Tasks"])  # now an adult: gets a personal list
        out = self.ok("member", "access", "Luis", "--role", "teen")
        self.assertEqual(out["member"]["access"]["budget"], "none")
        self.assertEqual(out["member"]["stars"], 0)

    def test_the_last_owner_cannot_be_demoted_or_removed(self):
        self.err("last_owner", "member", "access", "Ana", "--role", "adult")
        self.err("last_owner", "member", "remove", "Ana", "--owner-confirmed", "yes")
        self.ok("member", "access", "Luis", "--role", "owner")
        self.ok("member", "access", "Ana", "--role", "adult")  # fine now: Luis is an owner
        self.err("not_authorized", "member", "access", "Luis", "--role", "adult")  # Ana isn't an owner any more
        self.err("last_owner", "member", "access", "Luis", "--role", "adult", "--as", "Luis")

    def test_remove_asks_the_owner_then_erases(self):
        out = self.err("needs_owner", "member", "remove", "Luis")
        self.assertIn("Remove Luis", out["ask_owner"])
        hh = Hub(self.home).household()
        personal = [lst["id"] for lst in hh.data("todos")["lists"] if lst.get("owner") == "M2"]
        self.assertEqual(len(personal), 1)
        out = self.confirmed("member", "remove", "Luis", words="yes, remove Luis")
        self.assertIn("deleted their personal list (0 tasks)", out["changes"])
        hh = Hub(self.home).household()
        self.assertIsNone(hh.member("M2"))
        self.assertEqual(hh.member_name("M2"), "Former member")
        self.assertFalse([lst for lst in hh.data("todos")["lists"] if lst.get("owner") == "M2"])
        self.err("not_found", "member", "show", "Luis")

    def test_stars_are_for_kids_and_given_by_adults(self):
        out = self.ok("member", "stars", "Sofia", "--add", "2")
        self.assertEqual(out["stars"], 2)
        out = self.ok("member", "stars", "Sofia", "--add", "-5", "--as", "Luis")
        self.assertEqual(out["stars"], 0)  # never below zero
        self.err("not_a_kid", "member", "stars", "Luis", "--add", "1")
        listing = self.ok("member", "stars")
        self.assertEqual([s["name"] for s in listing["stars"]], ["Sofia", "Mateo"])

    def test_names_and_ids_both_find_members(self):
        self.assertEqual(self.ok("member", "show", "m2")["member"]["name"], "Luis")
        self.assertEqual(self.ok("member", "show", "lu")["member"]["name"], "Luis")
        self.ok("member", "add", "--name", "Lucia")
        out = self.err("ambiguous", "member", "show", "lu")
        self.assertEqual(len(out["candidates"]), 2)


if __name__ == "__main__":
    unittest.main()
