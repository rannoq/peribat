"""Run with: python tests/test_logitech.py  (no hardware needed)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sources.logitech import Channel, read_battery, device_name, device_kind, SW_ID


class FakeMouse:
    """Pretends to be a HID++ 2.0 device at index 1 with unified battery."""
    FEATURES = {0x0005: 3, 0x1004: 4}
    NAME = b"PRO X Superlight"

    def __init__(self):
        self.out = []

    def write(self, data):
        _, idx, feat, fs = data[0], data[1], data[2], data[3]
        func, params = fs >> 4, data[4:]
        if idx != 1:
            return
        resp = bytearray(20)
        resp[0], resp[1], resp[3] = 0x11, idx, fs
        if feat == 0x00 and func == 0:
            fid = (params[0] << 8) | params[1]
            resp[2], resp[4] = 0x00, self.FEATURES.get(fid, 0)
        elif feat == 3 and func == 0:
            resp[2], resp[4] = 3, len(self.NAME)
        elif feat == 3 and func == 2:  # device type: mouse
            resp[2], resp[4] = 3, 3
        elif feat == 3 and func == 1:
            off = params[0]
            chunk = self.NAME[off:off + 16]
            resp[2] = 3
            resp[4:4 + len(chunk)] = chunk
        elif feat == 4 and func == 1:
            resp[2], resp[4], resp[5], resp[6] = 4, 73, 0, 1  # 73 %, charging
        elif feat == 0x00 and func == 1:  # ping: protocol 4.2
            resp[2], resp[4], resp[5] = 0x00, 4, 2
        else:
            return
        self.out.append(bytes(resp))

    def read(self, n, timeout):
        return list(self.out.pop(0)) if self.out else []


ch = Channel(FakeMouse())
assert read_battery(ch, 1) == (73, True), read_battery(ch, 1)
assert device_name(ch, 1) == "PRO X Superlight", device_name(ch, 1)
assert device_kind(ch, 1) == "mouse", device_kind(ch, 1)
assert read_battery(Channel(FakeMouse()), 2) is None
print("ok")
