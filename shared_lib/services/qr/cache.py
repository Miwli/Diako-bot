"""Disk cache for the prepared (blurred + shaped) background.

Blur is the one heavy step and its result is identical for every user of a bot
until the admin changes the background, blur, or shape. Caching it means each
render is just "paste a QR onto a ready image", which stays cheap at scale.
"""

import hashlib
import pathlib

import shared_lib.db as db
from . import compose


def _cache_dir() -> pathlib.Path:
    d = pathlib.Path(db.DB_PATH).parent / "qr_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _key(source, cfg, long: int, frame: int = 0) -> str:
    blur = cfg.blur_amount if cfg.blur_enabled else 0
    raw = f"{source.key()}|{blur}|{cfg.shape}|{long}|{frame}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def _prepare_cached(frame_img, source, cfg, long, index):
    from PIL import Image
    path = _cache_dir() / f"{_key(source, cfg, long, index)}.png"
    if path.exists():
        return Image.open(path).convert("RGB")
    prep = compose.prepare_background(frame_img, cfg, long)
    prep.save(path, "PNG")
    return prep


def prepared_background(source, cfg, long: int = compose.OUTPUT_LONG) -> "object":
    """Prepared first frame of a source (the still-image path), disk-cached."""
    return _prepare_cached(source.frames()[0], source, cfg, long, 0)


def prepared_frames(source, cfg, long: int = compose.ANIM_LONG) -> list:
    """Prepared frames of an animated source, each disk-cached by index."""
    return [
        _prepare_cached(fr, source, cfg, long, i)
        for i, fr in enumerate(source.frames())
    ]
