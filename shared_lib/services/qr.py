"""QR rendering shared by the bot and the panel.

Returns raw PNG bytes and stays free of aiogram types, so the bot wraps the
result in a BufferedInputFile while the panel posts it straight to sendPhoto.

An admin can upload a background image from the panel; when the feature is on
and an image exists it is composited behind the code here, so callers never
change.
"""

import logging
import os
from io import BytesIO

import qrcode

import shared_lib.db as db

log = logging.getLogger(__name__)

FLAG_KEY = "qr_background_enabled"

# How far the background is faded toward white before the code is drawn on top.
# Higher keeps more contrast (safer scanning), lower shows the image stronger.
_FADE = 0.55


def qr_background_path() -> str:
    """Where the admin-uploaded background lives, next to the shared DB."""
    return os.path.join(os.path.dirname(db.DB_PATH), "qr_background.png")


def save_background(image_bytes: bytes) -> None:
    """Normalise an uploaded image to PNG and store it as the QR background."""
    from PIL import Image

    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    img.save(qr_background_path(), format="PNG")


def remove_background() -> None:
    """Delete the stored background, if any."""
    try:
        os.remove(qr_background_path())
    except FileNotFoundError:
        pass


def has_background() -> bool:
    return os.path.exists(qr_background_path())


def _load_active_background() -> bytes | None:
    """Return the background bytes when the feature is on and a file exists."""
    if db.get_setting_sync(FLAG_KEY) != "1":
        return None
    try:
        with open(qr_background_path(), "rb") as f:
            return f.read()
    except FileNotFoundError:
        return None


def _compose(qr_img, background_bytes: bytes) -> "object":
    """Draw the QR's dark modules over a faded copy of the background image.

    The dark modules stay solid black so the code keeps its contrast, while the
    faded image shows through the light modules.
    """
    from PIL import Image

    size = qr_img.size
    gray = qr_img.convert("L")  # dark modules -> 0, light -> 255

    bg = Image.open(BytesIO(background_bytes)).convert("RGB").resize(
        size, Image.LANCZOS
    )
    bg = Image.blend(bg, Image.new("RGB", size, "white"), _FADE)

    black = Image.new("RGB", size, "black")
    mask = gray.point(lambda p: 255 if p < 128 else 0)  # dark modules -> 255
    return Image.composite(black, bg, mask)


def make_qr_png(data: str, *, box_size: int = 10, border: int = 4,
                background: bytes | None = None) -> bytes:
    """Render `data` as a QR code and return the PNG bytes.

    Single choke point for QR appearance. When a background image is active it
    is composited in here; pass `background` explicitly to override the stored
    one (used in tests).
    """
    qr = qrcode.QRCode(box_size=box_size, border=border)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").get_image()

    if background is None:
        background = _load_active_background()
    if background:
        try:
            img = _compose(img, background)
        except Exception as e:
            log.warning("QR background compositing failed: %s", e)

    buf = BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()
