"""Razer wireless mice, keyboards and their dongles.

Razer devices answer a 90 byte feature report on their control interface. The
battery level is command class 0x07, command 0x80 (0-255 in the second
argument) and the charging state is command 0x84. Devices disagree on the
transaction id, so a few are tried. The framing follows the OpenRazer driver.
"""
from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional

from ..kinds import guess_kind
from ..model import Reading
from . import _hid

KEY = "razer"
LABEL = "Razer"

log = logging.getLogger(__name__)

VENDOR_ID = 0x1532
REPORT_SIZE = 90
TRANSACTION_IDS = (0x1F, 0x3F, 0xFF)
STATUS_SUCCESS = 0x02
CLASS_POWER = 0x07
CMD_BATTERY_LEVEL = 0x80
CMD_CHARGING = 0x84
REPLY_DELAY = 0.04
DEAD_FOR = 600  # seconds before an interface that never answered is tried again

_working: Dict[int, tuple] = {}   # product id -> (path, transaction id)
_dead: Dict[int, float] = {}      # product id -> time it last failed


def build_report(transaction_id: int, command_class: int, command_id: int, data_size: int = 2) -> bytes:
    report = bytearray(REPORT_SIZE)
    report[1] = transaction_id
    report[5] = data_size
    report[6] = command_class
    report[7] = command_id
    crc = 0
    for byte in report[2:88]:
        crc ^= byte
    report[88] = crc
    return bytes(report)


def parse_reply(reply: bytes, command_class: int, command_id: int) -> Optional[bytes]:
    """Arguments of a successful reply to the given command, otherwise None."""
    if len(reply) == REPORT_SIZE + 1:  # leading report id
        reply = reply[1:]
    if len(reply) < REPORT_SIZE or reply[0] != STATUS_SUCCESS:
        return None
    if reply[6] != command_class or reply[7] != command_id:
        return None
    return bytes(reply[8:88])


def _query(device, transaction_id: int, command_id: int) -> Optional[bytes]:
    request = build_report(transaction_id, CLASS_POWER, command_id)
    device.send_feature_report(b"\x00" + request)
    time.sleep(REPLY_DELAY)
    reply = bytes(device.get_feature_report(0, REPORT_SIZE + 1))
    return parse_reply(reply, CLASS_POWER, command_id)


def _read(device, transaction_ids) -> Optional[tuple]:
    for transaction_id in transaction_ids:
        args = _query(device, transaction_id, CMD_BATTERY_LEVEL)
        if args is None:
            continue
        level = round(args[1] * 100 / 255)
        charging_args = _query(device, transaction_id, CMD_CHARGING)
        charging = bool(charging_args and charging_args[1])
        return level, charging, transaction_id
    return None


def scan() -> List[Reading]:
    by_product: Dict[int, List[dict]] = {}
    for info in _hid.enumerate_vendor(VENDOR_ID):
        by_product.setdefault(info["product_id"], []).append(info)

    found: Dict[str, Reading] = {}
    now = time.monotonic()
    for product_id, interfaces in by_product.items():
        if now - _dead.get(product_id, -DEAD_FOR) < DEAD_FOR:
            continue
        known = _working.get(product_id)
        ordered = sorted(interfaces, key=lambda i: i["path"] != (known[0] if known else None))
        result = None
        for info in ordered:
            tids = (known[1],) if known and known[0] == info["path"] else TRANSACTION_IDS
            try:
                with _hid.open_path(info["path"]) as device:
                    result = _read(device, tids)
            except Exception:
                log.debug("razer: interface %r failed", info["path"], exc_info=True)
                continue
            if result:
                _working[product_id] = (info["path"], result[2])
                break
        if not result:
            _dead[product_id] = now  # wired devices and the like have no battery to read
            _working.pop(product_id, None)
            continue
        level, charging, _ = result
        product = ordered[0].get("product_string") or ""
        name = _hid.clean_name(product, "Razer device")
        if level == 0 and not charging:
            continue  # reported while the wireless device is switched off
        found[name] = Reading(name, level, charging, guess_kind(name), KEY)
    return list(found.values())
