"""Toolkit tests. Run from the plugin folder: python3 -m unittest discover -s tests"""

import json
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "skills" / "fridge-door" / "scripts" / "fridge.py"
sys.path.insert(0, str(CLI.parent))

from fridgedoor import money  # noqa: E402
from fridgedoor.util import ToolError, load_spec  # noqa: E402


def run(*args, home=None):
    cmd = [sys.executable, str(CLI)] + (["--home", str(home)] if home else []) + list(args)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, json.loads(proc.stdout)


class ToolkitTest(unittest.TestCase):
    def test_selftest_passes(self):
        code, out = run("selftest")
        self.assertEqual(code, 0, out)
        self.assertTrue(out["ok"])

    def test_doctor_on_an_empty_folder(self):
        with tempfile.TemporaryDirectory() as home:
            code, out = run("doctor", home=home)
            self.assertEqual(code, 0, out)
            self.assertFalse(out["initialized"])
            self.assertTrue(out["setup"]["missing"])

    def test_demo_then_doctor(self):
        with tempfile.TemporaryDirectory() as home:
            self.assertEqual(run("demo", home=home)[0], 0)
            code, out = run("doctor", home=home)
            self.assertTrue(out["initialized"])

    def test_demo_refuses_a_folder_with_data(self):
        with tempfile.TemporaryDirectory() as home:
            run("demo", home=home)
            code, out = run("demo", home=home)
            self.assertEqual(code, 1)
            self.assertEqual(out["code"], "not_empty")
            self.assertIn("hint", out)

    def test_usage_mistakes_are_json(self):
        code, out = run("no-such-command")
        self.assertEqual(code, 2)
        self.assertFalse(out["ok"])
        self.assertIn("--help", out["hint"])


class MoneyTest(unittest.TestCase):
    def test_splits_add_up_to_the_cent(self):
        self.assertEqual(
            money.allocate("100.00", [1, 1, 1], "USD"), [Decimal("33.34"), Decimal("33.33"), Decimal("33.33")]
        )
        self.assertEqual(sum(money.allocate("-10.00", [1, 2], "USD")), Decimal("-10.00"))
        self.assertEqual(money.allocate(1000, [1, 1, 1], "JPY"), [334, 333, 333])

    def test_currency_places(self):
        self.assertEqual((money.places("JPY"), money.places("KWD"), money.places("cad")), (0, 3, 2))
        self.assertEqual(money.quantize("2.005", "USD"), Decimal("2.01"))

    def test_strict_numbers(self):
        self.assertEqual(money.to_decimal("$1234.50"), Decimal("1234.50"))
        self.assertEqual(money.to_decimal("19.99 EUR"), Decimal("19.99"))
        for text in ("1,500", "1.234,50", "", "twelve"):
            with self.assertRaises(ToolError):
                money.to_decimal(text)

    def test_cash_rounding(self):
        self.assertEqual(money.cash_round("12.37", "0.05"), Decimal("12.35"))
        self.assertEqual(money.cash_round("12.38", "0.05"), Decimal("12.40"))

    def test_spec_numbers_stay_exact(self):
        self.assertEqual(load_spec('{"tips": 0.1}')["tips"], Decimal("0.1"))
        with self.assertRaises(ToolError):
            load_spec("{not json")


if __name__ == "__main__":
    unittest.main()
