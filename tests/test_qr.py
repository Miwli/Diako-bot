import asyncio
from io import BytesIO

from PIL import Image

from shared_lib.services import qr
from shared_lib.services.qr import compose, config, presets, sources


def _png(color, size=(400, 400)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _open(data):
    return Image.open(BytesIO(data))


# ─── config ───

def test_parse_color_argb_and_rgb():
    assert config.parse_color("#FF112233") == (0x11, 0x22, 0x33, 0xFF)
    assert config.parse_color("#112233") == (0x11, 0x22, 0x33, 255)
    assert config.parse_color("garbage", default=(1, 2, 3, 4)) == (1, 2, 3, 4)


def test_config_defaults_and_roundtrip():
    c = config.from_map({})
    assert c.enabled is False and c.source == "none" and c.shape == "square"
    # values survive a to_settings -> from_map round trip
    c2 = config.QrRenderConfig(enabled=True, source="azure", blur_amount=70,
                               plate_enabled=True, pos_x=0.25, size=0.5)
    back = config.from_map(c2.to_settings())
    assert back.enabled and back.source == "azure" and back.blur_amount == 70
    assert back.plate_enabled and abs(back.pos_x - 0.25) < 1e-6 and abs(back.size - 0.5) < 1e-6


def test_config_clamps_out_of_range():
    c = config.from_map({config.KEY_BLUR_AMOUNT: "999", config.KEY_SIZE: "5",
                         config.KEY_SHAPE: "weird"})
    assert c.blur_amount == 100 and c.size == 1.0 and c.shape == "square"


# ─── presets ───

def test_preset_files_exist():
    for key in presets.preset_keys():
        p = presets.preset_path(key)
        assert p and __import__("os").path.exists(p), f"missing preset {key}"


def test_unknown_preset_has_no_path():
    assert presets.preset_path("nope") is None


# ─── rendering ───

def test_disabled_gives_plain_png():
    r = qr.render_qr("data", config.QrRenderConfig(enabled=False))
    assert r.mime == "image/png"
    assert _open(r.data).format == "PNG"


def test_preset_source_composites(db_module, monkeypatch):
    cfg = config.QrRenderConfig(enabled=True, source="aurora", blur_enabled=False)
    plain = qr.render_qr("data", config.QrRenderConfig(enabled=False))
    withbg = qr.render_qr("data", cfg)
    assert withbg.data != plain.data
    assert _open(withbg.data).size == (compose.OUTPUT_LONG, compose.OUTPUT_LONG)


def test_original_shape_keeps_aspect(db_module):
    cfg = config.QrRenderConfig(enabled=True, source="custom", shape="original",
                                blur_enabled=False)
    p = sources.custom_background_path()
    Image.new("RGB", (800, 400), (40, 90, 160)).save(p, "PNG")
    r = qr.render_qr("data", cfg)
    w, h = _open(r.data).size
    assert w == compose.OUTPUT_LONG and h == compose.OUTPUT_LONG // 2


def test_qr_modules_stay_solid(db_module):
    cfg = config.QrRenderConfig(enabled=True, source="onyx", blur_enabled=False)
    colors = _open(qr.render_qr("scan-me", cfg).data).convert("RGB").getcolors(1_000_000)
    assert any(c[1] == (0, 0, 0) for c in colors)


def test_plate_adds_white_behind_qr(db_module):
    base = config.QrRenderConfig(enabled=True, source="onyx", blur_enabled=False)
    plated = config.QrRenderConfig(enabled=True, source="onyx", blur_enabled=False,
                                   plate_enabled=True)
    a = _open(qr.render_qr("x", base).data)
    b = _open(qr.render_qr("x", plated).data)
    # onyx is very dark; a white plate raises the count of near-white pixels
    def near_white(im):
        return sum(n for n, c in im.convert("RGB").getcolors(1_000_000)
                   if min(c) > 230)
    assert near_white(b) > near_white(a)


def test_broken_background_falls_back_to_plain(db_module):
    cfg = config.QrRenderConfig(enabled=True, source="custom", blur_enabled=False)
    with open(sources.custom_background_path(), "wb") as f:
        f.write(b"not an image")
    r = qr.render_qr("x", cfg)
    assert _open(r.data).format == "PNG"


# ─── custom upload storage ───

def test_save_and_remove_custom_background(db_module):
    assert not qr.has_background()
    qr.save_background(_png((10, 10, 10)))
    assert qr.has_background()
    qr.remove_background()
    assert not qr.has_background()
    qr.remove_background()  # idempotent


# ─── cache ───

def test_prepared_background_is_cached(db_module):
    import pathlib
    from shared_lib.services.qr import cache
    cfg = config.QrRenderConfig(enabled=True, source="aurora", blur_amount=50)
    src = sources.resolve_background(cfg)
    cache.prepared_background(src, cfg)
    cache_dir = pathlib.Path(db_module.DB_PATH).parent / "qr_cache"
    assert list(cache_dir.glob("*.png")), "expected a cached background file"


# ─── animated (GIF) backgrounds ───

def _gif(colors, size=(120, 120)) -> bytes:
    frames = [Image.new("RGB", size, c) for c in colors]
    buf = BytesIO()
    frames[0].save(buf, format="GIF", save_all=True, append_images=frames[1:],
                   duration=100, loop=0)
    return buf.getvalue()


def test_animated_upload_is_detected(db_module):
    assert qr.save_background(_gif([(200, 0, 0), (0, 200, 0)])) is True
    assert qr.has_background() and qr.custom_is_animated()


def test_static_upload_is_not_animated(db_module):
    assert qr.save_background(_png((10, 10, 10))) is False
    assert qr.has_background() and not qr.custom_is_animated()


def test_upload_switches_type_cleanly(db_module):
    qr.save_background(_gif([(1, 2, 3), (4, 5, 6)]))
    assert qr.custom_is_animated()
    qr.save_background(_png((9, 9, 9)))          # replace GIF with a still image
    assert qr.has_background() and not qr.custom_is_animated()


def test_card_mode_produces_a_gif(db_module):
    qr.save_background(_gif([(200, 0, 0), (0, 200, 0), (0, 0, 200)]))
    cfg = config.QrRenderConfig(enabled=True, source="custom",
                                plate_enabled=True, blur_enabled=False)
    r = qr.render_qr("scan-me", cfg)
    assert r.mime == "image/gif"
    assert _open(r.data).n_frames == 3


def test_animated_without_plate_stays_static(db_module):
    qr.save_background(_gif([(200, 0, 0), (0, 200, 0)]))
    cfg = config.QrRenderConfig(enabled=True, source="custom",
                                plate_enabled=False, blur_enabled=False)
    assert qr.render_qr("x", cfg).mime == "image/png"


def test_still_preset_never_animates(db_module):
    cfg = config.QrRenderConfig(enabled=True, source="onyx",
                                plate_enabled=True, blur_enabled=False)
    assert qr.render_qr("x", cfg).mime == "image/png"


def test_animated_preset_is_detected():
    assert presets.preset_is_animated("samurai")
    assert not presets.preset_is_animated("aurora")


def test_animated_preset_card_mode_produces_a_gif(db_module):
    cfg = config.QrRenderConfig(enabled=True, source="samurai",
                                plate_enabled=True, blur_enabled=False)
    r = qr.render_qr("scan-me", cfg)
    assert r.mime == "image/gif"
    assert _open(r.data).n_frames > 1
