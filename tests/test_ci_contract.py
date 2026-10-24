"""Kontrakt obowiązkowej kontroli: żaden rodzaj zmiany nie omija testów."""

import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


class CiContractTest(unittest.TestCase):
    def test_required_check_runs_for_every_pr_and_main_push(self):
        workflow = yaml.load(
            (ROOT / ".github/workflows/check.yml").read_text(encoding="utf-8"),
            Loader=yaml.BaseLoader,
        )
        events = workflow["on"]
        self.assertIn("pull_request", events)
        self.assertFalse(events["pull_request"])
        self.assertEqual(events["push"], {"branches": ["main"]})

        check = workflow["jobs"]["check"]
        self.assertEqual(check["name"], "Kontrola projektu")
        self.assertNotIn("if", check)
        self.assertNotIn("needs", check)
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        runs = [step for step in check["steps"] if step.get("run") == "./scripts/check"]
        self.assertEqual(len(runs), 1)
        self.assertNotIn("if", runs[0])
        self.assertNotIn("continue-on-error", runs[0])
        self.assertNotIn("continue-on-error", check)


if __name__ == "__main__":
    unittest.main()
