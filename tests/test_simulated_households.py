"""Fixes for what four simulated households found (a family in Canada, a couple in the UK, flatmates in Australia
and a single parent in the US), and the security review's notes on them. Each test names the problem it guards."""

import datetime as _dt
import json
import time
import zipfile

from helpers import HomeTest, fridge
from fridgedoor import printables
from fridgedoor.store import Hub


def events_of(home):
    return Hub(home).household().data("calendar")["events"]


class SecurityReviewTest(HomeTest):
    def setUp(self):
        super().setUp()
        self.setup_family("Ana, Luis, Theo (kid)", "GB")

    def test_a_years_long_event_is_refused_and_a_stored_one_stays_quick_to_show(self):
        self.err("bad_date", "cal", "add", "Forever", "--date", "today", "--until-date", "9999-12-31")
        hh = Hub(self.home).household()
        with hh.transaction():  # an old or hand-edited file with a silly end date
            hh.data("calendar")["events"].append({
                "id": "E99", "title": "Forever", "type": "other", "kind": "event", "date": "2026-10-01",
                "time": None, "end_time": None, "end_date": "9999-12-31", "visibility": "household", "members": [],
                "owner": "M1", "reminders": [], "rrule": None, "exdates": [], "overrides": {}})
            hh.touch("calendar")
        started = time.monotonic()
        out = self.ok("cal", "week")
        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual(out["text"].count("Forever"), 7)  # once a day, for the week asked for only

    def test_undo_by_name_never_reaches_a_list_the_person_cant_see(self):
        # Luis's private repeating task: one ticked off on his own list, then the next one moved to the shared list.
        self.ok("todo", "add", "Water plants", "--mine", "--repeat", "daily", "--as", "Luis")
        self.ok("todo", "done", "Water plants", "--as", "Luis")
        self.ok("todo", "edit", "Water plants", "--list", "Household Tasks", "--as", "Luis")
        out = self.ok("todo", "undo", "Water plants")  # Ana sees only the shared one, which isn't done
        self.assertIn("isn't done yet", out["summary"])
        done = [t for t in Hub(self.home).household().data("todos")["tasks"]
                if t["title"] == "Water plants" and t.get("completed_at")]
        self.assertEqual(len(done), 1)  # Luis's private one stays done


class OwnerAndChatsTest(HomeTest):
    def setUp(self):
        super().setUp()
        self.setup_family("Kai, Jess, Sam, Arjun (14)", "AU", "Flat 4", "--timezone", "Australia/Perth")
        self.ok("who", "chat", "flat", "--type", "group", "--minors", "no")

    def test_the_owners_no_never_switches_anything_on(self):
        self.err("owner_declined", "who", "link", "flat", "--participant", "@jess", "--member", "Jess",
                 "--owner-confirmed", "No - Jess is only 16")
        self.err("minor_cannot_chat", "who", "link", "flat", "--participant", "@jess", "--member", "Jess",
                 "--owner-confirmed", "yes, she's 16")  # a yes that says they're under 18
        self.err("owner_declined", "household", "settings", "--set", "sensitive_notes_in_groups=yes",
                 "--owner-confirmed", "nah leave it off")
        self.err("owner_declined", "member", "remove", "Sam", "--owner-confirmed", "no, don't")
        self.assertIsNotNone(Hub(self.home).household().member("M3"))  # Sam is still there

    def test_one_to_one_chats_need_the_same_adult_check_and_belong_to_their_person(self):
        self.err("needs_owner", "who", "chat", "jess-dm", "--type", "direct", "--member", "Jess")
        self.confirmed("who", "chat", "jess-dm", "--type", "direct", "--member", "Jess", words="yes")
        self.ok("member", "access", "Jess", "--set", "budget=none")
        self.err("chat_belongs_to_someone", "budget", "bills", "--chat", "jess-dm", "--as", "Kai")
        self.assertEqual(self.ok("who", "am-i", "--chat", "jess-dm", "--as", "Jess")["member"]["name"], "Jess")
        self.assertIn("jess-dm (Jess)", self.ok("who", "show")["summary"])

    def test_a_teens_handle_is_noted_so_their_messages_are_recognised(self):
        self.ok("who", "link", "flat", "--participant", "@arjun14", "--member", "Arjun")
        self.err("minor_cannot_chat", "shop", "add", "pizza pops", "--chat", "flat", "--from", "@arjun14")
        self.assertTrue(Hub(self.home).household().meta()["chats"]["flat"]["minors_present"])

    def test_the_owners_export_leaves_out_other_peoples_private_things(self):
        self.ok("cal", "add", "Job interview", "--date", "friday", "--private", "--as", "Sam")
        self.ok("note", "add", "Gift ideas for Jess", "--private", "--as", "Sam")
        self.ok("todo", "add", "Call the bank", "--mine", "--as", "Jess")
        self.ok("cal", "add", "Rent inspection", "--date", "friday")
        self.ok("todo", "add", "Renew my licence", "--mine")
        path = self.ok("export")["file"]
        with zipfile.ZipFile(path) as zf:
            files = {name.split("/")[-1]: json.loads(zf.read(name)) for name in zf.namelist()
                     if name.endswith(".json")}
        self.assertEqual([e["title"] for e in files["calendar.json"]["events"]], ["Rent inspection"])
        self.assertEqual(files["notes.json"]["notes"], [])
        tasks = [t["title"] for t in files["todos.json"]["tasks"]]
        self.assertIn("Renew my licence", tasks)
        self.assertNotIn("Call the bank", tasks)


