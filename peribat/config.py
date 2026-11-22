"""User settings, stored as JSON in %APPDATA%\\peribat\\settings.json."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict

log = logging.getLogger(__name__)

DEFAULTS: Dict[str, Any] = {
    # widget
    "show_widget": True,
    "attach_taskbar": True,
    "mode": "lowest",              # "lowest" or "all"
    "show_icon": True,
    "show_percent": True,
    "show_charging": True,
    "font_size": 10,
    "bold": True,
    "x_offset": 0,
    "y_offset": 0,
    "gap": 10,
    "hidden": [],                  # device names that are never shown
    # colours
    "color_mode": "level",         # "level" or "fixed"
    "fixed_color": "#ffffff",
    "color_good": "#4cc38a",
    "color_mid": "#f0a830",
    "color_low": "#ee5f5b",
    "mid_pct": 40,
    "low_pct": 15,
    "icon_follows_text": True,
    "icon_color": "#ffffff",
    # behaviour
    "notify": True,
    "notify_pct": 15,
    "refresh_seconds": 60,
    "sources_off": [],             # names of sources that are switched off
    "first_run_done": False,
}


def default_path() -> Path:
    return Path(os.environ.get("APPDATA") or Path.home()) / "peribat" / "settings.json"


class Settings:
    """Dictionary-like settings that save themselves on every change."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else default_path()
        self._data = self._defaults()
        self._load()

    @staticmethod
    def _defaults() -> Dict[str, Any]:
        return {k: (list(v) if isinstance(v, list) else v) for k, v in DEFAULTS.items()}

    def _load(self) -> None:
        try:
            raw = json.loads(self.path.read_text("utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError) as exc:
            log.warning("settings unreadable (%s), using defaults", exc)
            return
        if not isinstance(raw, dict):
            return
        for key, default in DEFAULTS.items():
            if key in raw and type(raw[key]) is type(default):
                self._data[key] = raw[key]

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._data, indent=2), "utf-8")
            os.replace(tmp, self.path)
        except OSError as exc:
            log.warning("could not save settings: %s", exc)

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        if key not in DEFAULTS:
            raise KeyError(key)
        self._data[key] = value
        self.save()

    def reset(self) -> None:
        done = self._data["first_run_done"]
        self._data = self._defaults()
        self._data["first_run_done"] = done
        self.save()
