"""Built-in background presets shipped with the app.

The images live as static assets in the repo (design assets, not user data).
Selecting a preset only stores its key in settings; the image is read from here
at render time, so improving a preset in a later release reaches every install.
"""

import os

# Ordered registry of preset keys. Each has a matching image in the assets dir,
# either a still .png or an animated .gif (resolved at read time).
PRESETS = ("aurora", "azure", "onyx", "samurai")

# Probed in order, so an animated preset wins over a still one with the same key.
_EXTS = ("gif", "png")

_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "assets", "qr_presets")
)


def preset_keys() -> list:
    return list(PRESETS)


def preset_path(key: str):
    """Absolute path to a preset image, or None for an unknown key.

    Returns the .gif if one is shipped for the key, else the .png. Falls back to
    the .png path (which may not exist) so callers can still test for it.
    """
    if key not in PRESETS:
        return None
    for ext in _EXTS:
        p = os.path.join(_DIR, f"{key}.{ext}")
        if os.path.exists(p):
            return p
    return os.path.join(_DIR, f"{key}.png")


def preset_is_animated(key: str) -> bool:
    """True when the preset ships as an animated GIF."""
    p = preset_path(key)
    return bool(p) and p.lower().endswith(".gif") and os.path.exists(p)
