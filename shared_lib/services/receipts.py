"""Receipt duplicate detection.

Fingerprints each payment receipt so a reused image can be flagged to the admin
before they approve it. Gated by the `receipt_duplicate_check_enabled` setting
so it can be switched off from the panel.

The fingerprint is a dHash: the image is reduced to a 9x8 grayscale grid and
each pixel is compared with its right-hand neighbour, giving 64 bits. It
survives rescaling and re-compression — which is what a screenshotted or
forwarded receipt goes through — and needs nothing beyond Pillow.
"""

import logging
from dataclasses import dataclass
from io import BytesIO

from shared_lib.db import (
    add_receipt_hash,
    get_receipt_hashes,
)
from shared_lib.services import features

log = logging.getLogger(__name__)

FLAG_KEY = "receipt_duplicate_check_enabled"

# Out of 64 bits. Identical images score 0; a re-encoded copy stays in the low
# single digits, while unrelated receipts sit far above this.
MAX_DISTANCE = 6

_HASH_WIDTH = 9
_HASH_HEIGHT = 8

# Admin-facing labels, kept here so the bot and the panel word a flag the same.
KIND_LABELS = {
    "order":        "سفارش",
    "topup":        "شارژ",
    "extra_time":   "افزودن زمان",
    "extra_volume": "افزودن حجم",
}


@dataclass
class DuplicateMatch:
    kind: str
    obj_id: int
    user_id: int
    distance: int


def perceptual_hash(image_bytes: bytes) -> str:
    """Return the dHash of an image as 16 hex chars."""
    from PIL import Image

    img = Image.open(BytesIO(image_bytes)).convert("L").resize(
        (_HASH_WIDTH, _HASH_HEIGHT), Image.LANCZOS
    )
    px = img.load()

    bits = 0
    for y in range(_HASH_HEIGHT):
        for x in range(_HASH_WIDTH - 1):
            bits = (bits << 1) | int(px[x, y] > px[x + 1, y])
    return f"{bits:016x}"


def distance(a: str, b: str) -> int:
    """Hamming distance between two hex fingerprints."""
    return bin(int(a, 16) ^ int(b, 16)).count("1")


async def check_receipt(kind: str, obj_id: int, user_id: int,
                        image_bytes: bytes) -> DuplicateMatch | None:
    """Fingerprint a receipt, store it, and report the closest earlier match.

    Returns None when the check is disabled, the image is unreadable, or
    nothing similar was stored before. Never raises: a receipt must still go
    through even if fingerprinting fails.
    """
    if not await features.is_enabled(FLAG_KEY, default=True):
        return None

    try:
        phash = perceptual_hash(image_bytes)
    except Exception as e:
        log.warning("receipt hashing failed for %s#%s: %s", kind, obj_id, e)
        return None

    try:
        best = None
        for row in await get_receipt_hashes():
            if row["kind"] == kind and row["obj_id"] == obj_id:
                continue  # don't match a re-submission against itself
            d = distance(phash, row["phash"])
            if d <= MAX_DISTANCE and (best is None or d < best.distance):
                best = DuplicateMatch(
                    kind=row["kind"], obj_id=row["obj_id"],
                    user_id=row["user_id"], distance=d,
                )

        await add_receipt_hash(
            kind, obj_id, user_id, phash,
            dup_kind=best.kind if best else None,
            dup_obj_id=best.obj_id if best else None,
            dup_distance=best.distance if best else None,
        )
        return best
    except Exception as e:
        log.warning("receipt duplicate check failed for %s#%s: %s", kind, obj_id, e)
        return None
