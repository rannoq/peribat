"""Logitech devices over HID++ 2.0 (Lightspeed, Unifying and Bolt receivers, or wired)."""
from __future__ import annotations

import logging
import time
from typing import List, Optional, Tuple

from ..kinds import guess_kind
from ..model import Reading
from . import _hid

KEY = "logitech"
LABEL = "Logitech"

log = logging.getLogger(__name__)

VENDOR_ID = 0x046D
SW_ID = 0x07  # echoed back in replies, tells them apart from notifications

F_ROOT = 0x0000
F_DEVICE_NAME = 0x0005
F_BATTERY_STATUS = 0x1000
F_BATTERY_VOLTAGE = 0x1001
F_UNIFIED_BATTERY = 0x1004

# device type reported by feature 0x0005 -> icon kind
_TYPE_KINDS = {0: "keyboard", 2: "keyboard", 3: "mouse", 4: "mouse", 5: "mouse",
               8: "headset", 11: "gamepad", 12: "gamepad", 14: "speaker", 17: "gamepad"}

# Rough LiPo discharge curve for devices that only report their voltage.
_VOLTAGE_CURVE = ((4186, 100), (4067, 90), (3989, 80), (3922, 70), (3859, 60), (3811, 50),
                  (3778, 40), (3751, 30), (3717, 20), (3671, 10), (3636, 5), (3500, 0))


class Channel:
    """Long (20 byte) HID++ reports over one receiver interface."""

    def __init__(self, device) -> None:
        self.device = device

    def request(self, index: int, feature: int, function: int,
                params: bytes = b"", timeout: float = 0.6) -> Optional[bytes]:
        """Send one request and return the reply parameters, or None (error or no answer)."""
        header = (function << 4) | SW_ID
        message = bytearray(20)
        message[0:4] = bytes((0x11, index, feature, header))
        message[4:4 + len(params)] = params
        self.device.write(bytes(message))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            reply = self.device.read(20, 100)
            if not reply:
                continue
            reply = bytes(reply)
            if len(reply) < 5 or reply[1] != index:
                continue
            if reply[2] == 0x8F:                         # HID++ 1.0 error
                return None
            if reply[2] == 0xFF and reply[3] == feature:  # HID++ 2.0 error
                return None
            if reply[2] == feature and reply[3] == header:
                return reply[4:]
        return None

    def ping(self, index: int) -> bool:
        """True if something answers at this index (an empty slot or a sleeping device does not)."""
        return self.request(index, F_ROOT, 1, b"\x00\x00\x5a") is not None

    def feature_index(self, index: int, feature_id: int) -> Optional[int]:
        reply = self.request(index, F_ROOT, 0, feature_id.to_bytes(2, "big"))
        return reply[0] if reply and reply[0] else None


def voltage_to_percent(millivolt: int) -> int:
    for volts, percent in _VOLTAGE_CURVE:
        if millivolt >= volts:
            return percent
    return 0


def decode_unified(params: bytes) -> Tuple[int, bool]:
    """Feature 0x1004 GetStatus: state of charge, flags, charging state."""
    return params[0], params[2] in (1, 2)


def decode_status(params: bytes) -> Tuple[int, bool]:
    """Feature 0x1000 GetBatteryLevelStatus: level, next level, status."""
    return params[0], params[2] in (1, 2, 4)


def decode_voltage(params: bytes) -> Tuple[int, bool]:
    """Feature 0x1001 GetBatteryVoltage: millivolt, flags."""
    return voltage_to_percent((params[0] << 8) | params[1]), bool(params[2] & 0x80)


# (feature, function that returns the status, decoder)
_BATTERY_FEATURES = ((F_UNIFIED_BATTERY, 1, decode_unified),
                     (F_BATTERY_STATUS, 0, decode_status),
                     (F_BATTERY_VOLTAGE, 0, decode_voltage))


def read_battery(channel: Channel, index: int) -> Optional[Tuple[int, bool]]:
    for feature_id, function, decode in _BATTERY_FEATURES:
        slot = channel.feature_index(index, feature_id)
        if slot is None:
            continue
        params = channel.request(index, slot, function)
        if params:
            return decode(params)
    return None


def identify(channel: Channel, index: int) -> Tuple[Optional[str], Optional[str]]:
    """Name and icon kind of a device, from the device name feature."""
    slot = channel.feature_index(index, F_DEVICE_NAME)
    if slot is None:
        return None, None
    count = channel.request(index, slot, 0)
    name = None
    if count:
        total, raw = count[0], b""
        while len(raw) < total and len(raw) < 64:
            chunk = channel.request(index, slot, 1, bytes((len(raw),)))
            if not chunk:
                break
            raw += chunk.split(b"\x00")[0] if b"\x00" in chunk else chunk
            if b"\x00" in chunk:
                break
        name = raw[:total].decode("ascii", "replace") or None
    kind_reply = channel.request(index, slot, 2)
    return name, (_TYPE_KINDS.get(kind_reply[0]) if kind_reply else None)


def read_device(channel: Channel, index: int) -> Optional[Reading]:
    if not channel.ping(index):  # empty slot, or the device is asleep
        return None
    battery = read_battery(channel, index)
    if battery is None:
        return None
    name, kind = identify(channel, index)
    name = name or f"Logitech device {index}"
    return Reading(name, battery[0], battery[1], kind or guess_kind(name), KEY)


def scan() -> List[Reading]:
    found = {}
    seen_paths = set()
    for info in _hid.enumerate_vendor(VENDOR_ID):
        # the long-report collection of the vendor specific interface
        if info.get("usage_page") != 0xFF00 or info.get("usage") != 2:
            continue
        path = info["path"]
        if path in seen_paths:
            continue
        seen_paths.add(path)
        try:
            with _hid.open_path(path) as device:
                channel = Channel(device)
                for index in (1, 2, 3, 4, 5, 6, 0xFF):  # receiver slots, then a wired device
                    try:
                        reading = read_device(channel, index)
                    except Exception:
                        log.debug("logitech: index %d failed", index, exc_info=True)
                        continue
                    if reading:
                        found[reading.name] = reading
        except OSError:
            log.debug("logitech: could not open %r", path, exc_info=True)
    return list(found.values())
