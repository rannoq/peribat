"""Xbox compatible controllers, through the XInput API."""
from __future__ import annotations

import ctypes
import logging
from typing import List, Optional

from ..model import Reading

KEY = "xbox"
LABEL = "Xbox controllers"

log = logging.getLogger(__name__)

# XInput only reports four steps: empty, low, medium, full.
LEVELS = (10, 33, 66, 100)
BATTERY_TYPE_DISCONNECTED = 0
BATTERY_TYPE_WIRED = 1
DEVTYPE_GAMEPAD = 0


class BatteryInformation(ctypes.Structure):
    _fields_ = (("battery_type", ctypes.c_ubyte), ("battery_level", ctypes.c_ubyte))


def _load() -> Optional[ctypes.WinDLL]:
    for dll in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
        try:
            return ctypes.WinDLL(dll)
        except OSError:
            continue
    return None


def describe(battery_type: int, battery_level: int) -> Optional[int]:
    """Battery percentage, or None for a controller that is disconnected or wired."""
    if battery_type in (BATTERY_TYPE_DISCONNECTED, BATTERY_TYPE_WIRED):
        return None
    return LEVELS[min(battery_level, len(LEVELS) - 1)]


def scan() -> List[Reading]:
    xinput = _load()
    if xinput is None:
        return []
    readings = []
    for user in range(4):
        info = BatteryInformation()
        if xinput.XInputGetBatteryInformation(user, DEVTYPE_GAMEPAD, ctypes.byref(info)) != 0:
            continue
        level = describe(info.battery_type, info.battery_level)
        if level is not None:
            readings.append(Reading(f"Xbox controller {user + 1}", level, False, "gamepad", KEY))
    return readings
