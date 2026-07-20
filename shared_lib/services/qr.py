"""QR rendering shared by the bot and the panel.

Returns raw PNG bytes and stays free of aiogram types, so the bot wraps the
result in a BufferedInputFile while the panel posts it straight to sendPhoto.
"""

from io import BytesIO

import qrcode


def make_qr_png(data: str, *, box_size: int = 10, border: int = 4) -> bytes:
    """Render `data` as a QR code and return the PNG bytes.

    Single choke point for QR appearance: a future admin-supplied background
    image gets composed here, so callers never change.
    """
    qr = qrcode.QRCode(box_size=box_size, border=border)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
