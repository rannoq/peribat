"""Where the widget goes, as pure geometry (no Windows calls, so it can be tested)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

TRAY_FALLBACK_WIDTH = 270
EDGE_GAP = 6


@dataclass(frozen=True)
class Taskbar:
    left: int
    top: int
    right: int
    bottom: int
    tray_left: Optional[int] = None  # left edge of the notification area

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def is_horizontal(self) -> bool:
        return 20 <= self.height <= 200 and self.width > self.height * 3


def widget_position(bar: Taskbar, w: int, h: int, dx: int = 0, dy: int = 0) -> Tuple[int, int]:
    """Top-left corner (screen coordinates) of a w x h widget just left of the tray area."""
    if bar.tray_left and bar.left + bar.width // 2 < bar.tray_left < bar.right:
        edge = bar.tray_left
    else:
        edge = bar.right - TRAY_FALLBACK_WIDTH
    return edge - w - EDGE_GAP + dx, bar.top + (bar.height - h) // 2 + dy


def is_off_screen(y: int, h: int, screen_height: int) -> bool:
    """True when an auto-hiding taskbar has slid out of sight, taking the widget with it."""
    return y + h // 2 >= screen_height
