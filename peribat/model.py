"""Device readings and the tracker that turns noisy scans into a stable list."""
from __future__ import annotations

import time
from dataclasses import dataclass, replace
from typing import Callable, Dict, Iterable, List, Optional


@dataclass(frozen=True)
class Reading:
    """One battery reading of one device."""

    name: str
    level: int
    charging: bool = False
    kind: str = "generic"
    source: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "level", max(0, min(100, int(self.level))))


class _Entry:
    __slots__ = ("reading", "seen", "pending")

    def __init__(self, reading: Reading, seen: float) -> None:
        self.reading = reading
        self.seen = seen
        self.pending: Optional[int] = None


class Tracker:
    """Merges successive scans of the sources into a steady device list.

    Wireless devices fall asleep and then do not answer for a while, and some
    report a wrong value now and then. Two rules keep the display calm:

    * a device that is missing from a scan keeps its last reading until it has
      been gone for ``stale_after`` seconds;
    * a level that rises sharply without the device charging is only accepted
      once a second scan confirms it (a battery swap shows up one scan later,
      a single bad reading never does).
    """

    def __init__(
        self,
        stale_after: float = 30 * 60,
        max_jump: int = 15,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.stale_after = stale_after
        self.max_jump = max_jump
        self._clock = clock
        self._entries: Dict[str, _Entry] = {}

    def update(self, readings: Iterable[Reading]) -> List[Reading]:
        now = self._clock()
        seen_now = set()
        for reading in readings:
            seen_now.add(reading.name)
            entry = self._entries.get(reading.name)
            if entry is None:
                self._entries[reading.name] = _Entry(reading, now)
                continue
            entry.seen = now
            entry.reading = self._merge(entry, reading)
        for name in [n for n, e in self._entries.items() if now - e.seen > self.stale_after]:
            del self._entries[name]
        return self.current()

    def _merge(self, entry: _Entry, new: Reading) -> Reading:
        old = entry.reading
        sudden_rise = new.level - old.level > self.max_jump and not new.charging and not old.charging
        if not sudden_rise:
            entry.pending = None
            return new
        if entry.pending is not None and abs(entry.pending - new.level) <= 3:
            entry.pending = None
            return new
        entry.pending = new.level
        return replace(old, kind=new.kind, source=new.source)

    def drop_sources(self, sources: Iterable[str]) -> None:
        """Forget devices that came from sources that have been switched off."""
        off = set(sources)
        for name in [n for n, e in self._entries.items() if e.reading.source in off]:
            del self._entries[name]

    def current(self) -> List[Reading]:
        return sorted((e.reading for e in self._entries.values()), key=lambda r: (r.level, r.name))

    def missing(self, within: float) -> List[str]:
        """Names of devices that were seen before but not in the latest scan,
        and have been gone for less than ``within`` seconds."""
        now = self._clock()
        latest = max((e.seen for e in self._entries.values()), default=now)
        return [n for n, e in self._entries.items() if e.seen < latest and now - e.seen < within]
