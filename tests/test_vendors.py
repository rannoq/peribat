import unittest

from peribat.sources import bluetooth, corsair, razer, steelseries, xinput


class RazerTests(unittest.TestCase):
    def test_report_layout_and_crc(self):
        report = razer.build_report(0x1F, 0x07, 0x80)
        self.assertEqual(len(report), 90)
        self.assertEqual((report[1], report[5], report[6], report[7]), (0x1F, 2, 0x07, 0x80))
        crc = 0
        for byte in report[2:88]:
            crc ^= byte
        self.assertEqual(report[88], crc)
        self.assertEqual(report[88], 0x02 ^ 0x07 ^ 0x80)

    def reply(self, status=0x02, command=0x80, arg1=128, with_id=True):
        data = bytearray(90)
        data[0], data[6], data[7], data[9] = status, 0x07, command, arg1
        return (b"\x00" if with_id else b"") + bytes(data)

    def test_parse_success(self):
        args = razer.parse_reply(self.reply(), 0x07, 0x80)
        self.assertEqual(args[1], 128)

    def test_parse_rejects_failures_and_mismatches(self):
        self.assertIsNone(razer.parse_reply(self.reply(status=0x05), 0x07, 0x80))
        self.assertIsNone(razer.parse_reply(self.reply(command=0x84), 0x07, 0x80))
        self.assertIsNone(razer.parse_reply(b"\x00" * 10, 0x07, 0x80))

    def test_reads_level_and_charging(self):
        class Device:
            def __init__(self):
                self.last = None

            def send_feature_report(self, data):
                self.last = data[1:][7]

            def get_feature_report(self, report_id, size):
                level = self.last == 0x80
                return list(RazerTests.reply(RazerTests, command=self.last, arg1=255 if level else 1))

        razer.REPLY_DELAY = 0
        level, charging, tid = razer._read(Device(), (0x1F, 0x3F))
        self.assertEqual((level, charging, tid), (100, True, 0x1F))


class SteelSeriesTests(unittest.TestCase):
    def test_legacy(self):
        self.assertEqual(steelseries.parse_legacy(bytes((6, 0x18, 64, 0, 0, 0, 0, 0))), 64)
        self.assertIsNone(steelseries.parse_legacy(bytes((6, 0x18, 0))))     # headset off
        self.assertIsNone(steelseries.parse_legacy(bytes((6, 0x18, 200))))
        self.assertIsNone(steelseries.parse_legacy(b"\x06"))

    def test_nova(self):
        self.assertEqual(steelseries.parse_nova(bytes((0xB0, 0, 80, 3)), discrete=False), (80, False))
        self.assertEqual(steelseries.parse_nova(bytes((0xB0, 0, 3, 1)), discrete=True), (75, True))
        self.assertIsNone(steelseries.parse_nova(bytes((0xB0, 0, 80, 0)), discrete=False))  # offline
        self.assertIsNone(steelseries.parse_nova(bytes((0x20, 0, 80, 3)), discrete=False))


class CorsairTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(corsair.parse(bytes((0, 0, 85, 0, 1))), (85, False))
        self.assertEqual(corsair.parse(bytes((0, 0, 0x80 | 40, 0, 4))), (40, True))   # mic up flag
        self.assertIsNone(corsair.parse(bytes((0, 0, 85, 0, 0))))                    # not connected
        self.assertIsNone(corsair.parse(b"\x00\x00"))


class XInputTests(unittest.TestCase):
    def test_describe(self):
        self.assertIsNone(xinput.describe(0, 3))   # disconnected
        self.assertIsNone(xinput.describe(1, 3))   # wired, no battery
        self.assertEqual(xinput.describe(2, 3), 100)
        self.assertEqual(xinput.describe(3, 0), 10)
        self.assertEqual(xinput.describe(2, 9), 100)


class BluetoothTests(unittest.TestCase):
    def test_parse(self):
        readings = bluetooth.parse('[{"name":"WH-1000XM4","level":64},{"name":"WH-1000XM4","level":60}]')
        self.assertEqual([(r.name, r.level, r.kind) for r in readings], [("WH-1000XM4", 64, "headset")])

    def test_single_object_and_empty(self):
        self.assertEqual(bluetooth.parse('{"name":"Keyboard K380","level":90}')[0].level, 90)
        self.assertEqual(bluetooth.parse(""), [])

    def test_out_of_range_is_dropped(self):
        self.assertEqual(bluetooth.parse('[{"name":"x","level":255}]'), [])


if __name__ == "__main__":
    unittest.main()
