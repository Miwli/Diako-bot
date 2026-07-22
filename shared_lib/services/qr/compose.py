"""Pure image compositing — no I/O, no settings reads.

Two stages, kept separate so the expensive one (background prep) can be cached
and the cheap one (placing the QR) can run per render or be mirrored in the
panel's canvas preview:

  prepare_background(image, cfg, size) -> the blurred/shaped canvas
  render_frame(prepared, data, cfg)   -> the canvas with the QR composited on
"""

import qrcode
from PIL import Image, ImageDraw, ImageFilter

from .config import parse_color

# Long side of the rendered output, in pixels.
OUTPUT_LONG = 1024

# Max blur radius as a fraction of the canvas short side (at blur_amount = 100).
_BLUR_MAX = 0.08


def _clampf(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def canvas_size(bg_w: int, bg_h: int, cfg, long: int = OUTPUT_LONG) -> tuple:
    """Target canvas size for a given background and shape setting."""
    if cfg.shape == "original":
        if bg_w >= bg_h:
            return (long, max(1, round(long * bg_h / bg_w)))
        return (max(1, round(long * bg_w / bg_h)), long)
    return (long, long)  # square


def prepare_background(image: "Image.Image", cfg, long: int = OUTPUT_LONG) -> "Image.Image":
    """Shape the background to the canvas and apply blur. Returns RGB."""
    img = image.convert("RGB")
    w, h = img.size
    out_w, out_h = canvas_size(w, h, cfg, long)

    if cfg.shape == "original":
        img = img.resize((out_w, out_h), Image.LANCZOS)
    else:
        # centre-crop to a square, then resize
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        img = img.crop((left, top, left + side, top + side)).resize(
            (out_w, out_h), Image.LANCZOS
        )

    if cfg.blur_enabled and cfg.blur_amount > 0:
        radius = (cfg.blur_amount / 100.0) * min(out_w, out_h) * _BLUR_MAX
        if radius > 0:
            img = img.filter(ImageFilter.GaussianBlur(radius))
    return img


def qr_layer(data: str, size: int, fg: tuple) -> "Image.Image":
    """A transparent RGBA image of the QR: modules in `fg`, quiet area clear."""
    qr = qrcode.QRCode(border=4)
    qr.add_data(data)
    qr.make(fit=True)
    base = qr.make_image(fill_color="black", back_color="white").get_image()
    base = base.convert("L").resize((size, size), Image.NEAREST)

    mask = base.point(lambda p: 255 if p < 128 else 0).convert("L")
    solid = Image.new("RGBA", (size, size), fg)
    clear = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    return Image.composite(solid, clear, mask)


def render_frame(prepared: "Image.Image", data: str, cfg) -> "Image.Image":
    """Composite the plate (optional) and the QR onto a prepared background."""
    canvas = prepared.convert("RGBA")
    w, h = canvas.size
    short = min(w, h)

    qr_w = max(1, round(short * _clampf(cfg.size, 0.1, 1.0)))
    cx = cfg.pos_x * w
    cy = cfg.pos_y * h
    x0 = round(cx - qr_w / 2)
    y0 = round(cy - qr_w / 2)

    if cfg.plate_enabled:
        pad = round(qr_w * _clampf(cfg.plate_padding, 0, 100) / 100)
        px0, py0 = x0 - pad, y0 - pad
        px1, py1 = x0 + qr_w + pad, y0 + qr_w + pad
        radius = round((px1 - px0) * _clampf(cfg.plate_radius, 0, 100) / 200)
        overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(overlay).rounded_rectangle(
            [px0, py0, px1, py1], radius=radius, fill=parse_color(cfg.plate_color, (255, 255, 255, 255))
        )
        canvas = Image.alpha_composite(canvas, overlay)

    qr_rgba = qr_layer(data, qr_w, parse_color(cfg.fg_color, (0, 0, 0, 255)))
    canvas.alpha_composite(qr_rgba, (x0, y0))
    return canvas.convert("RGB")


def plain_qr(data: str) -> "Image.Image":
    """The default black-on-white QR, used when no background is active."""
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").get_image().convert("RGB")
