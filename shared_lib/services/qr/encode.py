"""Output encoding.

Turns the composited frame(s) into the bytes the bot sends, plus the MIME type
so callers pick sendPhoto vs (phase 3) sendAnimation without changing. Today
there is always a single frame and the output is PNG.
"""

from dataclasses import dataclass
from io import BytesIO


@dataclass
class RenderedQr:
    data: bytes
    mime: str


def encode(frames: list, cfg) -> RenderedQr:
    """Encode the composited frames. Single frame -> PNG."""
    buf = BytesIO()
    frames[0].convert("RGB").save(buf, format="PNG")
    return RenderedQr(buf.getvalue(), "image/png")
