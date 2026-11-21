"""Device icons drawn with Pillow (anti-aliased), plus device type guessing."""
from PIL import Image, ImageDraw

KINDS = ("mouse", "keyboard", "headset", "gamepad", "speaker", "generic")

_NAME_RULES = [
    ("headset", ("headset", "headphone", "earbud", "buds", "airpods", "arctis", "hyperx cloud",
                 "cloud ii", "cloud iii", "cloud alpha", "kraken", "barracuda", "astro a",
                 "g733", "g535", "g935", "wh-1000", "wf-1000", "jabra", "earphone")),
    ("gamepad", ("controller", "gamepad", "xbox", "dualsense", "dualshock", "joy-con", "8bitdo")),
    ("speaker", ("speaker", "soundbar", "boombox", "soundcore")),
    ("keyboard", ("keyboard", "keychron", "k380", "k780", "mx keys", "g915", "g613", "g512",
                  "k400", "k520", "huntsman", "blackwidow", "aula", "f75", "f87")),
    ("mouse", ("mouse", "mice", "superlight", "g305", "g502", "g703", "g903", "g604",
               "g pro wireless", "deathadder", "viper", "basilisk", "naga", "mx master",
               "mx anywhere", "trackball", "pulsefire", "harpoon", "glorious", "model o")),
]


def guess_kind(name):
    n = (name or "").lower()
    for kind, words in _NAME_RULES:
        if any(w in n for w in words):
            return kind
    return "generic"


def render(kind, color, px, bg="#010101"):
    """Return an RGB image (px x px) of the icon drawn in `color` on solid `bg`."""
    big = 256
    k = big / 100.0
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    lw = int(9 * k)
    thin = int(7 * k)

    def box(x0, y0, x1, y1):
        return [x0 * k, y0 * k, x1 * k, y1 * k]

    if kind == "mouse":
        d.rounded_rectangle(box(27, 6, 73, 94), radius=23 * k, outline=color, width=lw)
        d.line([50 * k, 8 * k, 50 * k, 44 * k], fill=color, width=thin)
        d.line([27 * k, 44 * k, 73 * k, 44 * k], fill=color, width=thin)
    elif kind == "keyboard":
        d.rounded_rectangle(box(5, 24, 95, 76), radius=10 * k, outline=color, width=lw)
        for x in (17, 33, 49, 65):
            d.rounded_rectangle(box(x, 36, x + 11, 45), radius=2 * k, fill=color)
        d.rounded_rectangle(box(25, 56, 75, 65), radius=3 * k, fill=color)
    elif kind == "headset":
        d.arc(box(18, 10, 82, 90), 180, 360, fill=color, width=lw)
        d.rounded_rectangle(box(8, 48, 30, 86), radius=9 * k, fill=color)
        d.rounded_rectangle(box(70, 48, 92, 86), radius=9 * k, fill=color)
    elif kind == "gamepad":
        d.rounded_rectangle(box(5, 26, 95, 74), radius=23 * k, outline=color, width=lw)
        d.line([19 * k, 50 * k, 37 * k, 50 * k], fill=color, width=thin)
        d.line([28 * k, 41 * k, 28 * k, 59 * k], fill=color, width=thin)
        d.ellipse(box(62, 39, 72, 49), fill=color)
        d.ellipse(box(74, 51, 84, 61), fill=color)
    elif kind == "speaker":
        d.polygon([(12 * k, 38 * k), (30 * k, 38 * k), (52 * k, 18 * k),
                   (52 * k, 82 * k), (30 * k, 62 * k), (12 * k, 62 * k)], fill=color)
        d.arc(box(40, 34, 74, 66), -55, 55, fill=color, width=int(8 * k))
        d.arc(box(36, 22, 90, 78), -55, 55, fill=color, width=int(8 * k))
    else:  # generic battery
        d.rounded_rectangle(box(6, 28, 84, 72), radius=9 * k, outline=color, width=lw)
        d.rounded_rectangle(box(86, 41, 95, 59), radius=3 * k, fill=color)
        d.rounded_rectangle(box(17, 39, 62, 61), radius=3 * k, fill=color)

    img = img.resize((px, px), Image.Resampling.LANCZOS)
    base = Image.new("RGB", (px, px), bg)
    base.paste(img, (0, 0), img)
    return base
