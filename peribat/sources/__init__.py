"""Battery sources. Each module offers ``scan() -> list[Reading]``, a ``KEY`` and a ``LABEL``.

A module may also set ``INTERVAL`` (seconds) when a scan is expensive.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from types import ModuleType
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from ..model import Reading
from . import bluetooth, corsair, logitech, razer, steelseries, xinput

ALL: Tuple[ModuleType, ...] = (logitech, razer, steelseries, corsair, xinput, bluetooth)

log = logging.getLogger(__name__)


class Scanner:
    """Runs the sources side by side and remembers results of the slow ones."""

    def __init__(self, sources: Sequence[ModuleType] = ALL, timeout: float = 40.0) -> None:
        self.sources = tuple(sources)
        self.timeout = timeout
        self._cache: Dict[str, Tuple[float, List[Reading]]] = {}

    def scan(self, disabled: Iterable[str] = ()) -> List[Reading]:
        off = set(disabled)
        active = [s for s in self.sources if s.KEY not in off]
        now = time.monotonic()
        due = [s for s in active if not self._fresh(s, now)]
        if due:
            pool = ThreadPoolExecutor(max_workers=len(due))
            try:
                futures = {s.KEY: pool.submit(s.scan) for s in due}
                for source in due:
                    try:
                        readings = futures[source.KEY].result(timeout=self.timeout)
                    except Exception:
                        log.warning("source %s failed", source.KEY, exc_info=log.isEnabledFor(logging.DEBUG))
                        continue
                    self._cache[source.KEY] = (time.monotonic(), readings)
            finally:
                pool.shutdown(wait=False)  # a stuck driver must not hold up the others
        merged: Dict[str, Reading] = {}
        for source in active:
            for reading in self._cache.get(source.KEY, (0.0, []))[1]:
                merged[reading.name] = reading
        return list(merged.values())

    def _fresh(self, source: ModuleType, now: float) -> bool:
        interval = getattr(source, "INTERVAL", 0)
        cached = self._cache.get(source.KEY)
        return bool(interval and cached and now - cached[0] < interval)


def labels() -> List[Tuple[str, str]]:
    """(key, label) of every source, for the settings window."""
    return [(s.KEY, s.LABEL) for s in ALL]
