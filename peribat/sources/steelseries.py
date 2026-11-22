"""SteelSeries Arctis wireless headsets (Arctis 7 / Pro and Arctis Nova 7 families).

Both families answer a vendor specific HID report on one interface. The byte
layouts follow the protocol notes of the HeadsetControl project.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from ..model import Reading
from . import _hid

KEY = "steelseries"
LABEL = "SteelSeries"

log = logging.getLogger(__name__)

VENDOR_ID = 0x1038
TIMEOUT_MS = 1000

LEGACY_PRODUCTS = frozenset({0x1260, 0x12AD, 0x1252, 0x1280})  # Arctis 7, 7 (2019), Pro, Pro GameDAC
LEGACY_USAGE = (0xFF43, 0x0202, 5)                              # usage page, usage, interface

NOVA_DISCRETE = frozenset({0x2202, 0x2206, 0x220A, 0x223A, 0x227A, 0x22A4})  # levels 0-4
NOVA_PERCENT = frozenset({0x22A1, 0x227E, 0x2258, 0x229E, 0x22AD, 0x22A9, 0x22A5, 0x22A7})
NOVA_USAGE = (0xFFC0, 0x0001, 3)


def parse_legacy(reply: bytes) -> Optional[int]:
    """Arctis 7 / Pro: the battery percentage is byte 2 (0 means the headset is off)."""
    if len(reply) < 3 or not 0 < reply[2] <= 100:
        return None
    return reply[2]


def parse_nova(reply: bytes, discrete: bool) -> Optional[Tuple[int, bool]]:
    """Arctis Nova 7: status report 0xB0, level in byte 2, connection state in byte 3."""
    if len(reply) < 4 or reply[0] != 0xB0 or reply[3] == 0:
        return None
    level = reply[2] * 25 if discrete else reply[2]
    return min(level, 100), reply[3] in (1, 2)


def _padded(payload: bytes, size: int) -> bytes:
    return payload + bytes(size - len(payload))


def _read_legacy(device) -> Optional[Tuple[int, bool]]:
    _hid.drain(device)
    device.write(_padded(bytes((0x06, 0x18)), 31))
    level = parse_legacy(bytes(device.read(8, TIMEOUT_MS)))
    return None if level is None else (level, False)


def _read_nova(device, discrete: bool) -> Optional[Tuple[int, bool]]:
    _hid.drain(device)
    device.write(_padded(bytes((0x00, 0xB0)), 64))
    for _ in range(8):  # status reports can arrive on their own, skip other reports
        reply = bytes(device.read(128, TIMEOUT_MS))
        if not reply:
            return None
        if reply[0] == 0xB0:
            return parse_nova(reply, discrete)
    return None


def _matches(info: dict, usage: Tuple[int, int, int]) -> bool:
    return (info.get("usage_page"), info.get("usage"), info.get("interface_number")) == usage


def scan() -> List[Reading]:
    found = {}
    for info in _hid.enumerate_vendor(VENDOR_ID):
        product = info["product_id"]
        if product in LEGACY_PRODUCTS and _matches(info, LEGACY_USAGE):
            read = _read_legacy
        elif product in NOVA_DISCRETE | NOVA_PERCENT and _matches(info, NOVA_USAGE):
            def read(device, discrete=product in NOVA_DISCRETE):
                return _read_nova(device, discrete)
        else:
            continue
        try:
            with _hid.open_path(info["path"]) as device:
                result = read(device)
        except Exception:
            log.debug("steelseries: %r failed", info["path"], exc_info=True)
            continue
        if result:
            name = _hid.clean_name(info.get("product_string") or "", "SteelSeries headset")
            found[name] = Reading(name, result[0], result[1], "headset", KEY)
    return list(found.values())
