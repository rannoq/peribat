"""Tray icon with the lowest battery as a number, tooltip and menu."""
from __future__ import annotations

import logging
import threading
from typing import Callable, List, Optional

import pystray
from PIL import Image, ImageDraw

from .model import Reading
from .ui.render import load_font

log = logging.getLogger(__name__)

TOOLTIP_LIMIT = 127  # Windows cuts longer tooltips


def make_image(level: Optional[int], color: str) -> Image.Image:
    size = 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((2, 8, size - 2, size - 8), radius=10, fill=color)
    text = "?" if level is None else str(level)
    font = load_font(38 if len(text) < 3 else 30, True)
    draw.text((size / 2, size / 2), text, fill="white", font=font, anchor="mm")
    return image


class Tray:
    def __init__(self, devices: Callable[[], List[Reading]], color_for: Callable[[Optional[int]], str],
                 on_settings: Callable[[], None], on_refresh: Callable[[], None],
                 widget_enabled: Callable[[], bool], toggle_widget: Callable[[], None],
                 autostart_enabled: Callable[[], bool], toggle_autostart: Callable[[], None],
                 on_quit: Callable[[], None]) -> None:
        self._devices = devices
        self._color_for = color_for
        self._icon = pystray.Icon("peribat", make_image(None, color_for(None)), "peribat",
                                  menu=pystray.Menu(lambda: self._menu(
                                      on_settings, on_refresh, widget_enabled, toggle_widget,
                                      autostart_enabled, toggle_autostart, on_quit)))

    def _menu(self, on_settings, on_refresh, widget_enabled, toggle_widget,
              autostart_enabled, toggle_autostart, on_quit):
        entries = [pystray.MenuItem(
            f"{d.name}  -  {d.level}%" + ("  (charging)" if d.charging else ""), None, enabled=False)
            for d in self._devices()]
        if not entries:
            entries = [pystray.MenuItem("No devices found", None, enabled=False)]
        return entries + [
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Settings...", lambda *_: on_settings(), default=True),
            pystray.MenuItem("Refresh now", lambda *_: on_refresh()),
            pystray.MenuItem("Show next to tray", lambda *_: toggle_widget(),
                             checked=lambda _item: widget_enabled()),
            pystray.MenuItem("Start with Windows", lambda *_: toggle_autostart(),
                             checked=lambda _item: autostart_enabled()),
            pystray.MenuItem("Quit", lambda *_: on_quit()),
        ]

    def start(self, on_ready: Callable[[], None]) -> None:
        """Run the tray in its own thread; on_ready is called once the icon exists."""
        def setup(icon):
            icon.visible = True
            on_ready()

        threading.Thread(target=lambda: self._icon.run(setup=setup), daemon=True, name="tray").start()

    def update(self) -> None:
        devices = self._devices()
        if devices:
            lowest = devices[0]
            self._icon.icon = make_image(lowest.level, self._color_for(lowest.level))
            lines = [f"{d.name}: {d.level}%" + (" (charging)" if d.charging else "") for d in devices]
            self._icon.title = "\n".join(lines)[:TOOLTIP_LIMIT]
        else:
            self._icon.icon = make_image(None, self._color_for(None))
            self._icon.title = "No devices with battery info"
        self._icon.update_menu()

    def notify(self, title: str, message: str) -> None:
        try:
            self._icon.notify(message, title)
        except Exception:
            log.debug("notification failed", exc_info=True)

    def stop(self) -> None:
        self._icon.stop()
