"""Who's talking: direct-chat speakers, adult-only chat links, minors, and group audiences."""

from helpers import HomeTest
from fridgedoor.store import Hub


class WhoTest(HomeTest):
    def setUp(self):
        super().setUp()
        self.setup_family()
        self.ok("who", "chat", "family", "--type", "group", "--minors", "yes")

    def test_direct_chat_defaults_to_the_person_who_set_it_up(self):
        out = self.ok("who", "am-i")
        self.assertEqual(out["member"]["name"], "Ana")
        self.assertFalse(out["group"])
        self.assertEqual(out["audience"], ["Ana"])

    def test_as_works_before_or_after_the_command(self):
        self.assertEqual(self.ok("--as", "Luis", "who", "am-i")["member"]["name"], "Luis")
        self.assertEqual(self.ok("who", "am-i", "--as", "Luis")["member"]["name"], "Luis")
        self.assertEqual(self.ok("who", "--as", "Luis", "am-i")["member"]["name"], "Luis")

    def test_kids_and_teens_never_act_through_the_agent(self):
        out = self.err("minor_cannot_chat", "who", "am-i", "--as", "Sofia")
        self.assertIn("--by Sofia", out["hint"])
        self.err("minor_cannot_chat", "who", "am-i", "--as", "Mateo")

    def test_group_chats_must_say_whether_minors_are_present(self):
        out = self.err("needs_owner", "who", "chat", "other", "--type", "group")
        self.assertIn("under 18", out["ask_owner"])

    def test_linking_an_adult_asks_the_owner_once_to_confirm_18_plus(self):
        out = self.err("needs_owner", "who", "link", "family", "--participant", "@luis", "--member", "Luis")
        self.assertIn("18 or older", out["ask_owner"])
        self.ok("who", "link", "family", "--participant", "@luis", "--member", "Luis",
                "--owner-confirmed", "yes, he's my husband", "--confirm", out["confirm"])  # fmt: skip
        self.ok("who", "link", "family", "--participant", "@ana", "--member", "Ana")  # the owner needs no check
        self.ok("who", "chat", "luis-dm", "--type", "direct", "--member", "Luis")
        self.ok("who", "chat", "garden", "--type", "group", "--minors", "no")
        self.ok("who", "link", "garden", "--participant", "@lu", "--member", "Luis")  # already confirmed once
        record = Hub(self.home).household().member("M2")["chat_ok"]
        self.assertEqual(record["owner_said"], "yes, he's my husband")

    def test_kids_and_teens_are_noted_never_linked(self):
        for handle, name in (("@sofia", "Sofia"), ("@mateo", "Mateo")):
            out = self.ok("who", "link", "family", "--participant", handle, "--member", name)
            self.assertIn("don't chat with the agent", out["summary"])
            # Their messages are recognised and refused kindly, rather than asking the owner again and again.
            self.err("minor_cannot_chat", "shop", "add", "pizza", "--chat", "family", "--from", handle)
        chat = Hub(self.home).household().meta()["chats"]["family"]
        self.assertEqual((chat["participants"], chat["minors_present"]), ({}, True))
        self.err("minor_cannot_chat", "who", "chat", "kid-dm", "--type", "direct", "--member", "Sofia")

    def test_only_the_owner_links_chats(self):
        self.err("not_authorized", "who", "chat", "x", "--type", "group", "--minors", "no", "--as", "Luis")
        self.err("not_authorized", "who", "link", "family", "--participant", "@a", "--member", "Ana", "--as", "Luis")

    def test_group_messages_need_a_known_sender(self):
        self.err("who_is_talking", "who", "am-i", "--chat", "family")
        out = self.err("unknown_participant", "who", "am-i", "--chat", "family", "--from", "@stranger")
        self.assertIn("who link", out["hint"])
        self.err("chat_not_linked", "who", "am-i", "--chat", "nowhere", "--from", "@ana")

    def test_group_audience_includes_every_linked_adult_and_a_child_stand_in(self):
        self.ok("who", "link", "family", "--participant", "@ana", "--member", "Ana")
        self.confirmed("who", "link", "family", "--participant", "@luis", "--member", "Luis", words="yes")
        out = self.ok("who", "am-i", "--chat", "family", "--from", "@luis")
        self.assertEqual(out["member"]["name"], "Luis")
        self.assertEqual(out["audience"], ["Luis", "Ana", "a child"])
        self.assertTrue(out["minors_present"])

    def test_as_is_refused_in_group_chats(self):
        self.confirmed("who", "link", "family", "--participant", "@luis", "--member", "Luis", words="yes")
        self.err("use_from_in_groups", "who", "am-i", "--chat", "family", "--from", "@luis", "--as", "Ana")
        self.ok("who", "chat", "ana-dm", "--type", "direct")
        self.assertEqual(self.ok("who", "am-i", "--chat", "ana-dm")["member"]["name"], "Ana")

    def test_a_participant_handle_maps_to_one_member(self):
        self.ok("who", "link", "family", "--participant", "@ana", "--member", "Ana")
        asked = self.err("needs_owner", "who", "link", "family", "--participant", "@ana", "--member", "Luis")
        self.err("already_linked", "who", "link", "family", "--participant", "@ana", "--member", "Luis",
                 "--owner-confirmed", "yes", "--confirm", asked["confirm"])  # fmt: skip

    def test_a_chat_belongs_to_one_household(self):
        self.ok("household", "add", "--name", "Other", "--members", "Ana", "--country", "GB")
        self.err("chat_in_other_household", "who", "chat", "family", "--type", "group", "--minors", "no")
        # The chat still routes to its own household, whichever household is active.
        self.ok("who", "link", "family", "--participant", "@ana", "--member", "Ana", "--household", "Test home")
        out = self.ok("who", "am-i", "--chat", "family", "--from", "@ana")
        self.assertEqual(out["household"]["name"], "Test home")

    def test_becoming_a_teen_unlinks_chats(self):
        self.confirmed("who", "link", "family", "--participant", "@luis", "--member", "Luis", words="yes")
        out = self.ok("member", "access", "Luis", "--role", "teen")
        self.assertEqual(out["unlinked_chats"], ["family"])
        self.err("unknown_participant", "who", "am-i", "--chat", "family", "--from", "@luis")

    def test_a_removed_members_direct_chat_is_deleted_not_handed_to_the_owner(self):
        self.confirmed("who", "chat", "luis-dm", "--type", "direct", "--member", "Luis", words="yes")
        self.assertEqual(self.ok("who", "am-i", "--chat", "luis-dm")["member"]["name"], "Luis")
        out = self.confirmed("member", "remove", "Luis", words="yes")
        self.assertIn("deleted their direct chat luis-dm", out["changes"])
        self.err("chat_not_linked", "who", "am-i", "--chat", "luis-dm")  # never falls back to Ana
        self.assertNotIn("luis-dm", Hub(self.home).data["chats"])

    def test_becoming_a_teen_deletes_their_direct_chat(self):
        self.confirmed("who", "chat", "luis-dm", "--type", "direct", "--member", "Luis", words="yes")
        out = self.ok("member", "access", "Luis", "--role", "teen")
        self.assertEqual(out["deleted_chats"], ["luis-dm"])
        self.err("chat_not_linked", "who", "am-i", "--chat", "luis-dm")

    def test_a_direct_chat_with_nobody_attached_is_refused(self):
        hh = Hub(self.home).household()
        with hh.transaction():
            hh.meta()["chats"]["odd-dm"] = {"type": "direct", "member": None, "participants": {}}
            hh.touch("household")
        with Hub(self.home).transaction() as data:
            data["chats"]["odd-dm"] = hh.id
        self.err("chat_not_linked", "who", "am-i", "--chat", "odd-dm")

    def test_removing_the_speaker_leaves_nobody_speaking_until_the_owner_says(self):
        self.confirmed("who", "speaker", "Luis", words="yes, Luis is my partner")
        self.confirmed("member", "remove", "Luis", "--as", "Ana", words="yes")
        self.err("who_is_talking", "who", "am-i")  # not quietly the owner
        self.ok("who", "speaker", "Ana", "--as", "Ana")
        self.assertEqual(self.ok("who", "am-i")["member"]["name"], "Ana")

    def test_removing_a_member_unlinks_them(self):
        self.confirmed("who", "link", "family", "--participant", "@luis", "--member", "Luis", words="yes")
        out = self.confirmed("member", "remove", "Luis", words="yes")
        self.assertIn("unlinked from family", out["changes"])

    def test_speaker_and_forget_chat(self):
        self.err("needs_owner", "who", "speaker", "Luis")  # an adult who hasn't been confirmed 18+ yet
        self.confirmed("who", "speaker", "Luis", words="yes")
        self.assertEqual(self.ok("who", "am-i")["member"]["name"], "Luis")
        self.err("not_authorized", "who", "speaker", "Ana")  # Luis is talking now, and isn't the owner
        self.ok("who", "speaker", "Ana", "--as", "Ana")
        self.err("minor_cannot_chat", "who", "speaker", "Sofia")
        self.ok("who", "forget-chat", "family")
        self.err("chat_not_linked", "who", "am-i", "--chat", "family", "--from", "@ana")

    def test_listing_households_is_direct_chat_only(self):
        self.ok("who", "link", "family", "--participant", "@ana", "--member", "Ana")
        self.err("direct_chat_only", "household", "list", "--chat", "family", "--from", "@ana")
        self.err("direct_chat_only", "household", "delete", "--chat", "family", "--from", "@ana",
                 "--owner-confirmed", "yes")  # fmt: skip
