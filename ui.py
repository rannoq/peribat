"""Settings window for peribat (tkinter)."""
import tkinter as tk
from tkinter import colorchooser, ttk


class SettingsWindow:
    """ctx must provide: devices() -> [names], refresh(), autostart_get() -> bool,
    autostart_set(bool), changed(), reopen()."""

    def __init__(self, root, settings, ctx):
        self.S = settings
        self.ctx = ctx
        self._keep = []  # keep tk variables alive
        self.alive = True
        self.win = tk.Toplevel(root)
        self.win.title("peribat settings")
        self.win.resizable(False, False)
        self.win.protocol("WM_DELETE_WINDOW", self.close)

        nb = ttk.Notebook(self.win)
        nb.pack(fill="both", expand=True, padx=10, pady=(10, 4))
        for title, builder in (("Display", self._display_tab),
                               ("Colors", self._colors_tab),
                               ("Behavior", self._behavior_tab)):
            frame = ttk.Frame(nb, padding=12)
            builder(frame)
            nb.add(frame, text=title)

        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(bar, text="Reset to defaults", command=self._reset).pack(side="left")
        ttk.Button(bar, text="Close", command=self.close).pack(side="right")
        self.focus()

    # ---------- window handling ----------

    def focus(self):
        self.win.deiconify()
        self.win.lift()
        self.win.focus_force()

    def close(self):
        self.alive = False
        try:
            self.win.destroy()
        except tk.TclError:
            pass

    def _reset(self):
        self.S.reset()
        self.ctx.changed()
        self.close()
        self.ctx.reopen()

    def _set(self, key, value):
        self.S[key] = value
        self.ctx.changed()

    # ---------- widget helpers ----------

    def _check(self, parent, key, text, row):
        var = tk.BooleanVar(value=self.S[key])
        var.trace_add("write", lambda *_: self._set(key, var.get()))
        self._keep.append(var)
        ttk.Checkbutton(parent, text=text, variable=var).grid(
            row=row, column=0, columnspan=3, sticky="w", pady=2)

    def _number(self, parent, key, text, row, lo, hi):
        var = tk.StringVar(value=str(self.S[key]))

        def on_write(*_):
            try:
                value = int(var.get())
            except ValueError:
                return
            self._set(key, max(lo, min(hi, value)))

        var.trace_add("write", on_write)
        self._keep.append(var)
        ttk.Label(parent, text=text).grid(row=row, column=0, sticky="w", pady=2)
        ttk.Spinbox(parent, from_=lo, to=hi, width=6, textvariable=var).grid(
            row=row, column=1, sticky="w", padx=(8, 0))

    def _choice(self, parent, key, options, row):
        var = tk.StringVar(value=self.S[key])
        var.trace_add("write", lambda *_: self._set(key, var.get()))
        self._keep.append(var)
        for i, (value, text) in enumerate(options):
            ttk.Radiobutton(parent, text=text, value=value, variable=var).grid(
                row=row + i, column=0, columnspan=3, sticky="w", pady=1)
        return row + len(options)

    def _color(self, parent, key, text, row):
        ttk.Label(parent, text=text).grid(row=row, column=0, sticky="w", pady=3)
        btn = tk.Button(parent, width=9, relief="solid", bd=1, bg=self.S[key],
                        activebackground=self.S[key])
        btn.grid(row=row, column=1, sticky="w", padx=(8, 0))

        def pick():
            _, hex_color = colorchooser.askcolor(color=self.S[key], parent=self.win, title=text)
            if hex_color:
                btn.config(bg=hex_color, activebackground=hex_color)
                self._set(key, hex_color)
                self.focus()

        btn.config(command=pick)

    # ---------- tabs ----------

    def _display_tab(self, f):
        r = 0
        self._check(f, "show_widget", "Show next to the system tray", r); r += 1
        self._check(f, "attach_taskbar", "Attach to the taskbar (stays visible with Start menu open)", r); r += 1
        r = self._choice(f, "mode", (("lowest", "Show only the lowest battery"),
                                     ("all", "Show all devices")), r)
        self._check(f, "show_icon", "Show device icon (mouse, headset, ...)", r); r += 1
        self._check(f, "show_percent", "Show % sign", r); r += 1
        self._check(f, "show_charging", "Show \u26a1 while charging", r); r += 1
        self._number(f, "font_size", "Text size", r, 8, 24); r += 1
        self._check(f, "bold", "Bold text", r); r += 1
        self._number(f, "gap", "Space between devices", r, 0, 60); r += 1
        self._number(f, "x_offset", "Move left/right (px)", r, -400, 400); r += 1
        self._number(f, "y_offset", "Move up/down (px)", r, -40, 40); r += 1

        box = ttk.LabelFrame(f, text="Devices to show", padding=6)
        box.grid(row=r, column=0, columnspan=3, sticky="we", pady=(10, 0))
        names = self.ctx.devices()
        if not names:
            ttk.Label(box, text="No devices found yet").pack(anchor="w")
        for name in names:
            var = tk.BooleanVar(value=name not in self.S["hidden"])

            def on_write(*_, n=name, v=var):
                hidden = set(self.S["hidden"])
                if v.get():
                    hidden.discard(n)
                else:
                    hidden.add(n)
                self._set("hidden", sorted(hidden))

            var.trace_add("write", on_write)
            self._keep.append(var)
            ttk.Checkbutton(box, text=name, variable=var).pack(anchor="w")

    def _colors_tab(self, f):
        r = 0
        r = self._choice(f, "color_mode", (("level", "Color by battery level"),
                                           ("fixed", "One fixed color")), r)
        self._color(f, "color_good", "Battery OK", r); r += 1
        self._color(f, "color_mid", "Battery getting low", r); r += 1
        self._color(f, "color_low", "Battery low", r); r += 1
        self._color(f, "fixed_color", "Fixed color", r); r += 1
        self._number(f, "mid_pct", "'Getting low' at or below (%)", r, 1, 99); r += 1
        self._number(f, "low_pct", "'Low' at or below (%)", r, 1, 99); r += 1
        self._check(f, "icon_follows_text", "Icon uses the same color as the text", r); r += 1
        self._color(f, "icon_color", "Icon color (if different)", r)

    def _behavior_tab(self, f):
        r = 0
        auto = tk.BooleanVar(value=self.ctx.autostart_get())
        auto.trace_add("write", lambda *_: self.ctx.autostart_set(auto.get()))
        self._keep.append(auto)
        ttk.Checkbutton(f, text="Start with Windows", variable=auto).grid(
            row=r, column=0, columnspan=3, sticky="w", pady=2); r += 1
        self._check(f, "notify", "Notify when the battery is low", r); r += 1
        self._number(f, "notify_pct", "Notify at or below (%)", r, 1, 99); r += 1
        self._number(f, "refresh_seconds", "Check every (seconds)", r, 10, 3600); r += 1
        ttk.Button(f, text="Refresh now", command=self.ctx.refresh).grid(
            row=r, column=0, sticky="w", pady=(10, 0))