class DatesAndNamesTest(HomeTest):
    def setUp(self):
        super().setUp()
        self.setup_family("Jordan, Ava (11), Noah (7)", "US", "Home", "--timezone", "America/Denver")
        self.ok("budget", "category-edit", "Groceries", "--monthly", "600")

    def test_dates_people_write_and_dates_written_back_their_way(self):
        out = self.ok("cal", "add", "Dentist", "--date", "Nov 5", "--time", "3:15pm", "--for", "Noah")
        self.assertIn("Thu Nov 5", out["summary"])
        self.assertEqual(events_of(self.home)[-1]["date"], "2026-11-05")
        self.ok("cal", "add", "Book fair", "--date", "10/30/2026")
        self.assertEqual(events_of(self.home)[-1]["date"], "2026-10-30")
        out = self.ok("budget", "spend", "42.10", "--category", "Groceries", "--date", "friday")
        self.assertIn("Fri Oct 16", out["summary"])  # spending: the Friday that's been, not the coming one
        self.ok("budget", "spend", "10", "--category", "Groceries", "--date", "last monday")
        self.err("future_date", "budget", "spend", "12", "--category", "Groceries", "--date", "tomorrow")
        self.err("bad_number", "budget", "spend", "12.999", "--category", "Groceries")

    def test_kids_names_are_one_word_and_their_birth_years_arent_kept(self):
        self.err("minor_details", "member", "add", "--name", "Mia Brooks", "--role", "kid")
        self.ok("member", "add", "--name", "Mary-Jane", "--role", "kid")
        out = self.ok("cal", "birthday", "--member", "Ava", "--date", "2015-03-14")
        self.assertIn("Only the day and month are kept", out["summary"])

    def test_names_match_by_their_words(self):
        self.ok("todo", "add", "Put the black bin out", "--due", "today")
        self.ok("todo", "done", "black bin")
        self.ok("budget", "bill-add", "Power and gas", "--amount", "141.80", "--due", "2026-10-22")
        self.ok("budget", "bill-paid", "power bill")
        self.ok("todo", "add", "Book the winter tyre swap")
        self.ok("todo", "done", "winter tire swap")  # British and American spellings

    def test_a_twelve_hour_household_is_asked_am_or_pm(self):
        self.err("ambiguous_time", "cal", "add", "Soccer", "--date", "monday", "--time", "4:30")
        self.ok("cal", "add", "Soccer", "--date", "monday", "--time", "4:30pm")
        self.ok("cal", "add", "Brunch", "--date", "sunday", "--time", "10:00")  # two digits: the 24-hour clock


