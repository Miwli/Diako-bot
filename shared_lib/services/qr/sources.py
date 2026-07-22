"""Background sources.

A source yields the frames that sit behind the QR. A still image is a single
frame; an animated source (phase 3) yields many. The rest of the pipeline only
ever iterates `frames()`, so adding animation needs no change here beyond a new
source class.
"""

import os

import shared_lib.db as db
from . import presets


def custom_background_path() -> str:
    """Where an admin-uploaded background is stored (per-install runtime data)."""
    return os.path.join(os.path.dirname(db.DB_PATH), "qr_bg_custom.png")


class StaticSource:
    """A single still image, from disk."""

    def __init__(self, path: str):
        self.path = path

    def frames(self):
        from PIL import Image
        return [Image.open(self.path).convert("RGB")]

    def key(self) -> str:
        """Identity used for caching — changes when the file changes."""
        try:
            st = os.stat(self.path)
            return f"{self.path}:{int(st.st_mtime)}:{st.st_size}"
        except OSError:
            return self.path


def resolve_background(cfg):
    """Return the configured background source, or None for a plain QR."""
    if not cfg.enabled or cfg.source in ("", "none"):
        return None
    if cfg.source == "custom":
        p = custom_background_path()
        return StaticSource(p) if os.path.exists(p) else None
    p = presets.preset_path(cfg.source)
    return StaticSource(p) if p and os.path.exists(p) else None
