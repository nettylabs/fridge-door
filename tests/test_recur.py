"""Repeat rules: parsing, expansion, the completion rule ported from the original plan, and plain English."""

import datetime as dt
import unittest

import helpers  # noqa: F401
from fridgedoor import recur
from fridgedoor.util import ToolError

D = dt.date
MON = D(2026, 10, 19)


def dates(rule_text, start, first, last, **kw):
    return recur.between(recur.parse(rule_text), start, first, last, **kw)


class ParseTest(unittest.TestCase):
    def test_round_trip_is_canonical(self):
        self.assertEqual(recur.normalize("rrule:freq=weekly;byday=th,mo"), "FREQ=WEEKLY;BYDAY=MO,TH")
        self.assertEqual(recur.normalize("FREQ=MONTHLY;BYDAY=-1FR;COUNT=5"), "FREQ=MONTHLY;BYDAY=-1FR;COUNT=5")
        self.assertEqual(recur.normalize("FREQ=DAILY;INTERVAL=1"), "FREQ=DAILY")
        self.assertEqual(recur.normalize("FREQ=WEEKLY;UNTIL=20261231T000000Z"), "FREQ=WEEKLY;UNTIL=20261231")

    def test_garbage_is_refused_with_a_hint(self):
        for text in ("", "FREQ=HOURLY", "FREQ=WEEKLY;INTERVAL=0", "FREQ=WEEKLY;INTERVAL=abc", "FREQ=WEEKLY;BYDAY=XX",
                     "FREQ=WEEKLY;BYDAY=2TU", "FREQ=MONTHLY;BYMONTHDAY=0", "FREQ=DAILY;COUNT=3;UNTIL=20261231",
                     "INTERVAL=2", "FREQ=MONTHLY;BYSETPOS=0", "FREQ=MONTHLY;UNTIL=20261340", "nonsense"):  # fmt: skip
            with self.assertRaises(ToolError, msg=text) as cm:
                recur.parse(text)
            self.assertIn(cm.exception.code, ("bad_repeat", "unsupported_repeat"))

    def test_unsupported_parts_are_named(self):
        with self.assertRaises(ToolError) as cm:
            recur.parse("FREQ=DAILY;BYHOUR=9")
        self.assertEqual(cm.exception.code, "unsupported_repeat")


class ExpandTest(unittest.TestCase):
    def test_daily_and_interval(self):
        self.assertEqual(dates("FREQ=DAILY;INTERVAL=3", MON, MON, D(2026, 10, 28)),
                         [D(2026, 10, 19), D(2026, 10, 22), D(2026, 10, 25), D(2026, 10, 28)])  # fmt: skip

    def test_weekly_on_days_and_every_other_week(self):
        self.assertEqual(dates("FREQ=WEEKLY;BYDAY=MO,TH", MON, MON, D(2026, 10, 29)),
                         [D(2026, 10, 19), D(2026, 10, 22), D(2026, 10, 26), D(2026, 10, 29)])  # fmt: skip
        self.assertEqual(dates("FREQ=WEEKLY;INTERVAL=2;BYDAY=SA", D(2026, 10, 24), MON, D(2026, 11, 30)),
                         [D(2026, 10, 24), D(2026, 11, 7), D(2026, 11, 21)])  # fmt: skip

    def test_monthly_by_date_ordinal_and_last(self):
        self.assertEqual(dates("FREQ=MONTHLY;BYDAY=2TU", D(2026, 10, 1), D(2026, 10, 1), D(2026, 12, 31)),
                         [D(2026, 10, 13), D(2026, 11, 10), D(2026, 12, 8)])  # fmt: skip
        self.assertEqual(dates("FREQ=MONTHLY;BYDAY=-1FR", D(2026, 10, 1), D(2026, 10, 1), D(2026, 12, 31)),
                         [D(2026, 10, 30), D(2026, 11, 27), D(2026, 12, 25)])  # fmt: skip
        self.assertEqual(dates("FREQ=MONTHLY;BYMONTHDAY=-1", D(2026, 1, 31), D(2026, 1, 1), D(2026, 4, 30)),
                         [D(2026, 1, 31), D(2026, 2, 28), D(2026, 3, 31), D(2026, 4, 30)])  # fmt: skip

    def test_monthly_on_the_31st_skips_short_months_in_plain_rrule(self):
        # Standard RRULE behaviour, kept for imported rules (ported test).
        self.assertEqual(dates("FREQ=MONTHLY;BYMONTHDAY=31", D(2026, 1, 31), D(2026, 1, 1), D(2026, 5, 31)),
                         [D(2026, 1, 31), D(2026, 3, 31), D(2026, 5, 31)])  # fmt: skip

    def test_words_for_the_31st_fall_back_to_the_last_day(self):
        rule = recur.from_words("monthly on the 31st", D(2026, 1, 31))
        self.assertEqual(dates(rule, D(2026, 1, 31), D(2026, 1, 1), D(2026, 4, 30)),
                         [D(2026, 1, 31), D(2026, 2, 28), D(2026, 3, 31), D(2026, 4, 30)])  # fmt: skip

    def test_yearly_and_leap_day_birthdays(self):
        self.assertEqual(dates("FREQ=YEARLY;BYMONTH=3;BYMONTHDAY=14", D(2020, 3, 14), D(2026, 1, 1), D(2028, 12, 31)),
                         [D(2026, 3, 14), D(2027, 3, 14), D(2028, 3, 14)])  # fmt: skip
        rule = recur.from_words("yearly", D(2028, 2, 29))
        self.assertEqual(dates(rule, D(2028, 2, 29), D(2028, 1, 1), D(2030, 12, 31)),
                         [D(2028, 2, 29), D(2029, 2, 28), D(2030, 2, 28)])  # fmt: skip
        self.assertEqual(dates("FREQ=YEARLY;BYMONTH=11;BYDAY=4TH", D(2026, 11, 1), D(2026, 1, 1), D(2027, 12, 31)),
                         [D(2026, 11, 26), D(2027, 11, 25)])  # fmt: skip

    def test_count_until_and_skipped_dates(self):
        self.assertEqual(len(dates("FREQ=DAILY;COUNT=5", MON, MON, D(2027, 1, 1))), 5)
        self.assertEqual(dates("FREQ=WEEKLY;UNTIL=20261102", MON, MON, D(2027, 1, 1)),
                         [D(2026, 10, 19), D(2026, 10, 26), D(2026, 11, 2)])  # fmt: skip
        self.assertEqual(dates("FREQ=WEEKLY", MON, MON, D(2026, 11, 2), skip={D(2026, 10, 26)}),
                         [D(2026, 10, 19), D(2026, 11, 2)])  # fmt: skip

    def test_include_start_counts_as_the_first_occurrence(self):
        # A calendar file may start on a day the rule doesn't match; calendars still show that day.
        got = dates("FREQ=WEEKLY;BYDAY=MO;COUNT=3", D(2026, 10, 21), D(2026, 10, 1), D(2026, 12, 1), include_start=True)
        self.assertEqual(got, [D(2026, 10, 21), D(2026, 10, 26), D(2026, 11, 2)])

    def test_never_matching_rules_end_instead_of_hanging(self):
        rule = recur.parse("FREQ=MONTHLY;BYMONTH=2;BYMONTHDAY=30")
        self.assertIsNone(recur.next_after(rule, D(2026, 1, 1), D(2026, 1, 1)))