class RepeatsAndChoresTest(HomeTest):
    def setUp(self):
        super().setUp()
        self.setup_family("Kai, Jess, Sam", "AU", "Flat 4", "--timezone", "Australia/Perth")

    def test_repeat_words_are_read_or_asked_about(self):
        out = self.ok("todo", "add", "Bins", "--repeat", "every two weeks", "--dry-run")
        self.assertIn("every 2 weeks", out["summary"])
        out = self.ok("todo", "add", "Bathroom", "--repeat", "every second week", "--dry-run")
        self.assertIn("every 2 weeks", out["summary"])
        self.err("bad_repeat", "todo", "add", "Gym", "--repeat", "twice a week")
        self.err("bad_repeat", "cal", "add", "Book club", "--repeat", "every second tuesday")

    def test_a_chore_starts_on_its_first_matching_day(self):
        out = self.ok("todo", "add", "Bin night", "--repeat", "weekly on tue", "--rotate", "Kai, Jess, Sam")
        self.assertIn("due tomorrow", out["summary"])  # added on a Monday
        out = self.ok("todo", "add", "Window cleaner cash", "--repeat", "monthly on the 2nd monday", "--dry-run")
        self.assertIn("9 Nov", out["summary"])

    def test_catching_up_an_overdue_daily_chore_keeps_todays(self):
        self.ok("todo", "add", "Dishes", "--repeat", "daily", "--due", "yesterday")
        out = self.ok("todo", "done", "Dishes")
        self.assertIn("next one today", out["summary"])

    def test_the_chores_view_shows_whose_turn_it_is_all_week(self):
        self.ok("todo", "add", "Dishes", "--repeat", "daily", "--rotate", "Kai, Jess, Sam")
        chart = {c["member"]: len(c["tasks"]) for c in self.ok("todo", "chores")["chart"]}
        self.assertEqual(chart, {"Kai": 3, "Jess": 2, "Sam": 2})

    def test_removing_someone_whose_turn_it_is_passes_it_on(self):
        self.ok("todo", "add", "Bins", "--repeat", "weekly on tue", "--rotate", "Sam, Kai, Jess")
        out = self.confirmed("member", "remove", "Sam", words="yes, Sam has moved out")
        self.assertIn("passed their turn on Bins", " ".join(out["changes"]))
        task = next(t for t in Hub(self.home).household().data("todos")["tasks"] if t["title"] == "Bins")
        self.assertEqual(task["assignee"], "M1")  # Kai, next in line

    def test_a_turn_notice_says_when_its_due(self):
        self.ok("todo", "add", "Bathroom", "--repeat", "weekly", "--rotate", "Kai, Jess")
        self.ok("todo", "done", "Bathroom")
        notice = self.ok("notices", "list", "--as", "Jess")["notices"][0]["text"]
        self.assertTrue(notice.startswith("Your turn: Bathroom, due "), notice)


class BudgetTest(HomeTest):
    def setUp(self):
        super().setUp()
        self.setup_family("Sam, Alex", "GB")

    def test_categories_exist_from_the_start(self):
        self.ok("budget", "bill-add", "Rent", "--amount", "950", "--due", "2026-11-01", "--repeat", "monthly",
                "--category", "Housing")

    def test_a_bill_paid_twice_by_two_people_isnt_paid_for_next_month(self):
        self.ok("budget", "bill-add", "Broadband", "--amount", "32.99", "--due", "2026-10-18", "--repeat", "monthly")
        self.ok("budget", "bill-paid", "Broadband", "--as", "Alex")
        out = self.err("not_due_yet", "budget", "bill-paid", "Broadband")
        self.assertIn("recorded as paid", out["error"])
        out = self.ok("budget", "bill-paid", "Broadband", "--due", "2026-11-18", "--by", "Alex")
        self.assertIn("Next due Fri 18 Dec", out["summary"])

    def test_the_month_headline_compares_only_budgeted_categories(self):
        self.ok("budget", "category-edit", "Groceries", "--monthly", "600")
        self.ok("budget", "spend", "96.18", "--category", "Groceries")
        self.ok("budget", "spend", "1450", "--category", "Housing")
        out = self.ok("budget", "month")
        self.assertIn("£96.18 of £600.00 in the categories with a budget (£503.82 left)", out["summary"])
        self.assertIn("£1,450.00 in categories without one", out["summary"])

    def test_autopay_bills_arent_overdue(self):
        self.ok("budget", "bill-add", "Internet", "--amount", "89", "--due", "2026-10-15", "--autopay")
        out = self.ok("budget", "bills")
        self.assertNotIn("overdue", out["text"])
        self.assertIn("record it once it's gone out", out["text"])

    def test_the_budget_report_stays_out_of_group_chats(self):
        self.ok("who", "chat", "us", "--type", "group", "--minors", "no")
        self.ok("who", "link", "us", "--participant", "@sam", "--member", "Sam")
        self.confirmed("who", "link", "us", "--participant", "@alex", "--member", "Alex", words="yes")
        self.err("direct_chat_only", "print", "budget", "--chat", "us", "--from", "@sam")


