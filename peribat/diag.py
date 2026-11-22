"""``python -m peribat --diag``: what Windows shows, and what every source makes of it."""
from __future__ import annotations

import logging
import platform
import time
import traceback

from . import __version__, sources
from .sources import _hid

VENDORS = {0x046D: "Logitech", 0x1532: "Razer", 0x1038: "SteelSeries", 0x1B1C: "Corsair"}


def run() -> int:
    logging.basicConfig(level=logging.DEBUG, format="  [%(name)s] %(message)s")
    print(f"peribat {__version__}, Python {platform.python_version()}, {platform.platform()}")
    print(f"hidapi: {'available' if _hid.available() else 'NOT installed'}\n")

    for vendor_id, name in VENDORS.items():
        interfaces = _hid.enumerate_vendor(vendor_id)
        print(f"== {name} HID interfaces ({len(interfaces)})")
        for info in interfaces:
            print(f"  pid=0x{info['product_id']:04x} {info.get('product_string')!r} "
                  f"usage_page=0x{info.get('usage_page', 0):04x} usage=0x{info.get('usage', 0):x} "
                  f"interface={info.get('interface_number')}")
        print()

    for source in sources.ALL:
        print(f"== {source.LABEL}")
        started = time.monotonic()
        try:
            readings = source.scan()
        except Exception:
            print(traceback.format_exc())
            continue
        took = time.monotonic() - started
        if not readings:
            print(f"  nothing found ({took:.1f}s)")
        for reading in readings:
            charging = ", charging" if reading.charging else ""
            print(f"  {reading.name}: {reading.level}%{charging} [{reading.kind}] ({took:.1f}s)")
        print()
    return 0