class NextDueTest(unittest.TestCase):
    """The completion rule, ported from the original recurrence tests."""

    def test_daily_due_today_completed_today_gives_tomorrow(self):
        self.assertEqual(recur.next_due("FREQ=DAILY", MON, MON), D(2026, 10, 20))

    def test_catching_up_an_overdue_daily_chore_leaves_todays_to_do(self):
        self.assertEqual(recur.next_due("FREQ=DAILY", D(2026, 10, 15), MON), MON)  # the missed days are skipped
        self.assertEqual(recur.next_due("FREQ=WEEKLY;BYDAY=MO", D(2026, 10, 12), D(2026, 10, 14)), D(2026, 10, 19))

    def test_daily_with_no_due_date_anchors_on_the_completion_day(self):
        self.assertEqual(recur.next_due("FREQ=DAILY", None, MON), D(2026, 10, 20))

    def test_weekly_byday_walks_the_selected_weekdays(self):
        self.assertEqual(recur.next_due("FREQ=WEEKLY;BYDAY=MO,TH", MON, MON), D(2026, 10, 22))
        self.assertEqual(recur.next_due("FREQ=WEEKLY;BYDAY=MO,TH", D(2026, 10, 22), D(2026, 10, 22)), D(2026, 10, 26))

    def test_weekly_without_byday_recurs_on_the_due_weekday(self):
        self.assertEqual(recur.next_due("FREQ=WEEKLY", D(2026, 10, 21), D(2026, 10, 21)), D(2026, 10, 28))

    def test_early_completion_gives_the_next_one_not_this_one(self):
        saturday = D(2026, 10, 24)
        self.assertEqual(recur.next_due("FREQ=WEEKLY;BYDAY=SA", saturday, D(2026, 10, 22)), D(2026, 10, 31))

    def test_monthly_bymonthday(self):
        self.assertEqual(recur.next_due("FREQ=MONTHLY;BYMONTHDAY=25", D(2026, 10, 25), D(2026, 10, 20)),
                         D(2026, 11, 25))  # fmt: skip
        self.assertEqual(recur.next_due("FREQ=MONTHLY;BYMONTHDAY=25", None, D(2026, 10, 20)), D(2026, 10, 25))

    def test_every_other_week_stays_on_its_weeks(self):
        rule = "FREQ=WEEKLY;INTERVAL=2;BYDAY=SA"
        self.assertEqual(recur.next_due(rule, D(2026, 10, 24), D(2026, 10, 24)), D(2026, 11, 7))
        self.assertEqual(recur.next_due(rule, D(2026, 10, 24), D(2026, 10, 30)), D(2026, 11, 7))

    def test_broken_or_finished_rules_give_none_and_never_raise(self):
        for text in (None, "", "garbage", "FREQ=WEEKLY;INTERVAL=0", "FREQ=WEEKLY;BYDAY=XX"):
            self.assertIsNone(recur.next_due(text, MON, MON))
        self.assertIsNone(recur.next_due("FREQ=DAILY;UNTIL=20261019", MON, MON))

    def test_count_stops_after_the_last_occurrence(self):
        self.assertEqual(recur.next_due("FREQ=DAILY;COUNT=3", MON, MON, occurrence=2), D(2026, 10, 20))
        self.assertIsNone(recur.next_due("FREQ=DAILY;COUNT=3", MON, MON, occurrence=3))


