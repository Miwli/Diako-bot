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
preset_is_animated = presets.preset_is_animated


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

    # Animate only in card mode: the code stays on a static opaque plate every
    # frame, so it keeps its contrast while the background moves around it.
    animate = cfg.plate_enabled and getattr(src, "animated", False)

    try:
        if animate:
            prepared = cache.prepared_frames(src, cfg)
            frames = [compose.render_frame(p, data, cfg) for p in prepared]
            return encode(frames, cfg, src.durations())
        prepared = cache.prepared_background(src, cfg)
        return encode([compose.render_frame(prepared, data, cfg)], cfg)
    except Exception as e:
        log.warning("QR render failed, sending plain QR: %s", e)
        return encode([compose.plain_qr(data)], cfg)


def make_qr_png(data: str) -> bytes:
    """PNG bytes of the rendered QR (back-compat helper)."""
    return render_qr(data).data


# ─── admin-uploaded custom background ───

def save_background(image_bytes: bytes) -> bool:
    """Store an uploaded image as the custom background.

    An animated GIF is kept as a GIF (frames preserved); anything else is
    flattened to PNG. Returns True when the stored background is animated.
    """
    from io import BytesIO
    from PIL import Image

    img = Image.open(BytesIO(image_bytes))
    animated = getattr(img, "is_animated", False) and getattr(img, "n_frames", 1) > 1
    remove_background()
    if animated:
        img.save(sources._custom_path("gif"), format="GIF", save_all=True)
    else:
        img.convert("RGB").save(sources._custom_path("png"), format="PNG")
    return animated


def remove_background() -> None:
    import os
    for ext in ("gif", "png"):
        try:
            os.remove(sources._custom_path(ext))
        except FileNotFoundError:
            pass


def has_background() -> bool:
    import os
    return any(os.path.exists(sources._custom_path(e)) for e in ("gif", "png"))


def custom_is_animated() -> bool:
    import os
    return os.path.exists(sources._custom_path("gif"))


# Back-compat alias for callers that used the old single-file path name.
qr_background_path = custom_background_path
