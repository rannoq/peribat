import unittest

from peribat.layout import Taskbar, is_off_screen, widget_position


class LayoutTests(unittest.TestCase):
    bar = Taskbar(0, 1032, 1920, 1080, tray_left=1662)

    def test_sits_left_of_the_tray(self):
        x, y = widget_position(self.bar, 100, 24)
        self.assertEqual(x, 1662 - 100 - 6)
        self.assertEqual(y, 1032 + (48 - 24) // 2)

    def test_offsets(self):
        x, y = widget_position(self.bar, 100, 24, dx=-10, dy=2)
        self.assertEqual((x, y), (1662 - 100 - 6 - 10, 1032 + 12 + 2))

    def test_without_tray_edge_uses_fallback_width(self):
        bar = Taskbar(0, 1032, 1920, 1080)
        self.assertEqual(widget_position(bar, 100, 24)[0], 1920 - 270 - 100 - 6)

    def test_implausible_tray_edge_is_ignored(self):
        bar = Taskbar(0, 1032, 1920, 1080, tray_left=10)
        self.assertEqual(widget_position(bar, 100, 24)[0], 1920 - 270 - 100 - 6)

    def test_horizontal(self):
        self.assertTrue(self.bar.is_horizontal)
        self.assertFalse(Taskbar(0, 0, 48, 1080).is_horizontal)

    def test_hidden_taskbar(self):
        self.assertTrue(is_off_screen(1090, 24, 1080))
        self.assertFalse(is_off_screen(1044, 24, 1080))


if __name__ == "__main__":
    unittest.main()
