"""peribat - taskbar/tray battery monitor for wireless peripherals on Windows.

Collects battery levels from paired Bluetooth devices and from Logitech
receivers (HID++), shows them in a small always-visible widget next to the
system tray (click it to open the settings) and in the tray icon itself.
"""
import ctypes
import sys
import threading
import time
import tkinter as tk
import winreg
from ctypes import wintypes
from pathlib import Path
from tkinter import font as tkfont
from types import SimpleNamespace

import pystray
from PIL import Image, ImageDraw, ImageFont, ImageTk

import icons
from settings import Settings
from sources import bluetooth, logitech
from ui import SettingsWindow

APP_NAME = "peribat"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

GRAY = "#9a9a9a"
KEY = "#010101"  # colour made transparent, so only the text and icons are visible
DEBUG = "--debug" in sys.argv

_debug_last = {}


def _debug(*args):
    """Debug print that only repeats a line when it changed."""
    if not DEBUG:
        return
    msg = " ".join(str(a) for a in args)
    if _debug_last.get(args[0]) != msg:
        _debug_last[args[0]] = msg
        print("[peribat]", msg, flush=True)


# ---------- autostart ----------

def autostart_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP_NAME)
            return True
    except FileNotFoundError:
        return False


def set_autostart(on):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            exe = Path(sys.executable).with_name("pythonw.exe")
            script = Path(__file__).resolve()
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, f'"{exe}" "{script}"')
        else:
            try:
                winreg.DeleteValue(k, APP_NAME)
            except FileNotFoundError:
                pass


# ---------- reading devices ----------

def read_devices():
    """Collect (name, level, charging, kind) from every source, lowest first."""
    merged = {}
    for source in (bluetooth, logitech):
        try:
            for item in source.read():
                name, level, charging = item[0], item[1], item[2]
                kind = item[3] if len(item) > 3 else None
                merged[name] = (level, charging, kind or icons.guess_kind(name))
        except Exception:
            pass
    return sorted(((n, l, c, k) for n, (l, c, k) in merged.items()), key=lambda x: x[1])


# ---------- taskbar widget geometry ----------

_u32 = ctypes.windll.user32
_u32.FindWindowW.restype = wintypes.HWND
_u32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
_u32.FindWindowExW.restype = wintypes.HWND
_u32.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
_u32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
_u32.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT, ctypes.c_void_p, wintypes.UINT]
_u32.GetSystemMetrics.argtypes = [ctypes.c_int]
_u32.GetParent.restype = wintypes.HWND
_u32.GetParent.argtypes = [wintypes.HWND]
_u32.SetParent.restype = wintypes.HWND
_u32.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
_u32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
_u32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
_u32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
_u32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
_u32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                              ctypes.c_int, ctypes.c_int, wintypes.UINT]
GWL_STYLE = -16
WS_POPUP, WS_CHILD = 0x80000000, 0x40000000
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE, SWP_SHOWWINDOW = 0x0001, 0x0002, 0x0010, 0x0040
HWND_TOP = 0


def taskbar_info():
    """Return ((left, top, right, bottom) of the taskbar, left edge of tray area or None)."""
    tray = _u32.FindWindowW("Shell_TrayWnd", None)
    if not tray:
        return None
    r = wintypes.RECT()
    _u32.GetWindowRect(tray, ctypes.byref(r))
    bar = (r.left, r.top, r.right, r.bottom)
    notify = _u32.FindWindowExW(tray, None, "TrayNotifyWnd", None)
    notify_left = None
    if notify:
        _u32.GetWindowRect(notify, ctypes.byref(r))
        notify_left = r.left
    return bar, notify_left


# ---------- the app ----------

