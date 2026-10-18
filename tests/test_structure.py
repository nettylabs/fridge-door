"""Package checks. Run from the plugin folder: python3 -m unittest discover -s tests"""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = (".grok-plugin/plugin.json", ".cursor-plugin/plugin.json", ".claude-plugin/plugin.json")


class PackageTest(unittest.TestCase):
    def test_manifests_agree_on_name_and_version(self):
        data = [json.loads((ROOT / rel).read_text(encoding="utf-8")) for rel in MANIFESTS]
        self.assertEqual({d["name"] for d in data}, {"fridge-door"})
        self.assertEqual(len({d["version"] for d in data}), 1, "versions differ between manifests")

    def test_skill_version_matches_manifests(self):
        version = json.loads((ROOT / MANIFESTS[0]).read_text(encoding="utf-8"))["version"]
        skill = (ROOT / "skills" / "fridge-door" / "SKILL.md").read_text(encoding="utf-8")
        self.assertRegex(skill, r'(?m)^\s+version:\s*"?' + re.escape(version) + r'"?\s*$')

    def test_paths_in_cursor_manifest_exist(self):
        cursor = json.loads((ROOT / ".cursor-plugin/plugin.json").read_text(encoding="utf-8"))
        for key in ("logo", "skills", "commands"):
            if cursor.get(key):
                self.assertTrue((ROOT / cursor[key]).exists(), f"{key}: {cursor[key]} is missing")


if __name__ == "__main__":
    unittest.main()
