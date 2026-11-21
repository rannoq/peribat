"""Persistent user settings, stored as JSON in %APPDATA%\\peribat\\settings.json."""
import json
import os
from pathlib import Path

DEFAULTS = {
    # display
    "show_widget": True,
    "attach_taskbar": True,    # child window of the taskbar: stays visible with Start menu open
    "mode": "lowest",          # "lowest" or "all"
    "show_icon": True,
    "show_percent": True,
    "show_charging": True,
    "font_size": 10,
    "bold": True,
    "x_offset": 0,
    "y_offset": 0,
    "gap": 10,
    "hidden": [],              # device names that are never shown
    # colors
    "color_mode": "level",     # "level" or "fixed"
    "fixed_color": "#ffffff",
    "color_good": "#4cc38a",
    "color_mid": "#f0a830",
    "color_low": "#ee5f5b",
    "mid_pct": 40,
    "low_pct": 15,
    "icon_follows_text": True,
    "icon_color": "#ffffff",
    # behavior
    "notify": True,
    "notify_pct": 15,
    "refresh_seconds": 60,
    "first_run_done": False,
}

PATH = Path(os.environ.get("APPDATA") or Path.home()) / "peribat" / "settings.json"


class Settings:
    def __init__(self, path=PATH):
        self.path = Path(path)
        self.data = self._fresh()
        self.load()

    @staticmethod
    def _fresh():
        return {k: (list(v) if isinstance(v, list) else v) for k, v in DEFAULTS.items()}

    def load(self):
        try:
            raw = json.loads(self.path.read_text("utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(raw, dict):
            return
        for key, default in DEFAULTS.items():
            if key in raw and type(raw[key]) is type(default):
                self.data[key] = raw[key]

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, indent=2), "utf-8")
            os.replace(tmp, self.path)
        except OSError:
            pass

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value
        self.save()

    def reset(self):
        done = self.data["first_run_done"]
        self.data = self._fresh()
        self.data["first_run_done"] = done
        self.save()