class CalendarTest(HomeTest):
    def setUp(self):
        super().setUp()
        self.setup_family("Priya, Dev, Arjun (14), Maya (9)", "CA", "Home", "--timezone", "America/Regina")

    def test_moving_a_start_keeps_the_length(self):
        self.ok("cal", "add", "Hockey", "--date", "tuesday", "--time", "17:30", "--end", "19:00", "--repeat", "weekly")
        self.ok("cal", "edit", "Hockey", "--on", "2026-10-27", "--time", "18:30")
        occ = [o for o in self.ok("cal", "agenda", "--days", "14")["occurrences"] if o["date"] == "2026-10-27"][0]
        self.assertEqual((occ["time"], occ["end_time"]), ("18:30", "20:00"))
        self.ok("cal", "add", "Optician", "--date", "friday", "--time", "18:00", "--end", "18:30")
        self.ok("cal", "edit", "Optician", "--time", "18:45")
        optician = next(e for e in events_of(self.home) if e["title"] == "Optician")
        self.assertEqual(optician["end_time"], "19:15")

    def test_dates_inside_sentences_read_naturally(self):
        self.ok("cal", "add", "Soccer", "--date", "tuesday", "--time", "17:30", "--repeat", "weekly")
        out = self.ok("cal", "skip", "Soccer", "--on", "tomorrow", "--dry-run")
        self.assertIn("on Tue 2026-10-20 (tomorrow).", out["summary"])  # not "on Tomorrow, Tue ..."
        self.assertEqual(self.ok("cal", "week")["text"].splitlines()[0], "Week of Sun 2026-10-18")

    def test_a_multi_day_event_shows_on_each_day(self):
        self.ok("cal", "add", "Camping", "--date", "2026-10-22", "--until-date", "2026-10-24")
        text = self.ok("cal", "week")["text"]
        self.assertEqual(text.count("Camping"), 3)
        day = self.ok("cal", "day", "2026-10-23")["text"]
        self.assertIn("(day 2 of 3)", day)

    def test_a_parents_today_includes_the_kids_events(self):
        self.ok("cal", "add", "Field trip", "--date", "today", "--time", "07:15", "--for", "Maya")
        lines = self.ok("today")["sections"]["events"]["lines"]
        self.assertTrue(any("Field trip" in line for line in lines), lines)

    def test_busy_evenings_count_events_running_past_midnight(self):
        self.ok("cal", "add", "House party", "--date", "saturday", "--time", "19:00", "--end", "01:00")
        self.assertIn("2026-10-24", self.ok("cal", "busy")["busy"])

    def test_closer_icons_and_real_birthdays_only(self):
        self.ok("cal", "add", "Hockey", "--date", "friday")
        self.ok("cal", "add", "Recycling pickup", "--date", "friday")
        self.ok("cal", "add", "Pick up the birthday cake order form", "--date", "friday")
        icons = {e["title"]: e["icon"] for e in events_of(self.home)}
        self.assertEqual(icons["Hockey"], "🏒")
        self.assertEqual(icons["Recycling pickup"], "♻️")
        self.assertEqual(self.ok("cal", "birthdays", "--days", "14")["birthdays"], [])

    def test_calendar_files_cancellations_and_windows_time_zones(self):
        cal = ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:g1\r\nSUMMARY:Game\r\n"
               "DTSTART;TZID=\"Mountain Standard Time\":20261107T093000\r\nDURATION:PT75M\r\nEND:VEVENT\r\n"
               "BEGIN:VEVENT\r\nUID:g2\r\nSUMMARY:Practice\r\nDTSTART;TZID=Atlantis/Lost:20261108T100000\r\n"
               "END:VEVENT\r\nEND:VCALENDAR\r\n")  # fmt: skip
        path = self.home / "team.ics"
        path.write_text(cal, encoding="utf-8")
        out = self.ok("ics", "import", str(path))
        self.assertTrue(any("Atlantis/Lost" in w for w in out["warnings"]))
        game = next(e for e in events_of(self.home) if e["title"] == "Game")
        self.assertEqual(game["time"], "10:30")  # 9:30 in Denver; Saskatchewan never changes its clocks
        path.write_text(cal.replace("SUMMARY:Game\r\n", "SUMMARY:Game\r\nSTATUS:CANCELLED\r\n"), encoding="utf-8")
        out = self.ok("ics", "import", str(path))
        self.assertEqual(out["removed"], ["Game"])
        self.assertNotIn("Game", [e["title"] for e in events_of(self.home)])


