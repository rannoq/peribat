"""Device icons, drawn with Pillow on a 24 unit grid and rendered at any pixel size."""
from __future__ import annotations

from PIL import Image, ImageDraw

from ..kinds import KINDS, guess_kind  # noqa: F401  (re-exported)

_GRID = 24
_SUPERSAMPLE = 8
_CLEAR = (0, 0, 0, 0)


def _draw_mouse(d: ImageDraw.ImageDraw, k: float, fg) -> None:
    d.rounded_rectangle([6 * k, 1.5 * k, 18 * k, 22.5 * k], radius=6 * k, fill=fg)
    d.rectangle([11.1 * k, 1 * k, 12.9 * k, 11.2 * k], fill=_CLEAR)
    d.rectangle([5 * k, 10.2 * k, 19 * k, 11.8 * k], fill=_CLEAR)


def _draw_keyboard(d: ImageDraw.ImageDraw, k: float, fg) -> None:
    d.rounded_rectangle([1.5 * k, 5.5 * k, 22.5 * k, 18.5 * k], radius=2.6 * k, fill=fg)
    for row, y in enumerate((8.2, 11.6)):
        for i in range(5):
            x = 4.3 + i * 3.5 + (1.2 if row else 0)
            if x + 2 < 21.5:
                d.rectangle([x * k, y * k, (x + 2) * k, (y + 1.8) * k], fill=_CLEAR)
    d.rectangle([6.5 * k, 15 * k, 17.5 * k, 16.6 * k], fill=_CLEAR)


def _draw_headset(d: ImageDraw.ImageDraw, k: float, fg) -> None:
    d.arc([4.5 * k, 2.5 * k, 19.5 * k, 19.5 * k], 180, 360, fill=fg, width=int(2.4 * k))
    d.rounded_rectangle([2.5 * k, 11.5 * k, 7.5 * k, 20.5 * k], radius=2.2 * k, fill=fg)
    d.rounded_rectangle([16.5 * k, 11.5 * k, 21.5 * k, 20.5 * k], radius=2.2 * k, fill=fg)


def _draw_gamepad(d: ImageDraw.ImageDraw, k: float, fg) -> None:
    d.rounded_rectangle([1.5 * k, 6.5 * k, 22.5 * k, 16 * k], radius=4.5 * k, fill=fg)
    d.rounded_rectangle([2.6 * k, 11 * k, 8.6 * k, 19.5 * k], radius=2.8 * k, fill=fg)
    d.rounded_rectangle([15.4 * k, 11 * k, 21.4 * k, 19.5 * k], radius=2.8 * k, fill=fg)
    d.rectangle([5.2 * k, 9.9 * k, 9.2 * k, 11.4 * k], fill=_CLEAR)
    d.rectangle([6.55 * k, 8.55 * k, 8.05 * k, 12.75 * k], fill=_CLEAR)
    for cx, cy in ((16.2, 9.4), (18.4, 11.6)):
        d.ellipse([(cx - 1.05) * k, (cy - 1.05) * k, (cx + 1.05) * k, (cy + 1.05) * k], fill=_CLEAR)


def _draw_speaker(d: ImageDraw.ImageDraw, k: float, fg) -> None:
    d.polygon([(2.5 * k, 9 * k), (7 * k, 9 * k), (12.5 * k, 4 * k),
               (12.5 * k, 20 * k), (7 * k, 15 * k), (2.5 * k, 15 * k)], fill=fg)
    d.arc([8.5 * k, 8 * k, 17 * k, 16 * k], -52, 52, fill=fg, width=int(1.9 * k))
    d.arc([6.5 * k, 4.6 * k, 21.5 * k, 19.4 * k], -52, 52, fill=fg, width=int(1.9 * k))


def _draw_generic(d: ImageDraw.ImageDraw, k: float, fg) -> None:
    d.rounded_rectangle([1.5 * k, 6.5 * k, 20 * k, 17.5 * k], radius=2.6 * k, outline=fg, width=int(1.8 * k))
    d.rounded_rectangle([21 * k, 10 * k, 22.8 * k, 14 * k], radius=0.8 * k, fill=fg)
    d.rounded_rectangle([4.2 * k, 9.2 * k, 14 * k, 14.8 * k], radius=1 * k, fill=fg)


def _draw_bolt(d: ImageDraw.ImageDraw, k: float, fg) -> None:
    pts = [(13.8, 1.5), (5.2, 13.2), (10.8, 13.2), (9.2, 22.5), (18.8, 10), (12.8, 10)]
    d.polygon([(x * k, y * k) for x, y in pts], fill=fg)


_DRAWERS = {
    "mouse": _draw_mouse,
    "keyboard": _draw_keyboard,
    "headset": _draw_headset,
    "gamepad": _draw_gamepad,
    "speaker": _draw_speaker,
    "generic": _draw_generic,
    "bolt": _draw_bolt,
}


def render(kind: str, color: str, px: int) -> Image.Image:
    """Return an RGBA icon of px x px pixels, anti-aliased, in the given colour."""
    draw_icon = _DRAWERS.get(kind, _draw_generic)
    size = _GRID * _SUPERSAMPLE
    canvas = Image.new("RGBA", (size, size), _CLEAR)
    draw_icon(ImageDraw.Draw(canvas), _SUPERSAMPLE, color)
    return canvas.resize((px, px), Image.Resampling.LANCZOS)
