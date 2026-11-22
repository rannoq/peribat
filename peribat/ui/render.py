"""Draws the widget content (icons and text) as one anti-aliased image."""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Sequence

from PIL import Image, ImageDraw, ImageFont

from . import icons

_BOLD_FONTS = ("segoeuib.ttf", "seguisb.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf")
_REGULAR_FONTS = ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf")


@dataclass(frozen=True)
class Cell:
    """One device in the widget."""

    kind: str
    text: str
    text_color: str
    icon_color: str
    charging: bool = False


@lru_cache(maxsize=16)
def load_font(px: int, bold: bool) -> ImageFont.ImageFont:
    for name in (_BOLD_FONTS if bold else _REGULAR_FONTS):
        try:
            return ImageFont.truetype(name, px)
        except OSError:
            continue
    return ImageFont.load_default()


def render_row(cells: Sequence[Cell], *, font_px: int, bold: bool, show_icon: bool,
               gap: int, background: str) -> Image.Image:
    """Lay the cells out left to right on a solid background (which the window makes transparent)."""
    font = load_font(font_px, bold)
    icon_px = round(font_px * 1.3)
    bolt_px = round(font_px * 1.1)
    inner_gap = max(2, round(font_px * 0.3))
    height = max(icon_px, font_px) + 4

    text_widths = [math.ceil(font.getlength(cell.text)) for cell in cells]
    cell_widths = [
        text_width
        + (icon_px + inner_gap if show_icon else 0)
        + (bolt_px if cell.charging else 0)
        for cell, text_width in zip(cells, text_widths)
    ]
    total = sum(cell_widths) + gap * max(0, len(cells) - 1) + 4

    image = Image.new("RGB", (max(total, 1), height), background)
    draw = ImageDraw.Draw(image)
    x = 2
    for cell, text_width, cell_width in zip(cells, text_widths, cell_widths):
        left = x
        if show_icon:
            icon = icons.render(cell.kind, cell.icon_color, icon_px)
            image.paste(icon, (left, (height - icon_px) // 2), icon)
            left += icon_px + inner_gap
        if cell.charging:
            bolt = icons.render("bolt", cell.text_color, bolt_px)
            image.paste(bolt, (left, (height - bolt_px) // 2), bolt)
            left += bolt_px
        draw.text((left, height / 2), cell.text, font=font, fill=cell.text_color, anchor="lm")
        x += cell_width + gap
    return image
