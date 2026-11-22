import json
import tempfile
import unittest
from pathlib import Path

from peribat.config import DEFAULTS, Settings


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "settings.json"

    def tearDown(self):
        self.dir.cleanup()

    def test_defaults(self):
        cfg = Settings(self.path)
        for key, value in DEFAULTS.items():
            self.assertEqual(cfg[key], value)

    def test_changes_are_saved_and_reloaded(self):
        cfg = Settings(self.path)
        cfg["font_size"] = 14
        cfg["hidden"] = ["Some device"]
        again = Settings(self.path)
        self.assertEqual(again["font_size"], 14)
        self.assertEqual(again["hidden"], ["Some device"])

    def test_wrong_types_fall_back_to_defaults(self):
        self.path.write_text(json.dumps({"font_size": "huge", "bold": False, "unknown": 1}))
        cfg = Settings(self.path)
        self.assertEqual(cfg["font_size"], DEFAULTS["font_size"])
        self.assertFalse(cfg["bold"])

    def test_broken_file_is_ignored(self):
        self.path.write_text("{not json")
        self.assertEqual(Settings(self.path)["gap"], DEFAULTS["gap"])

    def test_unknown_key_is_rejected(self):
        with self.assertRaises(KeyError):
            Settings(self.path)["nope"] = 1

    def test_defaults_are_not_shared(self):
        cfg = Settings(self.path)
        cfg["hidden"].append("x")
        self.assertEqual(DEFAULTS["hidden"], [])

    def test_reset_keeps_first_run_flag(self):
        cfg = Settings(self.path)
        cfg["first_run_done"] = True
        cfg["font_size"] = 20
        cfg.reset()
        self.assertEqual(cfg["font_size"], DEFAULTS["font_size"])
        self.assertTrue(cfg["first_run_done"])


if __name__ == "__main__":
    unittest.main()
