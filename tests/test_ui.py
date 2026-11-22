import unittest

from peribat.kinds import KINDS, guess_kind
from peribat.ui import icons
from peribat.ui.render import Cell, render_row


class KindTests(unittest.TestCase):
    def test_guess(self):
        cases = {
            "G305 Lightspeed Wireless Gaming Mouse": "mouse",
            "PRO X Superlight": "mouse",
            "Aula F75 Pro Max": "keyboard",
            "AirPods Pro": "headset",
            "Arctis Nova 7": "headset",
            "Xbox Wireless Controller": "gamepad",
            "Something Else": "generic",
        }
        for name, kind in cases.items():
            self.assertEqual(guess_kind(name), kind, name)


class IconTests(unittest.TestCase):
    def test_every_kind_renders_at_every_size(self):
        for kind in KINDS + ("bolt",):
            for px in (12, 16, 20, 32):
                image = icons.render(kind, "#ffffff", px)
                self.assertEqual(image.size, (px, px))
                self.assertGreater(image.getchannel("A").getbbox()[2], 0, kind)


class RenderTests(unittest.TestCase):
    cells = [Cell("mouse", "50%", "#4cc38a", "#4cc38a"),
             Cell("headset", "23%", "#f0a830", "#f0a830", charging=True)]

    def test_size_grows_with_content(self):
        one = render_row(self.cells[:1], font_px=14, bold=True, show_icon=True, gap=10, background="#202020")
        two = render_row(self.cells, font_px=14, bold=True, show_icon=True, gap=10, background="#202020")
        self.assertGreater(two.width, one.width)
        self.assertEqual(one.height, two.height)

    def test_icons_can_be_left_out(self):
        with_icons = render_row(self.cells, font_px=14, bold=True, show_icon=True, gap=10, background="#202020")
        without = render_row(self.cells, font_px=14, bold=True, show_icon=False, gap=10, background="#202020")
        self.assertLess(without.width, with_icons.width)

    def test_background_stays_exact(self):
        image = render_row(self.cells, font_px=14, bold=True, show_icon=True, gap=10, background="#202020")
        self.assertEqual(image.getpixel((image.width - 1, 0)), (0x20, 0x20, 0x20))


if __name__ == "__main__":
    unittest.main()
