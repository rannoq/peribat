import unittest

from peribat.sources import logitech
from peribat.sources.logitech import Channel


class FakeDevice:
    """A HID++ 2.0 device at one index. Replies follow the protocol: IRoot function 0 looks a
    feature up, function 1 is a ping."""

    def __init__(self, index=1, features=None, battery=(73, 0, 1), name=b"PRO X Superlight",
                 kind=3, asleep=False):
        self.index = index
        self.features = features or {0x0005: 3, 0x1004: 4}
        self.battery = battery
        self.name = name
        self.kind = kind
        self.asleep = asleep
        self.pending = []

    def write(self, data):
        _id, index, feature, header = data[0], data[1], data[2], data[3]
        function, params = header >> 4, data[4:]
        if index != self.index or self.asleep:
            return
        reply = bytearray(20)
        reply[0:4] = bytes((0x11, index, feature, header))
        if feature == 0 and function == 0:
            reply[4] = self.features.get((params[0] << 8) | params[1], 0)
        elif feature == 0 and function == 1:
            reply[4:7] = bytes((4, 2, params[2]))
        elif feature == 3 and function == 0:
            reply[4] = len(self.name)
        elif feature == 3 and function == 1:
            chunk = self.name[params[0]:params[0] + 16]
            reply[4:4 + len(chunk)] = chunk
        elif feature == 3 and function == 2:
            reply[4] = self.kind
        elif feature == 4 and function == 1:
            reply[4:7] = bytes(self.battery)
        else:
            reply[2], reply[3] = 0xFF, feature  # HID++ 2.0 error
        self.pending.append(bytes(reply))

    def read(self, size, timeout_ms):
        return list(self.pending.pop(0)) if self.pending else []


class LogitechTests(unittest.TestCase):
    def test_reads_battery_name_and_kind(self):
        reading = logitech.read_device(Channel(FakeDevice()), 1)
        self.assertEqual((reading.name, reading.level, reading.charging, reading.kind),
                         ("PRO X Superlight", 73, True, "mouse"))

    def test_empty_slot_is_skipped(self):
        self.assertIsNone(logitech.read_device(Channel(FakeDevice()), 2))

    def test_sleeping_device_is_skipped(self):
        channel = Channel(FakeDevice(asleep=True))
        channel.request = lambda *a, **k: None  # no answer, do not wait for the timeout
        self.assertIsNone(logitech.read_device(channel, 1))

    def test_falls_back_to_status_feature(self):
        device = FakeDevice(features={0x0005: 3, 0x1000: 5})
        original = device.write

        def write(data):
            if data[2] == 5 and data[3] >> 4 == 0:
                reply = bytearray(20)
                reply[0:4] = bytes((0x11, 1, 5, data[3]))
                reply[4:7] = bytes((40, 30, 0))
                device.pending.append(bytes(reply))
            else:
                original(data)

        device.write = write
        self.assertEqual(logitech.read_battery(Channel(device), 1), (40, False))

    def test_unknown_device_gets_a_generic_name(self):
        device = FakeDevice(features={0x1004: 4})
        reading = logitech.read_device(Channel(device), 1)
        self.assertEqual(reading.name, "Logitech device 1")

    def test_decoders(self):
        self.assertEqual(logitech.decode_unified(bytes((80, 0, 0))), (80, False))
        self.assertEqual(logitech.decode_unified(bytes((80, 0, 2))), (80, True))
        self.assertEqual(logitech.decode_status(bytes((55, 30, 4))), (55, True))
        self.assertEqual(logitech.decode_status(bytes((55, 30, 3))), (55, False))
        self.assertEqual(logitech.decode_voltage(bytes((0x0F, 0xA2, 0x80))), (80, True))  # 4002 mV

    def test_voltage_curve(self):
        self.assertEqual(logitech.voltage_to_percent(4200), 100)
        self.assertEqual(logitech.voltage_to_percent(3720), 20)
        self.assertEqual(logitech.voltage_to_percent(3000), 0)


if __name__ == "__main__":
    unittest.main()
