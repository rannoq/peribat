"""Windows specific code: taskbar geometry, attaching a window to it, system settings."""
from __future__ import annotations

import ctypes
import winreg
from ctypes import wintypes
from typing import Optional, Tuple

from .layout import Taskbar

_user32 = ctypes.windll.user32
_user32.FindWindowW.restype = wintypes.HWND
_user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
_user32.FindWindowExW.restype = wintypes.HWND
_user32.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
_user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
_user32.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT, ctypes.c_void_p, wintypes.UINT]
_user32.GetSystemMetrics.argtypes = [ctypes.c_int]
_user32.GetParent.restype = wintypes.HWND
_user32.GetParent.argtypes = [wintypes.HWND]
_user32.SetParent.restype = wintypes.HWND
_user32.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
_user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
_user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
_user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
_user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                 ctypes.c_int, ctypes.c_int, wintypes.UINT]

GWL_STYLE = -16
WS_POPUP, WS_CHILD = 0x80000000, 0x40000000
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE, SWP_SHOWWINDOW = 0x0001, 0x0002, 0x0010, 0x0040
HWND_TOP = 0
SPI_GETWORKAREA = 0x30
_PERSONALIZE = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"


def make_dpi_aware() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        _user32.SetProcessDPIAware()


def system_dpi() -> int:
    try:
        return int(_user32.GetDpiForSystem())
    except (AttributeError, OSError):
        return 96


def screen_size() -> Tuple[int, int]:
    return _user32.GetSystemMetrics(0), _user32.GetSystemMetrics(1)


def taskbar_is_light() -> bool:
    """True when Windows uses the light theme for the taskbar."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _PERSONALIZE) as key:
            return winreg.QueryValueEx(key, "SystemUsesLightTheme")[0] == 1
    except OSError:
        return False


def read_taskbar() -> Optional[Tuple[Taskbar, int]]:
    """The taskbar rectangle with the left edge of its tray area, and its window handle."""
    hwnd = _user32.FindWindowW("Shell_TrayWnd", None)
    if not hwnd:
        return None
    rect = wintypes.RECT()
    _user32.GetWindowRect(hwnd, ctypes.byref(rect))
    left, top, right, bottom = rect.left, rect.top, rect.right, rect.bottom
    tray_left = None
    notify = _user32.FindWindowExW(hwnd, None, "TrayNotifyWnd", None)
    if notify:
        _user32.GetWindowRect(notify, ctypes.byref(rect))
        tray_left = rect.left
    return Taskbar(left, top, right, bottom, tray_left), hwnd


def fallback_taskbar() -> Taskbar:
    """A taskbar guessed from the work area, for when the real one cannot be read."""
    width, height = screen_size()
    work = wintypes.RECT()
    _user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(work), 0)
    bar_height = height - work.bottom
    if bar_height <= 0:
        bar_height, top = 48, height - 48
    else:
        top = work.bottom
    return Taskbar(0, top, width, top + bar_height)


def top_level_handle(inner: int) -> int:
    """The window handle Tk's toplevel really lives in (it wraps the inner one)."""
    return _user32.GetParent(inner) or inner


def attach(hwnd: int, parent: int) -> bool:
    """Make ``hwnd`` a child window of ``parent`` so it shows and hides with it."""
    style = _user32.GetWindowLongPtrW(hwnd, GWL_STYLE)
    _user32.SetWindowLongPtrW(hwnd, GWL_STYLE, (style & ~WS_POPUP) | WS_CHILD)
    _user32.SetParent(hwnd, parent)
    if _user32.GetParent(hwnd) != parent:
        _user32.SetWindowLongPtrW(hwnd, GWL_STYLE, style)
        return False
    return True


def detach(hwnd: int) -> None:
    _user32.SetParent(hwnd, None)
    style = _user32.GetWindowLongPtrW(hwnd, GWL_STYLE)
    _user32.SetWindowLongPtrW(hwnd, GWL_STYLE, (style & ~WS_CHILD) | WS_POPUP)


def move_child(hwnd: int, x: int, y: int, w: int, h: int) -> None:
    _user32.SetWindowPos(hwnd, HWND_TOP, x, y, w, h, SWP_NOACTIVATE | SWP_SHOWWINDOW)


def raise_child(hwnd: int) -> None:
    _user32.SetWindowPos(hwnd, HWND_TOP, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
