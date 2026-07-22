"""Background sources.

A source yields the frames that sit behind the QR. A still image is a single
frame; an animated one (a GIF) yields many. The rest of the pipeline only
iterates `frames()`, so animation needs nothing beyond this extra source class.
"""

import os

import shared_lib.db as db
from . import presets

_CUSTOM_BASE = "qr_bg_custom"
# Cap frames so a long GIF can't blow up render time or output size.
MAX_FRAMES = 30


def _custom_path(ext: str) -> str:
    return os.path.join(os.path.dirname(db.DB_PATH), f"{_CUSTOM_BASE}.{ext}")


def custom_background_path() -> str:
    """The stored custom background — an animated .gif if present, else .png.

    Returns the .png path when neither exists, so callers can still test it.
    """
    for ext in ("gif", "png"):
        p = _custom_path(ext)
        if os.path.exists(p):
            return p
    return _custom_path("png")


class StaticSource:
    """A single still image, from disk."""

    animated = False

    def __init__(self, path: str):
        self.path = path

    def frames(self):
        from PIL import Image
        return [Image.open(self.path).convert("RGB")]

    def durations(self):
        return [0]

    def key(self) -> str:
        return _file_key(self.path)


class AnimatedSource:
    """An animated GIF, read frame by frame (capped at MAX_FRAMES)."""

    animated = True

    def __init__(self, path: str):
        self.path = path
        self._frames = None
        self._durations = None

    def _ensure(self):
        if self._frames is None:
            from PIL import Image, ImageSequence
            frames, durations = [], []
            im = Image.open(self.path)
            for i, fr in enumerate(ImageSequence.Iterator(im)):
                if i >= MAX_FRAMES:
                    break
                frames.append(fr.convert("RGB"))
                durations.append(int(fr.info.get("duration", 80)) or 80)
            self._frames, self._durations = frames, durations
        return self._frames, self._durations

    def frames(self):
        return self._ensure()[0]

    def durations(self):
        return self._ensure()[1]

    def key(self) -> str:
        return _file_key(self.path)


def _file_key(path: str) -> str:
    """Identity used for caching — changes when the file changes."""
    try:
        st = os.stat(path)
        return f"{path}:{int(st.st_mtime)}:{st.st_size}"
    except OSError:
        return path


def resolve_background(cfg):
    """Return the configured background source, or None for a plain QR."""
    if not cfg.enabled or cfg.source in ("", "none"):
        return None
    if cfg.source == "custom":
        gif = _custom_path("gif")
        if os.path.exists(gif):
            return AnimatedSource(gif)
        png = _custom_path("png")
        return StaticSource(png) if os.path.exists(png) else None
    p = presets.preset_path(cfg.source)
    return StaticSource(p) if p and os.path.exists(p) else None
