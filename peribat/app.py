"""Ties the sources, the tracker, the tray icon and the widget together."""
from __future__ import annotations

import ctypes
import logging
import logging.handlers
import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from typing import List, Optional, Sequence

from . import __version__, autostart, sources, taskbar
from .config import Settings
from .model import Reading, Tracker
from .tray import Tray
from .ui.render import Cell
from .ui.settings_window import Hooks, SettingsWindow
from .ui.widget import Widget

log = logging.getLogger("peribat")

GRAY = "#9a9a9a"
RETRY_SECONDS = 10      # re-scan quickly while a known device is not answering
RETRY_WINDOW = 5 * 60   # ...but only for this long
REQUEST_POLL_MS = 100

_mutex = None  # held for the lifetime of the process, see _already_running


class App:
    def __init__(self) -> None:
        self.cfg = Settings()
        self._scanner = sources.Scanner()
        self._tracker = Tracker()
        self._devices: List[Reading] = []
        self._lock = threading.Lock()
        self._scan_lock = threading.Lock()
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._settings_requested = threading.Event()
        self._notified: set = set()
        self._root: Optional[tk.Tk] = None
        self._settings_window: Optional[SettingsWindow] = None
        self._tray = Tray(
            devices=self.shown_devices, color_for=self.status_color,
            on_settings=self._settings_requested.set, on_refresh=self.request_refresh,
            widget_enabled=lambda: self.cfg["show_widget"], toggle_widget=self._toggle_widget,
            autostart_enabled=autostart.is_enabled,
            toggle_autostart=lambda: autostart.set_enabled(not autostart.is_enabled()),
            on_quit=self.quit)

    # what to show

    def shown_devices(self) -> List[Reading]:
        """Devices that are not hidden, lowest battery first."""
        hidden = set(self.cfg["hidden"])
        with self._lock:
            return [d for d in self._devices if d.name not in hidden]

    def device_names(self) -> List[str]:
        """Every device seen so far plus hidden ones, so they can be switched back on."""
        with self._lock:
            names = {d.name for d in self._devices}
        return sorted(names | set(self.cfg["hidden"]))

    def status_color(self, level: Optional[int]) -> str:
        if level is None:
            return GRAY
        if level <= min(self.cfg["low_pct"], self.cfg["mid_pct"]):
            return self.cfg["color_low"]
        if level <= max(self.cfg["low_pct"], self.cfg["mid_pct"]):
            return self.cfg["color_mid"]
        return self.cfg["color_good"]

    def text_color(self, level: int) -> str:
        return self.cfg["fixed_color"] if self.cfg["color_mode"] == "fixed" else self.status_color(level)

    def cells(self) -> List[Cell]:
        devices = self.shown_devices()
        if self.cfg["mode"] == "lowest":
            devices = devices[:1]
        if not devices:
            return [Cell("generic", "-", GRAY, GRAY)]
        cells = []
        for device in devices:
            color = self.text_color(device.level)
            text = f"{device.level}%" if self.cfg["show_percent"] else str(device.level)
            icon_color = color if self.cfg["icon_follows_text"] else self.cfg["icon_color"]
            cells.append(Cell(device.kind, text, color, icon_color, device.charging and self.cfg["show_charging"]))
        return cells

    # scanning

    def refresh(self) -> None:
        if not self._scan_lock.acquire(blocking=False):
            return  # a scan is already running
        try:
            off = self.cfg["sources_off"]
            self._tracker.drop_sources(off)
            devices = self._tracker.update(self._scanner.scan(off))
            with self._lock:
                self._devices = devices
            self._tray.update()
            self._notify_low_battery()
        except Exception:
            log.exception("scan failed")
        finally:
            self._scan_lock.release()

    def request_refresh(self) -> None:
        self._wake.set()

    def _worker(self) -> None:
        while not self._stop.is_set():
            self.refresh()
            wait = max(10, self.cfg["refresh_seconds"])
            if self._tracker.missing(RETRY_WINDOW):
                wait = min(wait, RETRY_SECONDS)
            self._wake.wait(wait)
            self._wake.clear()

    def _notify_low_battery(self) -> None:
        if not self.cfg["notify"]:
            return
        limit = self.cfg["notify_pct"]
        shown = self.shown_devices()
        for device in shown:
            if device.level <= limit and not device.charging and device.name not in self._notified:
                self._notified.add(device.name)
                self._tray.notify("Low battery", f"{device.name} is at {device.level}%")
            elif device.level > limit + 5 or device.charging:
                self._notified.discard(device.name)
        self._notified.intersection_update(d.name for d in shown)

    # windows

    def _toggle_widget(self) -> None:
        self.cfg["show_widget"] = not self.cfg["show_widget"]

    def _open_settings(self) -> None:
        """Runs in the Tk thread."""
        if self._settings_window is not None and self._settings_window.alive:
            self._settings_window.focus()
            return
        hooks = Hooks(
            device_names=self.device_names, sources=sources.labels(), refresh=self.request_refresh,
            autostart_get=autostart.is_enabled, autostart_set=autostart.set_enabled,
            changed=self._tray.update, reopen=self._settings_requested.set)
        self._settings_window = SettingsWindow(self._root, self.cfg, hooks)

    def _poll_requests(self) -> None:
        if self._settings_requested.is_set():
            self._settings_requested.clear()
            self._open_settings()
        self._root.after(REQUEST_POLL_MS, self._poll_requests)

    def quit(self) -> None:
        self._stop.set()
        self._wake.set()
        self._tray.stop()

    # run

    def run(self) -> None:
        if not self.cfg["first_run_done"]:
            autostart.set_enabled(True)
            self.cfg["first_run_done"] = True
        else:
            autostart.repair()

        self._root = tk.Tk()
        self._root.withdraw()  # the widget and the settings window are windows of their own
        self._tray.start(on_ready=lambda: threading.Thread(target=self._worker, daemon=True, name="scan").start())
        self._root.after(REQUEST_POLL_MS, self._poll_requests)
        widget = Widget(self._root, self.cfg, self.cells, self._settings_requested.set, self._stop.is_set)
        widget.run()


def _log_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home())
    return base / "peribat" / "peribat.log"


def _setup_logging(debug: bool) -> None:
    path = _log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(path, maxBytes=256_000, backupCount=1, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.DEBUG if debug else logging.WARNING, handlers=[handler])
    if debug and sys.stderr:
        logging.getLogger().addHandler(logging.StreamHandler())


def _already_running() -> bool:
    global _mutex
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    _mutex = kernel32.CreateMutexW(None, False, "Local\\peribat-single-instance")
    already = ctypes.get_last_error() == 183  # ERROR_ALREADY_EXISTS
    if already:
        ctypes.windll.user32.MessageBoxW(
            None, "peribat is already running (look for its icon next to the clock).\n\n"
                  "Quit it from the tray icon first if you want to start it again.", "peribat", 0x40)
    return already


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--version" in args:
        print(__version__)
        return 0
    if "--diag" in args:
        from . import diag
        return diag.run()
    taskbar.make_dpi_aware()
    _setup_logging("--debug" in args)
    if _already_running():
        return 1
    log.info("peribat %s starting", __version__)
    App().run()
    return 0