class ShoppingTest(HomeTest):
    def setUp(self):
        super().setUp()
        self.setup_family("Sam, Alex", "GB")

    def items(self):
        return {i["name"]: (i["qty"], g["aisle"]) for g in self.ok("shop", "show")["groups"] for i in g["items"]}

    def test_amounts_said_first_two_items_said_as_one_and_everyday_words(self):
        self.ok("shop", "add", "2 pints of milk", "500g mince", "2 tins chickpeas", "eggs and bread",
                "mac and cheese", "semi-skimmed milk x2", "pak choi", "washing up liquid")
        items = self.items()
        self.assertEqual(items["milk"], ("2 pints", "Dairy"))
        self.assertEqual(items["mince"], ("500 g", "Meat"))
        self.assertEqual(items["chickpeas"], ("2 tins", "Canned"))
        self.assertIn("eggs", items)
        self.assertIn("bread", items)
        self.assertIn("mac and cheese", items)
        self.assertEqual(items["semi-skimmed milk"][1], "Dairy")
        self.assertEqual(items["pak choi"][1], "Produce")
        self.assertEqual(items["washing up liquid"][1], "Household")

    def test_crossing_off_finds_the_item_its_words_name(self):
        self.ok("shop", "add", "semi-skimmed milk", "streaky bacon")
        self.ok("shop", "cross", "milk", "bacon")
        self.assertEqual(self.ok("shop", "show")["list"]["open"], 0)
        self.ok("shop", "add", "oat milk", "almond milk")
        self.err("ambiguous", "shop", "cross", "milk")
        self.ok("shop", "readd", "streaky bacon", "semi-skimmed milk")

    def test_a_store_list_has_aisles_and_files_its_items_when_they_change(self):
        self.ok("shop", "new", "--name", "Warehouse run", "--kind", "shopping")
        self.ok("shop", "aisles", "--list", "Warehouse run", "--order", "Bulk, Household, Snacks")
        self.ok("shop", "add", "toilet paper", "crisps", "--list", "Warehouse run")
        self.assertNotIn("toilet paper", self.items())  # on the warehouse list, not the groceries
        out = self.ok("shop", "show", "--list", "Warehouse run")
        self.assertEqual([g["aisle"] for g in out["groups"]], ["Household", "Snacks"])


