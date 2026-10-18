"""Shared test helpers: run the toolkit in-process and read its JSON reply."""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "fridge-door" / "scripts"
CLI = SCRIPTS / "fridge.py"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from fridgedoor import cli  # noqa: E402


def fridge(home, *args, env: dict | None = None):
    """Run `fridge --home <home> <args>`; return (exit code, parsed JSON)."""
    argv = (["--home", str(home)] if home else []) + [str(a) for a in args]
    out = io.StringIO()
    saved = {k: os.environ.get(k) for k in (env or {})}
    os.environ.update(env or {})
    try:
        with contextlib.redirect_stdout(out):
            try:
                cli.main(argv)
                code = 0
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else 1
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    text = out.getvalue()
    try:
        return code, json.loads(text)
    except json.JSONDecodeError:
        raise AssertionError(f"not JSON (exit {code}): {text[:500]}") from None


class HomeTest(unittest.TestCase):
    """A fresh data folder per test, with a fixed clock (Monday 19 Oct 2026, 08:00 local)."""

    NOW = "2026-10-19T08:00:00"

    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="fridge-test-"))
        self._env = os.environ.get("FRIDGE_NOW")
        os.environ["FRIDGE_NOW"] = self.NOW

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)
        if self._env is None:
            os.environ.pop("FRIDGE_NOW", None)
        else:
            os.environ["FRIDGE_NOW"] = self._env

    def ok(self, *args, **kw):
        code, out = fridge(self.home, *args, **kw)
        self.assertEqual(code, 0, out)
        self.assertTrue(out["ok"], out)
        return out

    def err(self, code_name: str, *args, **kw):
        code, out = fridge(self.home, *args, **kw)
        self.assertNotEqual(code, 0, out)
        self.assertEqual(out.get("code"), code_name, out)
        return out

    def setup_family(self, members="Ana, Luis, Sofia (kid), Mateo (teen)", country="CA", name="Test home", *extra):
        return self.ok("setup", "--name", name, "--members", members, "--country", country, *extra)
