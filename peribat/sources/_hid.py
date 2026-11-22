"""Thin helpers around the optional ``hidapi`` package."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Dict, Iterator, List

try:
    import hid  # pip install hidapi
except ImportError:  # HID based sources then report nothing
    hid = None

log = logging.getLogger(__name__)


def available() -> bool:
    return hid is not None


def enumerate_vendor(vendor_id: int) -> List[Dict]:
    if hid is None:
        return []
    try:
        return list(hid.enumerate(vendor_id, 0))
    except Exception:  # driver problems must never break a scan
        log.debug("hid.enumerate(0x%04x) failed", vendor_id, exc_info=True)
        return []


@contextmanager
def open_path(path: bytes) -> Iterator["hid.device"]:
    device = hid.device()
    device.open_path(path)
    try:
        yield device
    finally:
        device.close()


def drain(device, limit: int = 8) -> None:
    """Throw away reports that are already waiting, so a reply is not confused with them."""
    for _ in range(limit):
        if not device.read(64, 0):
            return


def clean_name(product: str, fallback: str) -> str:
    """Product string of a dongle or receiver, without the dongle part."""
    name = (product or "").strip()
    for suffix in ("Wireless Receiver", "Wireless Dongle", "Receiver", "Dongle"):
        if name.lower().endswith(suffix.lower()):
            name = name[: -len(suffix)].strip()
    return name or fallback
