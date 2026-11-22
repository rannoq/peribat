import types
import unittest

from peribat.model import Reading
from peribat.sources import Scanner


def fake_source(key, readings=None, interval=0, fail=False):
    calls = {"n": 0}

    def scan():
        calls["n"] += 1
        if fail:
            raise RuntimeError("boom")
        return readings or []

    module = types.SimpleNamespace(KEY=key, LABEL=key.title(), scan=scan)
    if interval:
        module.INTERVAL = interval
    module.calls = calls
    return module


class ScannerTests(unittest.TestCase):
    def test_merges_sources(self):
        a = fake_source("a", [Reading("mouse", 50)])
        b = fake_source("b", [Reading("pad", 70)])
        names = {r.name for r in Scanner([a, b]).scan()}
        self.assertEqual(names, {"mouse", "pad"})

    def test_failing_source_does_not_hide_others(self):
        scanner = Scanner([fake_source("bad", fail=True), fake_source("ok", [Reading("pad", 70)])])
        self.assertEqual([r.name for r in scanner.scan()], ["pad"])

    def test_disabled_source_is_skipped(self):
        a = fake_source("a", [Reading("mouse", 50)])
        self.assertEqual(Scanner([a]).scan(disabled=["a"]), [])
        self.assertEqual(a.calls["n"], 0)

    def test_slow_source_is_cached_between_scans(self):
        slow = fake_source("slow", [Reading("headset", 40)], interval=3600)
        scanner = Scanner([slow])
        scanner.scan()
        self.assertEqual([r.name for r in scanner.scan()], ["headset"])
        self.assertEqual(slow.calls["n"], 1)


if __name__ == "__main__":
    unittest.main()
