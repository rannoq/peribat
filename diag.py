"""Diagnostics for peribat. Run: py -3.13 diag.py"""
import sys
from sources import bluetooth, logitech

logitech.DEBUG = True
print("Python:", sys.version.split()[0])
print()

print("== Logitech HID interfaces ==")
if logitech.hid is None:
    print("hidapi is not installed for this Python")
else:
    infos = logitech.hid.enumerate(logitech.VENDOR_ID, 0)
    if not infos:
        print("No Logitech HID devices found at all")
    for d in infos:
        print(
            repr(d.get("product_string")),
            "usage_page=", hex(d.get("usage_page", 0)),
            "usage=", hex(d.get("usage", 0)),
            "interface=", d.get("interface_number"),
        )
    print()
    print("== Logitech battery read ==")
    print(logitech.read() or "nothing returned")

print()
print("== Bluetooth battery read ==")
print(bluetooth.read() or "nothing returned")