class RecipesAndMealsTest(HomeTest):
    def setUp(self):
        super().setUp()
        self.setup_family("Jordan, Ava (11)", "US", "Home")
        for title, lines, steps in (
            ("Chili", ["1 lb ground beef", "1 onion", "2 garlic cloves", "1 (28 oz) can tomatoes",
                       "1 tbsp chili powder", "2 eggs, beaten"], ["Brown the beef", "Add the rest", "Simmer"]),
            ("Tacos", ["1 lb ground turkey", "1 onion", "8 tortillas"], []),
        ):  # fmt: skip
            args = ["recipe", "add", "--title", title, "--servings", "4"]
            for line in lines:
                args += ["--ingredient", line]
            for step in steps:
                args += ["--step", step]
            self.ok(*args)

    def test_the_weeks_list_preview_is_what_gets_saved(self):
        self.ok("meal", "plan", "monday", "--recipe", "Chili")
        self.ok("meal", "plan", "tuesday", "--recipe", "Tacos")
        review = self.ok("meal", "to-list", "--dry-run")
        self.assertEqual(review["text"].count("onion"), 1)  # one line for both meals' onions
        self.assertIn("chili powder", [n["item"] for n in review["plan"]["check"]])  # a spoonful: check at home
        self.ok("meal", "to-list")
        items = {i["name"]: i for g in self.ok("shop", "show")["groups"] for i in g["items"]}
        self.assertIn(f"{len(items)} items", review["summary"])  # the preview counted what was saved
        self.assertEqual(items["onion"]["qty"], "2")
        self.assertEqual(items["tomatoes"]["aisle"], "Canned")
        self.assertIsNone(items["eggs"].get("note"))  # "beaten" is for the cook, not the shop

    def test_items_added_by_hand_keep_their_amount(self):
        self.ok("shop", "add", "eggs", "milk x2")
        self.ok("recipe", "to-list", "Chili")
        items = {i["name"]: i["qty"] for g in self.ok("shop", "show")["groups"] for i in g["items"]}
        self.assertEqual((items["eggs"], items["milk"]), (None, "2"))

    def test_swapping_meals_after_the_shop_doesnt_put_it_all_back(self):
        self.ok("meal", "plan", "wednesday", "--recipe", "Chili")
        self.ok("meal", "plan", "friday", "--recipe", "Tacos")
        self.ok("meal", "to-list")
        names = [i["name"] for g in self.ok("shop", "show")["groups"] for i in g["items"]]
        self.ok("shop", "cross", *names)
        out = self.ok("meal", "swap", "wednesday", "--recipe", "Tacos")  # two taco nights now
        self.assertIn("added ground turkey, tortillas.", out["summary"])
        items = {i["name"]: i["qty"] for g in self.ok("shop", "show")["groups"] for i in g["items"]}
        self.assertEqual(items, {"ground turkey": "1 lb", "tortillas": "8"})  # only what the first shop didn't cover

    def test_servings_must_be_a_real_number_and_skips_are_forgiving(self):
        self.err("usage", "meal", "plan", "monday", "--recipe", "Chili", "--servings", "-2")
        self.err("usage", "recipe", "show", "Chili", "--servings", "0")
        out = self.ok("recipe", "to-list", "Chili", "--skip", "beef, avocado", "--dry-run")
        self.assertEqual([n["item"] for n in out["plan"]["skip"]], ["ground beef"])
        self.assertEqual(out["plan"]["unmatched_skip"], ["avocado"])

    def test_scaled_amounts_read_like_a_cook_would_say_them(self):
        lines = self.ok("recipe", "show", "Chili", "--servings", "10")["recipe"]["ingredients"]
        self.assertIn("5 cloves garlic", lines)
        self.assertIn("2 1/2 tbsp chili powder", lines)
        self.assertIn("5 eggs (beaten)", lines)

    def test_cook_mode_carries_on_when_the_recipe_is_named_again(self):
        self.ok("recipe", "cook", "Chili")
        self.ok("recipe", "cook", "Chili", "--next")
        self.assertEqual(self.ok("recipe", "cook", "Chili", "--next")["step"], 2)
        self.assertIn("No steps are saved", self.ok("recipe", "cook", "Tacos")["text"])


