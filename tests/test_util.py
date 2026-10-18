"""Dates, times, quiet hours, months and name matching."""

import datetime as dt
import unittest

import helpers  # noqa: F401
from fridgedoor.util import ToolError, add_months, fold, in_window, match_one, parse_date, parse_hours_range, parse_time

MON = dt.date(2026, 10, 19)
SUN = dt.date(2026, 10, 25)


class DateTest(unittest.TestCase):
    def test_words_and_offsets(self):
        self.assertEqual(parse_date("today", MON), MON)
        self.assertEqual(parse_date("tomorrow", MON), dt.date(2026, 10, 20))
        self.assertEqual(parse_date("yesterday", MON), dt.date(2026, 10, 18))
        self.assertEqual(parse_date("+3", MON), dt.date(2026, 10, 22))
        self.assertEqual(parse_date("-2d", MON), dt.date(2026, 10, 17))
        self.assertEqual(parse_date("+2w", MON), dt.date(2026, 11, 2))
        self.assertEqual(parse_date("2026-12-25", MON), dt.date(2026, 12, 25))

    def test_weekday_names(self):
        self.assertEqual(parse_date("monday", MON), MON)  # today counts
        self.assertEqual(parse_date("Fri", MON), dt.date(2026, 10, 23))
        self.assertEqual(parse_date("this friday", MON), dt.date(2026, 10, 23))
        self.assertEqual(parse_date("next friday", MON), dt.date(2026, 10, 30))
        self.assertEqual(parse_date("next monday", MON), dt.date(2026, 10, 26))
        # With Sunday-start weeks, "next friday" on a Monday is still the Friday of the following week.
        self.assertEqual(parse_date("next friday", MON, week_start=6), dt.date(2026, 10, 30))

    def test_weekend_and_next_week_follow_the_old_presets(self):
        self.assertEqual(parse_date("this weekend", MON), dt.date(2026, 10, 24))
        self.assertEqual(parse_date("this weekend", SUN), SUN)  # on Sunday it means today
        self.assertEqual(parse_date("next week", MON, week_start=0), dt.date(2026, 10, 26))
        self.assertEqual(parse_date("next week", MON, week_start=6), dt.date(2026, 10, 25))
        self.assertEqual(parse_date("next week", SUN, week_start=6), dt.date(2026, 11, 1))

    def test_bad_dates(self):
        for text in ("someday", "2026-13-01", "31/13", "30 feb 2026"):
            with self.assertRaises(ToolError):
                parse_date(text, MON)
        with self.assertRaises(ToolError):  # 3/11 means different things; YYYY-MM-DD households use that
            parse_date("3/11", MON, date_format="YYYY-MM-DD")

    def test_add_months_clamps_to_the_month_end(self):
        self.assertEqual(add_months(dt.date(2026, 1, 31), 1), dt.date(2026, 2, 28))
        self.assertEqual(add_months(dt.date(2028, 1, 31), 1), dt.date(2028, 2, 29))
        self.assertEqual(add_months(dt.date(2026, 11, 15), 3), dt.date(2027, 2, 15))
        self.assertEqual(add_months(dt.date(2026, 3, 31), -1), dt.date(2026, 2, 28))


class TimeTest(unittest.TestCase):
    def test_times(self):
        self.assertEqual(parse_time("18:30"), dt.time(18, 30))
        self.assertEqual(parse_time("6:30pm"), dt.time(18, 30))
        self.assertEqual(parse_time("6 PM"), dt.time(18, 0))
        self.assertEqual(parse_time("12am"), dt.time(0, 0))
        self.assertEqual(parse_time("12pm"), dt.time(12, 0))
        self.assertEqual(parse_time("0730"), dt.time(7, 30))
        self.assertEqual(parse_time("noon"), dt.time(12, 0))
        for bad in ("25:00", "13pm", "half six"):
            with self.assertRaises(ToolError):
                parse_time(bad)

    def test_quiet_hours(self):
        self.assertEqual(parse_hours_range("21:00-07:00"), ("21:00", "07:00"))
        self.assertEqual(parse_hours_range("9pm to 7am"), ("21:00", "07:00"))
        self.assertTrue(in_window(dt.time(6, 59), "21:00", "07:00"))
        self.assertFalse(in_window(dt.time(7, 0), "21:00", "07:00"))
        self.assertTrue(in_window(dt.time(13, 0), "12:00", "14:00"))
        with self.assertRaises(ToolError):
            parse_hours_range("21:00-21:00")


class MatchTest(unittest.TestCase):
    ITEMS = [
        {"id": "L1", "name": "Household Tasks"},
        {"id": "L2", "name": "My Tasks"},
        {"id": "L3", "name": "Groceries"},
    ]

    def test_id_exact_prefix_and_word(self):
        self.assertEqual(match_one(self.ITEMS, "l3", "list")["name"], "Groceries")
        self.assertEqual(match_one(self.ITEMS, "groceries", "list")["id"], "L3")
        self.assertEqual(match_one(self.ITEMS, "groc", "list")["id"], "L3")
        self.assertEqual(match_one(self.ITEMS, "household", "list")["id"], "L1")

    def test_ambiguous_and_missing(self):
        with self.assertRaises(ToolError) as cm:
            match_one(self.ITEMS, "tasks", "list")
        self.assertEqual(cm.exception.code, "ambiguous")
        self.assertEqual(len(cm.exception.extra["candidates"]), 2)
        with self.assertRaises(ToolError) as cm:
            match_one(self.ITEMS, "garden", "list")
        self.assertEqual(cm.exception.code, "not_found")

    def test_fold(self):
        self.assertEqual(fold("  Zoë   Ann "), "zoe ann")


if __name__ == "__main__":
    unittest.main()