class WordsTest(unittest.TestCase):
    CASES = {
        "daily": "FREQ=DAILY",
        "every 3 days": "FREQ=DAILY;INTERVAL=3",
        "every other day": "FREQ=DAILY;INTERVAL=2",
        "weekdays": "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR",
        "weekends": "FREQ=WEEKLY;BYDAY=SA,SU",
        "weekly": "FREQ=WEEKLY;BYDAY=MO",
        "every monday": "FREQ=WEEKLY;BYDAY=MO",
        "Tuesdays and Thursdays": "FREQ=WEEKLY;BYDAY=TU,TH",
        "weekly on mon, thu": "FREQ=WEEKLY;BYDAY=MO,TH",
        "every 2 weeks on sat": "FREQ=WEEKLY;INTERVAL=2;BYDAY=SA",
        "every other tuesday": "FREQ=WEEKLY;INTERVAL=2;BYDAY=TU",
        "every 2 tuesdays": "FREQ=WEEKLY;INTERVAL=2;BYDAY=TU",
        "every other week on fri": "FREQ=WEEKLY;INTERVAL=2;BYDAY=FR",
        "every first monday": "FREQ=MONTHLY;BYDAY=1MO",
        "every third thursday": "FREQ=MONTHLY;BYDAY=3TH",
        "fortnightly": "FREQ=WEEKLY;INTERVAL=2;BYDAY=MO",
        "monthly": "FREQ=MONTHLY;BYMONTHDAY=19",
        "monthly on the 1st": "FREQ=MONTHLY;BYMONTHDAY=1",
        "monthly on the last day": "FREQ=MONTHLY;BYMONTHDAY=-1",
        "monthly on the 2nd tuesday": "FREQ=MONTHLY;BYDAY=2TU",
        "first monday of every month": "FREQ=MONTHLY;BYDAY=1MO",
        "monthly on the last friday": "FREQ=MONTHLY;BYDAY=-1FR",
        "quarterly": "FREQ=MONTHLY;INTERVAL=3;BYMONTHDAY=19",
        "yearly": "FREQ=YEARLY;BYMONTH=10;BYMONTHDAY=19",
        "every 2 years": "FREQ=YEARLY;INTERVAL=2;BYMONTH=10;BYMONTHDAY=19",
    }

    def test_friendly_words(self):
        for words, expected in self.CASES.items():
            self.assertEqual(recur.from_words(words, MON), expected, words)

    def test_end_date_or_count(self):
        self.assertEqual(recur.from_words("weekly", MON, until=D(2026, 12, 31)), "FREQ=WEEKLY;BYDAY=MO;UNTIL=20261231")
        self.assertEqual(recur.from_words("daily", MON, count=10), "FREQ=DAILY;COUNT=10")

    def test_unreadable_words(self):
        with self.assertRaises(ToolError):
            recur.from_words("whenever", MON)

    def test_every_second_weekday_is_asked_not_guessed(self):
        for words in ("every second tuesday", "every 2nd tue"):  # fortnightly, or monthly on the 2nd Tuesday?
            with self.assertRaises(ToolError) as caught:
                recur.from_words(words, MON)
            self.assertIn("monthly on the 2nd", caught.exception.hint)
        self.assertEqual(recur.from_words("monthly on the second tuesday", MON), "FREQ=MONTHLY;BYDAY=2TU")

    def test_describe(self):
        self.assertEqual(recur.describe(None), "doesn't repeat")
        self.assertEqual(recur.describe("FREQ=WEEKLY;INTERVAL=2;BYDAY=SA"), "every 2 weeks on Sat")
        self.assertEqual(recur.describe("FREQ=MONTHLY;BYDAY=-1FR"), "monthly on the last Fri")
        self.assertEqual(recur.describe("FREQ=YEARLY;BYMONTH=3;BYMONTHDAY=14"), "every year on 14 Mar")
        self.assertEqual(recur.describe("FREQ=DAILY;COUNT=10"), "every day, 10 times")
        self.assertEqual(recur.describe("FREQ=WEEKLY;BYDAY=MO;UNTIL=20261231"), "weekly on Mon until 31 Dec 2026")
        self.assertEqual(recur.describe("garbage"), "custom schedule")


if __name__ == "__main__":
    unittest.main()