class RemindersTest(HomeTest):
    def setUp(self):
        super().setUp()
        self.setup_family("Sam, Alex", "GB")
        for name in ("Sam", "Alex"):  # reminders are each adult's own yes
            self.ok("member", "edit", name, "--reminders", "on", "--as", name)

    def due(self, now):
        return self.ok("remind", "due", env={"FRIDGE_NOW": now})

    def test_reminders_are_worded_when_theyre_sent(self):
        self.ok("member", "edit", "Sam", "--quiet-hours", "22:00-07:00")
        self.ok("cal", "add", "Brunch", "--date", "2026-10-20", "--time", "10:00", "--remind", "12h")
        self.assertEqual(self.due("2026-10-19T23:00:00")["held"][0]["to"], "Sam")
        text = self.due("2026-10-20T07:00:00")["send"][0]["text"]
        self.assertIn("Brunch today at 10:00", text)
        self.assertNotIn("12 hours", text)

    def test_a_bill_added_after_its_reminder_time_is_still_reminded(self):
        self.confirmed("who", "chat", "alex-dm", "--type", "direct", "--member", "Alex", words="yes")
        self.ok("budget", "bill-add", "Council tax", "--amount", "180", "--due", "2026-10-21")
        out = self.due("2026-10-19T09:00:00")
        self.assertEqual([r["to"] for r in out["send"]], ["Sam", "Alex"])  # once each
        self.assertIn("is due on Wed 21 Oct", out["send"][0]["text"])

    def test_an_event_for_an_adult_who_never_chats_reminds_whoever_added_it(self):
        self.ok("cal", "add", "Dentist", "--date", "2026-10-20", "--time", "14:00", "--for", "Alex", "--remind", "1h")
        out = self.due("2026-10-20T13:05:00")
        self.assertEqual([(r["to"], r["chats"]) for r in out["send"]], [("Sam", ["direct"])])  # "remind me"
        self.assertIn("Dentist (Alex)", out["send"][0]["text"])
        self.confirmed("who", "chat", "alex-dm", "--type", "direct", "--member", "Alex", words="yes")
        self.ok("cal", "add", "Optician", "--date", "2026-10-21", "--time", "14:00", "--for", "Alex", "--remind", "1h")
        self.assertEqual([r["to"] for r in self.due("2026-10-21T13:05:00")["send"]], ["Alex"])  # now Alex's own

    def test_someone_with_no_chat_to_get_a_reminder_in_is_only_named(self):
        self.ok("budget", "bill-add", "Council tax", "--amount", "180", "--due", "2026-10-21")
        out = self.due("2026-10-19T09:00:00")
        self.assertEqual([r["to"] for r in out["send"]], ["Sam"])
        self.assertEqual(out["nowhere"], [{"to": "Alex", "member": "M2", "kind": "bill"}])  # not what it was
        self.assertIn("Alex had a reminder but no chat to get it in", out["summary"])
        self.assertEqual(self.due("2026-10-19T09:15:00")["nowhere"], [])  # said once

    def test_one_landing_in_quiet_hours_for_something_before_they_end_goes_early(self):
        self.ok("member", "edit", "Sam", "--quiet-hours", "22:30-09:00")
        self.ok("cal", "add", "Dentist", "--date", "2026-10-20", "--time", "08:30", "--remind", "1h")
        out = self.due("2026-10-19T22:05:00")
        self.assertIn("sent before quiet hours start", out["send"][0]["text"])

    def test_hours_before_count_real_hours_across_the_clock_change(self):
        self.ok("member", "edit", "Sam", "--quiet-hours", "none")
        self.ok("cal", "add", "Car boot sale", "--date", "2026-10-25", "--time", "09:00", "--remind", "12h")
        self.assertEqual(self.due("2026-10-24T21:30:00")["send"], [])  # 9am GMT is 12 hours after 10pm BST
        self.assertEqual(len(self.due("2026-10-24T22:00:00")["send"]), 1)

    def test_birthdays_remind_everyone_but_the_birthday_person(self):
        self.ok("cal", "birthday", "--member", "Alex", "--date", "20 October")
        out = self.due("2026-10-19T08:00:00")
        self.assertEqual([r["to"] for r in out["send"]], ["Sam"])

    def test_each_reminder_says_which_chats_it_may_go_to(self):
        self.ok("who", "chat", "us", "--type", "group", "--minors", "no")
        self.ok("who", "link", "us", "--participant", "@sam", "--member", "Sam")
        self.confirmed("who", "link", "us", "--participant", "@alex", "--member", "Alex", words="yes")
        self.ok("cal", "add", "Movie", "--date", "today", "--time", "20:00", "--remind", "1h")
        self.ok("cal", "add", "Therapy", "--date", "today", "--time", "20:00", "--remind", "1h", "--private")
        sent = {r["text"].split()[1]: r["chats"] for r in self.due("2026-10-19T19:05:00")["send"]}
        self.assertEqual(sent["Movie"], ["direct", "us"])
        self.assertEqual(sent["Therapy"], ["direct"])  # private: never the group


