import asyncio
from io import BytesIO

from PIL import Image

from shared_lib.services import qr


def _png(color, size=(300, 300)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _open(png_bytes):
    return Image.open(BytesIO(png_bytes))


# ─── rendering ───

def test_plain_qr_is_valid_png():
    img = _open(qr.make_qr_png("https://example.com/sub/abc"))
    assert img.format == "PNG"
    assert img.size[0] > 0


def test_background_changes_the_output():
    plain = qr.make_qr_png("data", background=None)
    withbg = qr.make_qr_png("data", background=_png((200, 40, 40)))
    assert plain != withbg


def test_dark_modules_stay_solid_black():
    # A composited code must keep pure-black modules so it stays scannable.
    png = qr.make_qr_png("scan-me-123456", background=_png((30, 90, 160)))
    colors = _open(png).convert("RGB").getcolors(maxcolors=1_000_000)
    assert any(c[1] == (0, 0, 0) for c in colors)


def test_background_is_faded_not_raw():
    # The quiet-zone corner must be lightened, never the raw background colour.
    raw = (200, 40, 40)
    png = qr.make_qr_png("x", background=_png(raw))
    corner = _open(png).convert("RGB").getpixel((2, 2))
    assert corner != raw
    assert all(corner[i] > raw[i] for i in range(3))  # blended toward white


def test_bad_background_falls_back_to_plain():
    # Fingerprinting must never break QR delivery.
    png = qr.make_qr_png("x", background=b"not an image")
    assert _open(png).format == "PNG"


# ─── storage + flag ───

def test_save_and_remove_background(db_module):
    # db_module points DB_PATH at an isolated tmp dir; the background lives there.
    assert not qr.has_background()
    qr.save_background(_png((10, 10, 10)))
    assert qr.has_background()
    qr.remove_background()
    assert not qr.has_background()
    qr.remove_background()  # idempotent


def test_active_background_needs_flag_and_file(db_module):
    # file present, flag off -> nothing
    qr.save_background(_png((10, 10, 10)))
    asyncio.run(db_module.set_setting(qr.FLAG_KEY, "0"))
    assert qr._load_active_background() is None

    # flag on, file present -> bytes
    asyncio.run(db_module.set_setting(qr.FLAG_KEY, "1"))
    assert qr._load_active_background() is not None

    # flag on, file removed -> nothing
    qr.remove_background()
    assert qr._load_active_background() is None
