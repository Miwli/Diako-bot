"""Built-in background presets shipped with the app.

The images live as static assets in the repo (design assets, not user data).
Selecting a preset only stores its key in settings; the image is read from here
at render time, so improving a preset in a later release reaches every install.
"""

import os

# Ordered registry: key -> filename in the assets dir.
PRESETS = ("aurora", "azure", "onyx")

_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "assets", "qr_presets")
)


def preset_keys() -> list:
    return list(PRESETS)


def preset_path(key: str):
    """Absolute path to a preset image, or None for an unknown key."""
    if key not in PRESETS:
        return None
    return os.path.join(_DIR, f"{key}.png")
