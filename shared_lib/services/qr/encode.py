"""Output encoding.

Turns the composited frame(s) into the bytes the bot sends, plus the MIME type
so callers pick sendPhoto vs sendAnimation without changing. A single frame is
a PNG; several frames become an animated GIF.
"""

from dataclasses import dataclass
from io import BytesIO


@dataclass
class RenderedQr:
    data: bytes
    mime: str


def encode(frames: list, cfg, durations=None) -> RenderedQr:
    """Encode composited frames: one -> PNG, many -> animated GIF."""
    if len(frames) <= 1:
        buf = BytesIO()
        frames[0].convert("RGB").save(buf, format="PNG")
        return RenderedQr(buf.getvalue(), "image/png")

    conv = [f.convert("RGB") for f in frames]
    durs = durations or [80] * len(conv)
    buf = BytesIO()
    conv[0].save(
        buf, format="GIF", save_all=True, append_images=conv[1:],
        duration=durs, loop=0, disposal=1, optimize=True,
    )
    return RenderedQr(buf.getvalue(), "image/gif")
