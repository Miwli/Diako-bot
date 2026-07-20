import random
from io import BytesIO

from PIL import Image, ImageDraw

import shared_lib.db as db
from shared_lib.services import receipts


def _receipt_image(seed: int, size=(600, 900)) -> Image.Image:
    """A fake receipt with enough structure to fingerprint."""
    rnd = random.Random(seed)
    img = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(img)
    for i in range(14):
        top = 60 + i * 55
        draw.rectangle([40, top, 40 + rnd.randint(150, 520), top + 35], fill=(30, 30, 30))
    draw.rectangle([300, 700, 560, 860], fill=(200, 40, 40))
    return img


def _png(img: Image.Image, fmt="PNG", **kw) -> bytes:
    buf = BytesIO()
    img.save(buf, format=fmt, **kw)
    return buf.getvalue()


# ─── hashing ───

def test_same_image_hashes_identically():
    data = _png(_receipt_image(1))
    assert receipts.perceptual_hash(data) == receipts.perceptual_hash(data)


def test_survives_jpeg_recompression():
    img = _receipt_image(1)
    d = receipts.distance(
        receipts.perceptual_hash(_png(img)),
        receipts.perceptual_hash(_png(img, fmt="JPEG", quality=55)),
    )
    assert d <= receipts.MAX_DISTANCE


def test_survives_rescaling():
    img = _receipt_image(1)
    shrunk = img.resize((300, 450)).resize((600, 900))
    d = receipts.distance(
        receipts.perceptual_hash(_png(img)),
        receipts.perceptual_hash(_png(shrunk)),
    )
    assert d <= receipts.MAX_DISTANCE


def test_different_receipts_are_far_apart():
    d = receipts.distance(
        receipts.perceptual_hash(_png(_receipt_image(1))),
        receipts.perceptual_hash(_png(_receipt_image(99))),
    )
    assert d > receipts.MAX_DISTANCE


# ─── check_receipt ───

async def test_first_receipt_has_no_match(db_module):
    match = await receipts.check_receipt("order", 1, 100, _png(_receipt_image(1)))
    assert match is None
    assert await db.get_receipt_flag("order", 1) is None


async def test_reused_image_is_flagged(db_module):
    img = _png(_receipt_image(1))
    await receipts.check_receipt("order", 1, 100, img)

    match = await receipts.check_receipt("order", 2, 200, img)
    assert match is not None
    assert (match.kind, match.obj_id, match.user_id) == ("order", 1, 100)
    assert match.distance == 0


async def test_flag_is_persisted_for_the_panel(db_module):
    img = _png(_receipt_image(1))
    await receipts.check_receipt("order", 1, 100, img)
    await receipts.check_receipt("topup", 5, 200, img)

    flag = await db.get_receipt_flag("topup", 5)
    assert flag["dup_kind"] == "order"
    assert flag["dup_obj_id"] == 1

    assert set(await db.get_flagged_receipts("topup")) == {5}
    assert await db.get_flagged_receipts("order") == {}


async def test_match_crosses_kinds(db_module):
    """A receipt reused between a top-up and an order still matches."""
    img = _png(_receipt_image(3))
    await receipts.check_receipt("topup", 7, 100, img)

    match = await receipts.check_receipt("order", 8, 100, img)
    assert match is not None
    assert (match.kind, match.obj_id) == ("topup", 7)


async def test_distinct_receipts_are_not_flagged(db_module):
    await receipts.check_receipt("order", 1, 100, _png(_receipt_image(1)))
    match = await receipts.check_receipt("order", 2, 200, _png(_receipt_image(99)))
    assert match is None


async def test_closest_match_wins(db_module):
    """A near-miss stored first must lose to an exact match stored later."""
    img = _png(_receipt_image(1))
    exact = receipts.perceptual_hash(img)
    near = f"{int(exact, 16) ^ 0b1111:016x}"  # 4 bits off — inside the threshold

    await db.add_receipt_hash("order", 1, 100, near)
    await db.add_receipt_hash("order", 2, 100, exact)

    match = await receipts.check_receipt("order", 3, 200, img)
    assert (match.obj_id, match.distance) == (2, 0)


async def test_tie_goes_to_the_earliest_receipt(db_module):
    """Two identical stored receipts: report the first one, not the newest."""
    img = _png(_receipt_image(1))
    await receipts.check_receipt("order", 1, 100, img)
    await receipts.check_receipt("order", 2, 100, img)

    match = await receipts.check_receipt("order", 3, 200, img)
    assert match.obj_id == 1


async def test_disabled_flag_skips_everything(db_module):
    await db.set_setting(receipts.FLAG_KEY, "0")
    img = _png(_receipt_image(1))
    await receipts.check_receipt("order", 1, 100, img)

    assert await receipts.check_receipt("order", 2, 200, img) is None
    # nothing stored at all, so turning it back on starts from a clean slate
    assert await db.get_receipt_hashes() == []


async def test_unreadable_image_is_ignored(db_module):
    assert await receipts.check_receipt("order", 1, 100, b"not an image") is None
    assert await db.get_receipt_hashes() == []


async def test_resubmission_does_not_match_itself(db_module):
    img = _png(_receipt_image(1))
    await receipts.check_receipt("order", 1, 100, img)
    assert await receipts.check_receipt("order", 1, 100, img) is None
