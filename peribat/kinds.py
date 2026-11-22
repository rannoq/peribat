"""Device types and a guess of the type from a device name."""
from __future__ import annotations

KINDS = ("mouse", "keyboard", "headset", "gamepad", "speaker", "generic")

_NAME_HINTS = (
    ("headset", ("headset", "headphone", "earbud", "buds", "airpods", "arctis", "cloud ii",
                 "cloud iii", "cloud alpha", "cloud flight", "kraken", "barracuda", "astro a",
                 "void", "virtuoso", "hs80", "hs70", "g733", "g535", "g935", "wh-1000",
                 "wf-1000", "jabra", "earphone")),
    ("gamepad", ("controller", "gamepad", "xbox", "dualsense", "dualshock", "joy-con", "8bitdo")),
    ("speaker", ("speaker", "soundbar", "boombox", "soundcore")),
    ("keyboard", ("keyboard", "keychron", "k380", "k780", "mx keys", "g915", "g613", "g512",
                  "k400", "k520", "huntsman", "blackwidow", "aula", "f75", "f87", "apex")),
    ("mouse", ("mouse", "mice", "superlight", "g305", "g502", "g703", "g903", "g604",
               "g pro wireless", "deathadder", "viper", "basilisk", "naga", "mx master",
               "mx anywhere", "trackball", "pulsefire", "harpoon", "glorious", "model o",
               "aerox", "rival", "cobra", "orochi", "lancehead", "mamba")),
)


def guess_kind(name: str) -> str:
    lowered = (name or "").lower()
    for kind, words in _NAME_HINTS:
        if any(word in lowered for word in words):
            return kind
    return "generic"
