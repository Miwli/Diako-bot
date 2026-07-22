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


def _key(source, cfg, long: int) -> str:
    blur = cfg.blur_amount if cfg.blur_enabled else 0
    raw = f"{source.key()}|{blur}|{cfg.shape}|{long}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def prepared_background(source, cfg, long: int = compose.OUTPUT_LONG) -> "object":
    """Return the prepared background for a source, hitting disk cache first."""
    from PIL import Image

    path = _cache_dir() / f"{_key(source, cfg, long)}.png"
    if path.exists():
        return Image.open(path).convert("RGB")

    prep = compose.prepare_background(source.frames()[0], cfg, long)
    prep.save(path, "PNG")
    return prep
