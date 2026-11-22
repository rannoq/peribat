"""The small window next to the system tray."""
from __future__ import annotations

import logging
import time
import tkinter as tk
from typing import Callable, List, Optional

from PIL import ImageTk

from .. import layout, taskbar
from ..config import Settings
from .render import Cell, render_row

log = logging.getLogger(__name__)

FLOATING_POLL_MS = 16   # follows the taskbar's auto-hide animation
ATTACHED_POLL_MS = 100  # an attached window moves with the taskbar by itself
RETRY_ATTACH_SECONDS = 5.0
RAISE_EVERY_SECONDS = 0.5


class Widget:
    """Shows the cells it is given, glued to the taskbar or floating above it."""

    def __init__(self, root: tk.Tk, cfg: Settings, cells: Callable[[], List[Cell]],
                 on_click: Callable[[], None], should_stop: Callable[[], bool]) -> None:
        self.root = root
        self.cfg = cfg
        self._cells = cells
        self._on_click = on_click
        self._should_stop = should_stop

        light = taskbar.taskbar_is_light()
        self._key = "#f3f3f3" if light else "#202020"  # drawn around the content, made transparent
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=self._key)
        self.win.attributes("-transparentcolor", self._key)
        self._label = tk.Label(self.win, bd=0, highlightthickness=0, bg=self._key)
        self._label.pack()
        self._label.bind("<Button-1>", lambda _event: self._on_click())
        self.win.withdraw()  # hidden until it has a position

        self._signature: Optional[tuple] = None
        self._photo: Optional[ImageTk.PhotoImage] = None
        self._size = (0, 0)
        self._shown = False
        self._last_pos: Optional[tuple] = None
        self._raised = 0.0
        self._handle: Optional[int] = None
        self._attached_to: Optional[int] = None
        self._retry_attach_at = 0.0

    # content

    def _refresh_content(self) -> None:
        cfg = self.cfg
        cells = self._cells()
        dpi = taskbar.system_dpi()
        signature = (tuple(cells), cfg["font_size"], cfg["bold"], cfg["show_icon"], cfg["gap"], dpi)
        if signature == self._signature:
            return
        self._signature = signature
        image = render_row(
            cells, font_px=round(cfg["font_size"] * dpi / 72), bold=cfg["bold"],
            show_icon=cfg["show_icon"], gap=round(cfg["gap"] * dpi / 96), background=self._key)
        self._photo = ImageTk.PhotoImage(image)
        self._label.configure(image=self._photo)
        self._size = image.size
        self._last_pos = None

    # attaching to the taskbar

    def _hwnd(self) -> int:
        if self._handle is None:
            self.win.update_idletasks()
            self._handle = taskbar.top_level_handle(self.win.winfo_id())
        return self._handle

    def _sync_attachment(self, bar_hwnd: Optional[int], now: float) -> None:
        wanted = bar_hwnd if self.cfg["attach_taskbar"] else None
        if wanted is None and self._attached_to is not None:
            taskbar.detach(self._hwnd())
            self._attached_to, self._last_pos = None, None
        elif wanted is not None and self._attached_to != wanted and now >= self._retry_attach_at:
            if self._attached_to is not None:
                taskbar.detach(self._hwnd())
            if taskbar.attach(self._hwnd(), wanted):
                self._attached_to, self._last_pos = wanted, None
            else:
                self._attached_to = None
                self._retry_attach_at = now + RETRY_ATTACH_SECONDS
                log.debug("could not attach to the taskbar, floating instead")

    # position

    def _place(self) -> bool:
        """Move next to the tray. Returns False when the widget should be hidden."""
        now = time.monotonic()
        found = taskbar.read_taskbar()
        bar, bar_hwnd = found if found else (None, None)
        if bar is not None and not bar.is_horizontal:
            bar = bar_hwnd = None
        self._sync_attachment(bar_hwnd, now)
        if bar is None:
            bar = taskbar.fallback_taskbar()

        w, h = self._size
        x, y = layout.widget_position(bar, w, h, self.cfg["x_offset"], self.cfg["y_offset"])

        if self._attached_to is not None:
            position = (x - bar.left, y - bar.top, w, h)  # relative to the taskbar
            if position != self._last_pos:
                taskbar.move_child(self._hwnd(), *position)
                self._last_pos = position
            if now - self._raised > RAISE_EVERY_SECONDS:
                taskbar.raise_child(self._hwnd())
                self._raised = now
            return True

        if layout.is_off_screen(y, h, taskbar.screen_size()[1]):
            self._last_pos = None
            return False
        if (x, y) != self._last_pos:
            self.win.geometry(f"+{x}+{y}")
            self._last_pos = (x, y)
        if now - self._raised > RAISE_EVERY_SECONDS:
            self.win.attributes("-topmost", True)
            self.win.lift()
            self._raised = now
        return True

    # loop

    def _tick(self) -> None:
        if self._should_stop():
            self.root.destroy()
            return
        try:
            visible = False
            if self.cfg["show_widget"]:
                self._refresh_content()
                visible = self._place()
            if visible and not self._shown:
                self.win.deiconify()
                self._last_pos = None
                self._shown = True
            elif not visible and self._shown:
                self.win.withdraw()
                self._shown = False
        except Exception:
            log.exception("widget update failed")
        delay = ATTACHED_POLL_MS if self._attached_to is not None else FLOATING_POLL_MS
        self.root.after(delay, self._tick)

    def run(self) -> None:
        self._tick()
        self.root.mainloop()
