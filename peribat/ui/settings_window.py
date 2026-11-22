"""The settings window. Every change is applied and saved immediately."""
from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import colorchooser, ttk
from typing import Callable, List, Tuple

from ..config import Settings


@dataclass
class Hooks:
    """What the window needs from the application."""

    device_names: Callable[[], List[str]]
    sources: List[Tuple[str, str]]          # (key, label)
    refresh: Callable[[], None]
    autostart_get: Callable[[], bool]
    autostart_set: Callable[[bool], None]
    changed: Callable[[], None]
    reopen: Callable[[], None]


class SettingsWindow:
    def __init__(self, root: tk.Misc, cfg: Settings, hooks: Hooks) -> None:
        self.cfg = cfg
        self.hooks = hooks
        self.alive = True
        self._variables: list = []  # tk variables are dropped when garbage collected
        self.win = tk.Toplevel(root)
        self.win.title("peribat settings")
        self.win.resizable(False, False)
        self.win.protocol("WM_DELETE_WINDOW", self.close)

        notebook = ttk.Notebook(self.win)
        notebook.pack(fill="both", expand=True, padx=10, pady=(10, 4))
        for title, build in (("Display", self._display_tab), ("Colors", self._colors_tab),
                             ("Behavior", self._behavior_tab)):
            page = ttk.Frame(notebook, padding=12)
            build(page)
            notebook.add(page, text=title)

        buttons = ttk.Frame(self.win)
        buttons.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(buttons, text="Reset to defaults", command=self._reset).pack(side="left")
        ttk.Button(buttons, text="Close", command=self.close).pack(side="right")
        self.focus()

    # window

    def focus(self) -> None:
        self.win.deiconify()
        self.win.lift()
        self.win.focus_force()

    def close(self) -> None:
        self.alive = False
        try:
            self.win.destroy()
        except tk.TclError:
            pass

    def _reset(self) -> None:
        self.cfg.reset()
        self.hooks.changed()
        self.close()
        self.hooks.reopen()

    def _set(self, key: str, value) -> None:
        self.cfg[key] = value
        self.hooks.changed()

    # controls

    def _check(self, parent, key: str, text: str, row: int) -> None:
        var = tk.BooleanVar(value=self.cfg[key])
        var.trace_add("write", lambda *_: self._set(key, var.get()))
        self._variables.append(var)
        ttk.Checkbutton(parent, text=text, variable=var).grid(row=row, column=0, columnspan=3, sticky="w", pady=2)

    def _number(self, parent, key: str, text: str, row: int, low: int, high: int) -> None:
        var = tk.StringVar(value=str(self.cfg[key]))

        def changed(*_):
            try:
                value = int(var.get())
            except ValueError:
                return  # half typed
            self._set(key, max(low, min(high, value)))

        var.trace_add("write", changed)
        self._variables.append(var)
        ttk.Label(parent, text=text).grid(row=row, column=0, sticky="w", pady=2)
        ttk.Spinbox(parent, from_=low, to=high, width=6, textvariable=var).grid(row=row, column=1, sticky="w", padx=(8, 0))

    def _choice(self, parent, key: str, options, row: int) -> int:
        var = tk.StringVar(value=self.cfg[key])
        var.trace_add("write", lambda *_: self._set(key, var.get()))
        self._variables.append(var)
        for offset, (value, text) in enumerate(options):
            ttk.Radiobutton(parent, text=text, value=value, variable=var).grid(
                row=row + offset, column=0, columnspan=3, sticky="w", pady=1)
        return row + len(options)

    def _color(self, parent, key: str, text: str, row: int) -> None:
        ttk.Label(parent, text=text).grid(row=row, column=0, sticky="w", pady=3)
        swatch = tk.Button(parent, width=9, relief="solid", bd=1, bg=self.cfg[key], activebackground=self.cfg[key])
        swatch.grid(row=row, column=1, sticky="w", padx=(8, 0))

        def pick():
            _rgb, chosen = colorchooser.askcolor(color=self.cfg[key], parent=self.win, title=text)
            if chosen:
                swatch.configure(bg=chosen, activebackground=chosen)
                self._set(key, chosen)
                self.focus()

        swatch.configure(command=pick)

    # tabs

    def _display_tab(self, page) -> None:
        row = 0
        self._check(page, "show_widget", "Show next to the system tray", row); row += 1
        self._check(page, "attach_taskbar", "Attach to the taskbar (stays visible with the Start menu open)", row); row += 1
        row = self._choice(page, "mode", (("lowest", "Show only the lowest battery"),
                                          ("all", "Show all devices")), row)
        self._check(page, "show_icon", "Show device icon", row); row += 1
        self._check(page, "show_percent", "Show % sign", row); row += 1
        self._check(page, "show_charging", "Show a bolt while charging", row); row += 1
        self._number(page, "font_size", "Text size", row, 8, 24); row += 1
        self._check(page, "bold", "Bold text", row); row += 1
        self._number(page, "gap", "Space between devices", row, 0, 60); row += 1
        self._number(page, "x_offset", "Move left/right (px)", row, -400, 400); row += 1
        self._number(page, "y_offset", "Move up/down (px)", row, -40, 40); row += 1

        box = ttk.LabelFrame(page, text="Devices to show", padding=6)
        box.grid(row=row, column=0, columnspan=3, sticky="we", pady=(10, 0))
        names = self.hooks.device_names()
        if not names:
            ttk.Label(box, text="No devices found yet").pack(anchor="w")
        for name in names:
            var = tk.BooleanVar(value=name not in self.cfg["hidden"])

            def toggled(*_, device=name, variable=var):
                hidden = set(self.cfg["hidden"])
                (hidden.discard if variable.get() else hidden.add)(device)
                self._set("hidden", sorted(hidden))

            var.trace_add("write", toggled)
            self._variables.append(var)
            ttk.Checkbutton(box, text=name, variable=var).pack(anchor="w")

    def _colors_tab(self, page) -> None:
        row = self._choice(page, "color_mode", (("level", "Color by battery level"),
                                                ("fixed", "One fixed color")), 0)
        self._color(page, "color_good", "Battery OK", row); row += 1
        self._color(page, "color_mid", "Battery getting low", row); row += 1
        self._color(page, "color_low", "Battery low", row); row += 1
        self._color(page, "fixed_color", "Fixed color", row); row += 1
        self._number(page, "mid_pct", "'Getting low' at or below (%)", row, 1, 99); row += 1
        self._number(page, "low_pct", "'Low' at or below (%)", row, 1, 99); row += 1
        self._check(page, "icon_follows_text", "Icon uses the same color as the text", row); row += 1
        self._color(page, "icon_color", "Icon color (if different)", row)

    def _behavior_tab(self, page) -> None:
        row = 0
        autostart = tk.BooleanVar(value=self.hooks.autostart_get())
        autostart.trace_add("write", lambda *_: self.hooks.autostart_set(autostart.get()))
        self._variables.append(autostart)
        ttk.Checkbutton(page, text="Start with Windows", variable=autostart).grid(
            row=row, column=0, columnspan=3, sticky="w", pady=2); row += 1
        self._check(page, "notify", "Notify when the battery is low", row); row += 1
        self._number(page, "notify_pct", "Notify at or below (%)", row, 1, 99); row += 1
        self._number(page, "refresh_seconds", "Check every (seconds)", row, 10, 3600); row += 1

        box = ttk.LabelFrame(page, text="Look for", padding=6)
        box.grid(row=row, column=0, columnspan=3, sticky="we", pady=(10, 0)); row += 1
        for key, label in self.hooks.sources:
            var = tk.BooleanVar(value=key not in self.cfg["sources_off"])

            def toggled(*_, source=key, variable=var):
                off = set(self.cfg["sources_off"])
                (off.discard if variable.get() else off.add)(source)
                self._set("sources_off", sorted(off))

            var.trace_add("write", toggled)
            self._variables.append(var)
            ttk.Checkbutton(box, text=label, variable=var).pack(anchor="w")

        ttk.Button(page, text="Refresh now", command=self.hooks.refresh).grid(
            row=row, column=0, sticky="w", pady=(10, 0))
