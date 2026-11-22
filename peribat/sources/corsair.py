"""Corsair Void family wireless headsets.

The headset answers a vendor specific HID report with the battery level and a
status byte. The byte layout follows the protocol notes of the HeadsetControl
project.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from ..model import Reading
from . import _hid

KEY = "corsair"
LABEL = "Corsair"

log = logging.getLogger(__name__)

VENDOR_ID = 0x1B1C
PRODUCTS = frozenset({0x1B1C, 0x1B27, 0x0A14, 0x0A16, 0x0A17, 0x0A1D, 0x0A1A, 0x1B2A, 0x1B23,
                      0x1B29, 0x0A55, 0x0A51, 0x0A52, 0x0A38, 0x0A4F, 0x0A2B, 0x0A75, 0x0A56})
USAGE = (0xFFC5, 0x0001, 3)  # usage page, usage, interface
TIMEOUT_MS = 1000
MIC_UP_FLAG = 0x80


def parse(reply: bytes) -> Optional[Tuple[int, bool]]:
    """Level in byte 2 (bit 7 is the microphone), status in byte 4."""
    if len(reply) < 5:
        return None
    status = reply[4]
    if status not in (1, 2, 4, 5):  # 0: headset not connected to the receiver
        return None
    level = reply[2] & ~MIC_UP_FLAG
    if level > 100:
        return None
    return level, status in (4, 5)


def scan() -> List[Reading]:
    found = {}
    for info in _hid.enumerate_vendor(VENDOR_ID):
        wanted = (info.get("usage_page"), info.get("usage"), info.get("interface_number"))
        if info["product_id"] not in PRODUCTS or wanted != USAGE:
            continue
        try:
            with _hid.open_path(info["path"]) as device:
                _hid.drain(device)
                device.write(bytes((0xC9, 0x64)))
                result = parse(bytes(device.read(5, TIMEOUT_MS)))
        except Exception:
            log.debug("corsair: %r failed", info["path"], exc_info=True)
            continue
        if result:
            name = _hid.clean_name(info.get("product_string") or "", "Corsair headset")
            found[name] = Reading(name, result[0], result[1], "headset", KEY)
    return list(found.values())