class NotesAndPrintoutsTest(HomeTest):
    def setUp(self):
        super().setUp()
        self.setup_family("Jordan, Ava (11)", "US")

    def test_a_childs_health_or_school_details_need_a_sensitive_or_private_note(self):
        body = ("--body", "Ava is allergic to peanuts, EpiPen in bag")
        out = self.err("child_details", "note", "add", "Grandma's pickup notes", *body)
        self.assertIn("--sensitive", out["hint"])
        self.ok("note", "add", "Grandma's pickup notes", *body, "--sensitive")
        self.err("child_details", "note", "add", "Ava", "--body", "Ava attends Maple Elementary")
        self.ok("note", "add", "Ava", "--body", "Ava attends Maple Elementary", "--private")
        self.ok("note", "add", "Sitter", "--body", "Bedtime 8pm")
        self.err("child_details", "note", "edit", "Sitter", "--append", "Ava has asthma, inhaler in the kitchen")
        self.ok("note", "edit", "Sitter", "--append", "Ava has asthma, inhaler in the kitchen", "--sensitive")
        self.err("child_details", "note", "edit", "Sitter", "--not-sensitive")

    def test_a_persons_own_printout_stays_theirs_and_goes_when_they_do(self):
        self.ok("member", "add", "--name", "Rose", "--role", "adult")
        self.confirmed("who", "chat", "rose-dm", "--type", "direct", "--member", "Rose", words="yes")
        self.ok("cal", "add", "Hospital check", "--date", "friday", "--private", "--chat", "rose-dm")
        out = self.ok("print", "calendar", "--mine", "--chat", "rose-dm")
        self.assertIn("/private/M3/", out["files"][0])
        self.confirmed("member", "remove", "Rose", words="yes")
        self.assertFalse((Hub(self.home).household().output_dir() / "private" / "M3").exists())


class DemoHouseholdsTest(HomeTest):
    def test_each_demo_has_one_of_each_category_and_list(self):
        for region in ("CA", "GB", "AU", "US"):
            with self.subTest(region=region):
                home = self.home / region
                self.assertEqual(fridge(home, "demo", "--region", region)[0], 0)
                for args, key, name in ((("budget", "categories"), "categories", "category"),
                                        (("shop", "lists"), "lists", "name"), (("todo", "lists"), "lists", "name")):
                    names = [row[name] for row in fridge(home, *args)[1][key]]
                    self.assertEqual(len(names), len(set(names)), names)
                groceries = next(c for c in fridge(home, "budget", "categories")[1]["categories"]
                                 if c["category"] == "Groceries")  # fmt: skip
                self.assertIsNotNone(groceries["budget"])

    def test_the_fridge_sheet_writes_dates_in_the_households_order(self):
        sun, sat, jan = _dt.date(2026, 10, 18), _dt.date(2026, 10, 24), _dt.date(2027, 1, 2)
        for order, heading, span, new_year in (
            ("DD/MM/YYYY", "Sun 18/10", "18 Oct – 24 Oct 2026", "18 Oct 2026 – 2 Jan 2027"),
            ("MM/DD/YYYY", "Sun 10/18", "Oct 18 – Oct 24, 2026", "Oct 18, 2026 – Jan 2, 2027"),
            ("YYYY-MM-DD", "Sun Oct 18", "Oct 18 – Oct 24, 2026", "Oct 18, 2026 – Jan 2, 2027"),  # 18/10 is unclear
        ):  # fmt: skip
            settings = {"date_format": order}
            self.assertEqual(printables._day_heading(sun, settings), heading)
            self.assertEqual(printables._span_text(sun, sat, settings), span)
            self.assertEqual(printables._span_text(sun, jan, settings), new_year)