class App:
    def __init__(self):
        self.S = Settings()
        self.found = []          # (name, level, charging, kind), lowest first
        self.lock = threading.Lock()
        self.refresh_lock = threading.Lock()
        self.notified = set()
        self.stop = threading.Event()
        self.icon = None
        self.widget = None
        self.settings_win = None
        self.open_req = False    # set from the tray thread, handled by the widget loop

    # ----- derived data -----

    def snapshot(self):
        with self.lock:
            return list(self.found)

    def shown_devices(self):
        """Devices that are not hidden, lowest first."""
        hidden = set(self.S["hidden"])
        return [d for d in self.snapshot() if d[0] not in hidden]

    def widget_devices(self):
        devs = self.shown_devices()
        return devs[:1] if self.S["mode"] == "lowest" else devs

    def level_color(self, level):
        S = self.S
        if S["color_mode"] == "fixed":
            return S["fixed_color"]
        if level is None:
            return GRAY
        low = min(S["low_pct"], S["mid_pct"])
        mid = max(S["low_pct"], S["mid_pct"])
        if level <= low:
            return S["color_low"]
        if level <= mid:
            return S["color_mid"]
        return S["color_good"]

    def label_text(self, level, charging):
        text = f"{level}" + ("%" if self.S["show_percent"] else "")
        if charging and self.S["show_charging"]:
            text = "\u26a1" + text
        return text

    # ----- tray icon -----

    def make_icon(self, level):
        size = 64
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        text = "?" if level is None else str(level)
        d.rounded_rectangle((2, 8, size - 2, size - 8), radius=10, fill=self.level_color(level))
        try:
            font = ImageFont.truetype("arialbd.ttf", 38 if len(text) < 3 else 30)
        except OSError:
            font = ImageFont.load_default()
        d.text((size / 2, size / 2), text, fill="white", font=font, anchor="mm")
        return img

    def apply_tray(self):
        """Update the tray icon, tooltip and menu from the current data."""
        icon = self.icon
        if icon is None:
            return
        devs = self.shown_devices()
        if devs:
            icon.icon = self.make_icon(devs[0][1])
            lines = [f"{n}: {l}%" + (" (charging)" if c else "") for n, l, c, _ in devs]
            icon.title = "\n".join(lines)[:127]
        else:
            icon.icon = self.make_icon(None)
            icon.title = "No devices with battery info"
        icon.update_menu()

    def refresh(self):
        if not self.refresh_lock.acquire(blocking=False):
            return  # a refresh is already running
        try:
            found = read_devices()
            with self.lock:
                self.found[:] = found
            self.apply_tray()
            self.check_notifications()
        except Exception as e:
            _debug("refresh failed:", repr(e))
        finally:
            self.refresh_lock.release()

    def refresh_async(self):
        threading.Thread(target=self.refresh, daemon=True).start()

    def check_notifications(self):
        if not self.S["notify"]:
            return
        limit = self.S["notify_pct"]
        devs = self.shown_devices()
        for name, level, charging, _ in devs:
            if level <= limit and not charging and name not in self.notified:
                self.notified.add(name)
                self.icon.notify(f"{name} is at {level}%", "Low battery")
            elif level > limit + 5 or charging:
                self.notified.discard(name)
        self.notified.intersection_update({d[0] for d in devs})

    def worker(self):
        while not self.stop.is_set():
            self.refresh()
            self.stop.wait(self.S["refresh_seconds"])

    # ----- settings window -----

    def ctx(self):
        return SimpleNamespace(
            devices=self.device_names,
            refresh=self.refresh_async,
            autostart_get=autostart_enabled,
            autostart_set=self._autostart_set,
            changed=self.changed,
            reopen=lambda: self.widget.root.after(50, self.open_settings),
        )

    def device_names(self):
        """Every device name seen so far, plus hidden ones, so they can be switched back on."""
        names = {d[0] for d in self.snapshot()} | set(self.S["hidden"])
        return sorted(names)

    @staticmethod
    def _autostart_set(on):
        try:
            set_autostart(on)
        except OSError as e:
            _debug("autostart failed:", repr(e))

    def changed(self):
        try:
            self.apply_tray()
        except Exception as e:
            _debug("apply_tray failed:", repr(e))

    def open_settings(self):
        """Must run in the Tk (main) thread."""
        win = self.settings_win
        if win is not None and win.alive:
            win.focus()
            return
        self.settings_win = SettingsWindow(self.widget.root, self.S, self.ctx())

    # ----- tray menu -----

    def build_menu(self):
        devs = self.shown_devices()
        items = [pystray.MenuItem(f"{n}  -  {l}%" + ("  (charging)" if c else ""), None, enabled=False)
                 for n, l, c, _ in devs]
        if not items:
            items = [pystray.MenuItem("No devices found", None, enabled=False)]
        items += [
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Settings...", self._request_settings, default=True),
            pystray.MenuItem("Refresh now", lambda icon, item: self.refresh_async()),
            pystray.MenuItem("Show next to tray", self._toggle_widget,
                             checked=lambda item: self.S["show_widget"]),
            pystray.MenuItem("Start with Windows", self._toggle_autostart,
                             checked=lambda item: autostart_enabled()),
            pystray.MenuItem("Quit", self._quit),
        ]
        return items

    def _request_settings(self, icon=None, item=None):
        self.open_req = True

    def _toggle_widget(self, icon, item):
        self.S["show_widget"] = not self.S["show_widget"]

    def _toggle_autostart(self, icon, item):
        self._autostart_set(not autostart_enabled())

    def _quit(self, icon, item):
        self.stop.set()
        icon.stop()

    # ----- run -----

    def run(self):
        if not self.S["first_run_done"]:  # first run: set up autostart once
            self._autostart_set(True)
            self.S["first_run_done"] = True

        self.icon = pystray.Icon(APP_NAME, self.make_icon(None), "peribat",
                                 menu=pystray.Menu(self.build_menu))
        threading.Thread(
            target=lambda: self.icon.run(
                setup=lambda i: (setattr(i, "visible", True),
                                 threading.Thread(target=self.worker, daemon=True).start())),
            daemon=True,
        ).start()

        self.widget = Widget(self)
        self.widget.run()


