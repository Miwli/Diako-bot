"""QR rendering shared by the bot and the panel.

Public entry point is `render_qr(data)`, which returns a `RenderedQr(data, mime)`
so callers send the result by MIME type — a still image today, an animation
later — without changing. The heavy background prep is cached (see cache.py).

`make_qr_png` stays as a thin PNG-bytes helper for existing callers.
"""

import logging

from . import cache, compose, presets, sources
from .config import QrRenderConfig, load_config
from .encode import RenderedQr, encode
from .sources import custom_background_path, resolve_background

log = logging.getLogger(__name__)

# The panel toggles the feature through this key.
FLAG_KEY = "qr_bg_enabled"

# Re-exports so callers can reach presets without importing the submodule.
preset_keys = presets.preset_keys
preset_path = presets.preset_path


def render_qr(data: str, cfg: QrRenderConfig | None = None) -> RenderedQr:
    """Render `data` as a QR, composited over the configured background.

    Falls back to a plain QR when the feature is off, no background is set, or
    anything in the pipeline fails — a QR must always go out.
    """
    if cfg is None:
        cfg = load_config()

    src = resolve_background(cfg)
    if src is None:
        return encode([compose.plain_qr(data)], cfg)

    try:
        prepared = cache.prepared_background(src, cfg)
        frame = compose.render_frame(prepared, data, cfg)
        return encode([frame], cfg)
    except Exception as e:
        log.warning("QR render failed, sending plain QR: %s", e)
        return encode([compose.plain_qr(data)], cfg)


def make_qr_png(data: str) -> bytes:
    """PNG bytes of the rendered QR (back-compat helper)."""
    return render_qr(data).data


# ─── admin-uploaded custom background ───

def save_background(image_bytes: bytes) -> None:
    """Normalise an uploaded image to PNG and store it as the custom background."""
    from io import BytesIO
    from PIL import Image

    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    img.save(custom_background_path(), format="PNG")


def remove_background() -> None:
    import os
    try:
        os.remove(custom_background_path())
    except FileNotFoundError:
        pass


def has_background() -> bool:
    import os
    return os.path.exists(custom_background_path())


# Back-compat alias for callers that used the old single-file path name.
qr_background_path = custom_background_path
