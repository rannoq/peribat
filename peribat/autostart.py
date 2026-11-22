"""Start with Windows, through the current user's Run key."""
from __future__ import annotations

import logging
import sys
import winreg
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "peribat"
LAUNCHER = Path(__file__).resolve().parent.parent / "peribat.pyw"


def command() -> str:
    python = Path(sys.executable)
    if python.name.lower() == "python.exe":
        python = python.with_name("pythonw.exe")
    return f'"{python}" "{LAUNCHER}"'


def _registered() -> Optional[str]:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            return winreg.QueryValueEx(key, VALUE_NAME)[0]
    except FileNotFoundError:
        return None


def is_enabled() -> bool:
    return _registered() is not None


def set_enabled(on: bool) -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if on:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command())
            else:
                try:
                    winreg.DeleteValue(key, VALUE_NAME)
                except FileNotFoundError:
                    pass
    except OSError:
        log.warning("could not change the autostart entry", exc_info=True)


def repair() -> None:
    """Point an existing entry at this installation, in case the folder or Python changed."""
    registered = _registered()
    if registered is not None and registered != command():
        set_enabled(True)