# ---------- the widget next to the tray ----------

class Widget:
    POLL_MS = 16  # ~60 Hz, so the widget follows the taskbar auto-hide animation

    def __init__(self, app):
        self.app = app
        self.root = tk.Tk()
        self.root.title("peribat")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=KEY)
        self.root.attributes("-transparentcolor", KEY)
        self.holder = tk.Frame(self.root, bg=KEY)
        self.holder.pack(padx=4)
        self.root.withdraw()  # stays hidden until it has a position
        self.shown = False
        self.w = self.h = 0
        self._sig = None
        self._pos = None
        self._raised = 0.0
        self._images = []   # keep PhotoImages alive
        self._font = None
        self._hwnd_cache = None
        self.attached = None        # taskbar hwnd we are a child of, or None
        self._attach_retry = 0.0

    # ----- attaching to the taskbar -----

    def hwnd(self):
        if self._hwnd_cache is None:
            self.root.update_idletasks()
            inner = self.root.winfo_id()
            self._hwnd_cache = _u32.GetParent(inner) or inner
        return self._hwnd_cache

    def attach(self, tray):
        """Make the widget a child window of the taskbar, so it shows and hides with it."""
        hwnd = self.hwnd()
        style = _u32.GetWindowLongPtrW(hwnd, GWL_STYLE)
        _u32.SetWindowLongPtrW(hwnd, GWL_STYLE, (style & ~WS_POPUP) | WS_CHILD)
        _u32.SetParent(hwnd, tray)
        if _u32.GetParent(hwnd) != tray:
            _u32.SetWindowLongPtrW(hwnd, GWL_STYLE, style)
            _debug("attach", "failed")
            return False
        self.attached = tray
        self._pos = None
        _debug("attach", "ok")
        return True

    def detach(self):
        hwnd = self.hwnd()
        _u32.SetParent(hwnd, None)
        style = _u32.GetWindowLongPtrW(hwnd, GWL_STYLE)
        _u32.SetWindowLongPtrW(hwnd, GWL_STYLE, (style & ~WS_CHILD) | WS_POPUP)
        self.attached = None
        self._pos = None

    # ----- content -----

    def rows(self):
        app, S = self.app, self.app.S
        devs = app.widget_devices()
        if not devs:
            return [("-", GRAY, GRAY, "generic")]
        rows = []
        for _name, level, charging, kind in devs:
            color = app.level_color(level)
            icolor = color if S["icon_follows_text"] else S["icon_color"]
            rows.append((app.label_text(level, charging), color, icolor, kind))
        return rows

    def update_content(self):
        S = self.app.S
        rows = self.rows()
        sig = (tuple(rows), S["font_size"], S["bold"], S["show_icon"], S["gap"])
        if sig == self._sig:
            return
        self._sig = sig
        self._pos = None

        for child in self.holder.winfo_children():
            child.destroy()
        self._images = []
        self._font = tkfont.Font(family="Segoe UI", size=S["font_size"],
                                 weight="bold" if S["bold"] else "normal")
        px = max(10, self._font.metrics("linespace"))

        for i, (text, color, icolor, kind) in enumerate(rows):
            cell = tk.Frame(self.holder, bg=KEY)
            cell.pack(side="left", padx=(S["gap"] if i else 0, 0))
            if S["show_icon"]:
                img = ImageTk.PhotoImage(icons.render(kind, icolor, px, KEY))
                self._images.append(img)
                lbl = tk.Label(cell, image=img, bg=KEY, bd=0, highlightthickness=0)
                lbl.pack(side="left", padx=(0, 3))
                lbl.bind("<Button-1>", self._clicked)
            lbl = tk.Label(cell, text=text, font=self._font, fg=color, bg=KEY, bd=0)
            lbl.pack(side="left")
            lbl.bind("<Button-1>", self._clicked)
            cell.bind("<Button-1>", self._clicked)

        self.root.update_idletasks()
        self.w, self.h = self.root.winfo_reqwidth(), self.root.winfo_reqheight()

    def _clicked(self, _event=None):
        self.app.open_settings()

    # ----- position -----

    def compute_pos(self, attached=False):
        """Return (x, y, taskbar origin or None), or None if the widget should be hidden."""
        S = self.app.S
        sh = _u32.GetSystemMetrics(1)
        x = y = None
        origin = None
        try:
            info = taskbar_info()
            _debug("taskbar_info", info)
            if info:
                (left, top, right, bottom), notify_left = info
                bar_h, bar_w = bottom - top, right - left
                if 20 <= bar_h <= 200 and bar_w > bar_h * 3:
                    if notify_left and left + bar_w // 2 < notify_left < right:
                        edge = notify_left
                    else:
                        edge = right - 270
                    x = edge - self.w - 6
                    y = top + (bar_h - self.h) // 2
                    origin = (left, top)
        except Exception as e:
            _debug("taskbar_info failed:", repr(e))
        if x is None:
            # fallback: work area and screen size
            sw = _u32.GetSystemMetrics(0)
            wa = wintypes.RECT()
            _u32.SystemParametersInfoW(0x30, 0, ctypes.byref(wa), 0)  # SPI_GETWORKAREA
            bar_h = sh - wa.bottom
            top = wa.bottom if bar_h > 0 else sh - 48
            bar_h = bar_h if bar_h > 0 else 48
            x = sw - 270 - self.w - 6
            y = top + (bar_h - self.h) // 2
            _debug("fallback", sw, sh, wa.bottom)
        if not (attached and origin) and y + self.h // 2 >= sh:  # taskbar (auto-hide) is out of sight
            return None
        return x + S["x_offset"], y + S["y_offset"], origin

    def place(self):
        """Follow the taskbar. Returns False if the widget should be hidden."""
        now = time.monotonic()
        tray = _u32.FindWindowW("Shell_TrayWnd", None)
        want = bool(self.app.S["attach_taskbar"] and tray)
        if want and self.attached != tray and now >= self._attach_retry:
            if self.attached:
                self.detach()
            if not self.attach(tray):
                self._attach_retry = now + 5.0
        elif not want and self.attached:
            self.detach()

        res = self.compute_pos(bool(self.attached))
        if res is None:
            self._pos = None
            return False
        x, y, origin = res

        if self.attached and origin:
            # child window: coordinates are relative to the taskbar, so it moves with it
            rel = (x - origin[0], y - origin[1], self.w, self.h)
            if rel != self._pos:
                _u32.SetWindowPos(self.hwnd(), HWND_TOP, rel[0], rel[1], rel[2], rel[3],
                                  SWP_NOACTIVATE | SWP_SHOWWINDOW)
                self._pos = rel
                _debug("place (attached)", *rel)
            if now - self._raised > 0.5:  # keep above the taskbar's other children
                _u32.SetWindowPos(self.hwnd(), HWND_TOP, 0, 0, 0, 0,
                                  SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
                self._raised = now
            return True

        if self.attached:  # taskbar geometry not understood, float instead
            self.detach()
        pos = (x, y)
        if pos != self._pos:
            self.root.geometry(f"+{x}+{y}")
            self._pos = pos
            _debug("place", x, y, self.w, self.h)
        if now - self._raised > 0.5:  # keep above the taskbar
            self.root.attributes("-topmost", True)
            self.root.lift()
            self._raised = now
        return True

    # ----- loop -----

    def tick(self):
        app = self.app
        if app.stop.is_set():
            self.root.destroy()
            return
        try:
            if app.open_req:
                app.open_req = False
                app.open_settings()
            ok = False
            if app.S["show_widget"]:
                self.update_content()
                ok = self.place()
            if ok and not self.shown:
                self.root.deiconify()
                if not self.attached:
                    self.root.attributes("-topmost", True)
                    self.root.lift()
                self._pos = None
                self.shown = True
            elif not ok and self.shown:
                self.root.withdraw()
                self.shown = False
        except Exception as e:
            _debug("tick failed:", repr(e))
        self.root.after(self.POLL_MS, self.tick)

    def run(self):
        self.tick()
        self.root.mainloop()


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        _u32.SetProcessDPIAware()
    App().run()


if __name__ == "__main__":
    main()
