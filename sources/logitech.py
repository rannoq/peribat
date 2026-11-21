"""Battery levels of Logitech wireless devices (HID++ 2.0).

Works for devices behind a Lightspeed / Unifying / Bolt receiver, and for
Logitech devices connected directly by cable. Talks to the receiver's
vendor-specific HID interface using long (20 byte) reports.
"""
import time

try:
    import hid  # pip install hidapi
except ImportError:  # the app still works with Bluetooth only
    hid = None

DEBUG = False  # set True (diag.py does) to print raw traffic


def _log(*args):
    if DEBUG:
        print("   [hid++]", *args)


VENDOR_ID = 0x046D
SW_ID = 0x07  # arbitrary software id, echoed back in replies

F_DEVICE_NAME = 0x0005
F_BATTERY_STATUS = 0x1000
F_BATTERY_VOLTAGE = 0x1001
F_UNIFIED_BATTERY = 0x1004

# Rough LiPo discharge curve (mV -> %), used only for devices that report
# voltage instead of a percentage. Approximate.
VOLT_TABLE = [(4186, 100), (4067, 90), (3989, 80), (3922, 70), (3859, 60),
              (3811, 50), (3778, 40), (3751, 30), (3717, 20), (3671, 10),
              (3636, 5), (3500, 0)]


class Channel:
    def __init__(self, dev):
        self.dev = dev

    def request(self, index, feature, func, params=b"", timeout=0.6):
        """Send one HID++ 2.0 request, return the reply parameters or None."""
        msg = bytearray(20)
        msg[0] = 0x11
        msg[1] = index
        msg[2] = feature
        msg[3] = (func << 4) | SW_ID
        msg[4:4 + len(params)] = params
        _log("->", bytes(msg[:8]).hex())
        self.dev.write(bytes(msg))
        end = time.time() + timeout
        while time.time() < end:
            r = self.dev.read(20, 100)
            if not r:
                continue
            r = bytes(r)
            _log("<-", r[:8].hex())
            if len(r) < 5 or r[1] != index:
                continue
            if r[2] == 0x8F:                      # HID++ 1.0 error (e.g. device offline)
                return None
            if r[2] == 0xFF and r[3] == feature:  # HID++ 2.0 error
                return None
            if r[2] == feature and r[3] == ((func << 4) | SW_ID):
                return r[4:]
        return None


def find_feature(ch, index, feature_id):
    # IRoot: function 0 = GetFeature(featureId), function 1 = Ping
    r = ch.request(index, 0x00, 0, bytes([feature_id >> 8, feature_id & 0xFF]))
    return r[0] if r and r[0] else None


def device_name(ch, index):
    fi = find_feature(ch, index, F_DEVICE_NAME)
    if fi is None:
        return None
    r = ch.request(index, fi, 0)
    if not r:
        return None
    total, name = r[0], b""
    while len(name) < total and len(name) < 64:
        chunk = ch.request(index, fi, 1, bytes([len(name)]))
        if not chunk:
            break
        name += chunk.split(b"\x00")[0] if b"\x00" in chunk else chunk
        if b"\x00" in chunk:
            break
    return name[:total].decode("ascii", "replace") or None


# HID++ device type codes (feature 0x0005, function 2) -> icon kind
TYPE_KINDS = {0: "keyboard", 2: "keyboard", 3: "mouse", 4: "mouse", 5: "mouse",
              8: "headset", 11: "gamepad", 12: "gamepad", 14: "speaker", 17: "gamepad"}


def device_kind(ch, index):
    fi = find_feature(ch, index, F_DEVICE_NAME)
    if fi is None:
        return None
    r = ch.request(index, fi, 2)
    return TYPE_KINDS.get(r[0]) if r else None


def volt_to_percent(mv):
    for volts, pct in VOLT_TABLE:
        if mv >= volts:
            return pct
    return 0


def read_battery(ch, index):
    """Return (percent, charging) or None."""
    fi = find_feature(ch, index, F_UNIFIED_BATTERY)
    if fi is not None:
        r = ch.request(index, fi, 1)  # GetStatus
        if r:
            return r[0], r[2] in (1, 2)
    fi = find_feature(ch, index, F_BATTERY_STATUS)
    if fi is not None:
        r = ch.request(index, fi, 0)
        if r:
            return r[0], r[2] in (1, 2, 4)
    fi = find_feature(ch, index, F_BATTERY_VOLTAGE)
    if fi is not None:
        r = ch.request(index, fi, 0)
        if r:
            mv = (r[0] << 8) | r[1]
            return volt_to_percent(mv), bool(r[2] & 0x80)
    return None


def read():
    """Return a list of (name, level_percent, charging, kind_or_None)."""
    if hid is None:
        return []
    found, seen_paths = {}, set()
    try:
        infos = hid.enumerate(VENDOR_ID, 0)
    except Exception:
        return []
    for info in infos:
        # long-report collection of the vendor-specific interface
        if info.get("usage_page") != 0xFF00 or info.get("usage") != 2:
            continue
        path = info["path"]
        if path in seen_paths:
            continue
        seen_paths.add(path)
        dev = hid.device()
        try:
            dev.open_path(path)
        except OSError as e:
            _log("open failed:", e)
            continue
        _log("opened", info.get("product_string"), path)
        try:
            ch = Channel(dev)
            for index in (1, 2, 3, 4, 5, 6, 0xFF):
                _log("-- device index", index)
                try:
                    batt = read_battery(ch, index)
                    if batt is None:
                        continue
                    name = device_name(ch, index) or f"Logitech device {index}"
                    found[name] = (batt[0], batt[1], device_kind(ch, index))
                except Exception as e:
                    _log("error at index", index, repr(e))
                    continue
        finally:
            dev.close()
    return [(n, l, c, k) for n, (l, c, k) in found.items()]
