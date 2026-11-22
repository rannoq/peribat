import unittest

from peribat.model import Reading, Tracker


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def reading(name="mouse", level=50, charging=False):
    return Reading(name, level, charging)


class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.tracker = Tracker(stale_after=600, max_jump=15, clock=self.clock)

    def test_sorted_lowest_first(self):
        result = self.tracker.update([reading("a", 80), reading("b", 20), reading("c", 50)])
        self.assertEqual([r.name for r in result], ["b", "c", "a"])

    def test_missing_device_keeps_last_reading(self):
        self.tracker.update([reading("mouse", 50), reading("pad", 90)])
        self.clock.now = 60
        result = self.tracker.update([reading("pad", 90)])
        self.assertEqual({r.name: r.level for r in result}, {"mouse": 50, "pad": 90})

    def test_missing_device_expires(self):
        self.tracker.update([reading("mouse", 50), reading("pad", 90)])
        self.clock.now = 700
        result = self.tracker.update([reading("pad", 90)])
        self.assertEqual([r.name for r in result], ["pad"])

    def test_single_bad_jump_is_ignored(self):
        self.tracker.update([reading("mouse", 50)])
        result = self.tracker.update([reading("mouse", 100)])
        self.assertEqual(result[0].level, 50)
        result = self.tracker.update([reading("mouse", 50)])
        self.assertEqual(result[0].level, 50)

    def test_confirmed_jump_is_accepted(self):
        self.tracker.update([reading("mouse", 20)])
        self.tracker.update([reading("mouse", 100)])
        result = self.tracker.update([reading("mouse", 100)])
        self.assertEqual(result[0].level, 100)

    def test_jump_while_charging_is_accepted(self):
        self.tracker.update([reading("mouse", 20)])
        result = self.tracker.update([reading("mouse", 60, charging=True)])
        self.assertEqual((result[0].level, result[0].charging), (60, True))

    def test_small_changes_pass(self):
        self.tracker.update([reading("mouse", 50)])
        self.assertEqual(self.tracker.update([reading("mouse", 45)])[0].level, 45)
        self.assertEqual(self.tracker.update([reading("mouse", 55)])[0].level, 55)

    def test_missing_reports_recently_lost(self):
        self.tracker.update([reading("mouse", 50), reading("pad", 90)])
        self.clock.now = 30
        self.tracker.update([reading("pad", 90)])
        self.assertEqual(self.tracker.missing(within=300), ["mouse"])
        self.clock.now = 400
        self.tracker.update([reading("pad", 90)])
        self.assertEqual(self.tracker.missing(within=300), [])

    def test_drop_sources(self):
        self.tracker.update([Reading("a", 10, source="razer"), Reading("b", 20, source="logitech")])
        self.tracker.drop_sources(["razer"])
        self.assertEqual([r.name for r in self.tracker.current()], ["b"])

    def test_level_is_clamped(self):
        self.assertEqual(Reading("x", 140).level, 100)
        self.assertEqual(Reading("x", -3).level, 0)


if __name__ == "__main__":
    unittest.main()
