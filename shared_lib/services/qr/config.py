"""Render configuration for the QR background feature.

All values live in the shared `settings` table so the panel can change them
without a code change. `QrRenderConfig` is the typed, defaulted view of those
settings that the render pipeline consumes.
"""

from dataclasses import dataclass

import shared_lib.db as db

# Setting keys, grouped by build phase. Phase 2/3 keys are read here already so
# the config object is stable as those phases land.
KEY_ENABLED = "qr_bg_enabled"
KEY_SOURCE = "qr_bg_source"
KEY_SHAPE = "qr_canvas_shape"
KEY_BLUR_ENABLED = "qr_blur_enabled"
KEY_BLUR_AMOUNT = "qr_blur_amount"
KEY_PLATE_ENABLED = "qr_plate_enabled"
KEY_PLATE_RADIUS = "qr_plate_radius"
KEY_PLATE_PADDING = "qr_plate_padding"
KEY_POS_X = "qr_pos_x"
KEY_POS_Y = "qr_pos_y"
KEY_SIZE = "qr_size"
KEY_PLATE_COLOR = "qr_plate_color"   # phase 2
KEY_FG_COLOR = "qr_fg_color"         # phase 2
KEY_OUTPUT_FORMAT = "qr_output_format"  # phase 3

_ALL_KEYS = [
    KEY_ENABLED, KEY_SOURCE, KEY_SHAPE, KEY_BLUR_ENABLED, KEY_BLUR_AMOUNT,
    KEY_PLATE_ENABLED, KEY_PLATE_RADIUS, KEY_PLATE_PADDING, KEY_POS_X,
    KEY_POS_Y, KEY_SIZE, KEY_PLATE_COLOR, KEY_FG_COLOR, KEY_OUTPUT_FORMAT,
]

SHAPES = ("square", "original")


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def _as_bool(v, default=False):
    if v is None:
        return default
    return str(v) == "1"


def _as_int(v, default, lo, hi):
    try:
        return int(_clamp(int(float(v)), lo, hi))
    except (TypeError, ValueError):
        return default


def _as_float(v, default, lo, hi):
    try:
        return float(_clamp(float(v), lo, hi))
    except (TypeError, ValueError):
        return default


def parse_color(value: str, default=(0, 0, 0, 255)) -> tuple:
    """Parse #AARRGGBB or #RRGGBB into an (r, g, b, a) tuple."""
    if not value:
        return default
    s = value.lstrip("#").strip()
    try:
        if len(s) == 8:  # AARRGGBB
            a = int(s[0:2], 16); r = int(s[2:4], 16)
            g = int(s[4:6], 16); b = int(s[6:8], 16)
            return (r, g, b, a)
        if len(s) == 6:  # RRGGBB
            return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), 255)
    except ValueError:
        pass
    return default


@dataclass
class QrRenderConfig:
    enabled: bool = False
    source: str = "none"          # none | custom | <preset key>
    shape: str = "square"         # square | original
    blur_enabled: bool = True
    blur_amount: int = 40         # 0..100
    plate_enabled: bool = False
    plate_radius: int = 18        # 0..100 (% of plate size, up to fully round)
    plate_padding: int = 8        # 0..100 (% of QR size)
    pos_x: float = 0.5            # 0..1 (centre)
    pos_y: float = 0.5
    size: float = 0.6            # 0..1 (QR width vs canvas short side)
    plate_color: str = "#FFFFFFFF"  # phase 2
    fg_color: str = "#FF000000"     # phase 2
    output_format: str = "auto"     # phase 3

    def to_settings(self) -> dict:
        return {
            KEY_ENABLED: "1" if self.enabled else "0",
            KEY_SOURCE: self.source,
            KEY_SHAPE: self.shape,
            KEY_BLUR_ENABLED: "1" if self.blur_enabled else "0",
            KEY_BLUR_AMOUNT: str(self.blur_amount),
            KEY_PLATE_ENABLED: "1" if self.plate_enabled else "0",
            KEY_PLATE_RADIUS: str(self.plate_radius),
            KEY_PLATE_PADDING: str(self.plate_padding),
            KEY_POS_X: f"{self.pos_x:.4f}",
            KEY_POS_Y: f"{self.pos_y:.4f}",
            KEY_SIZE: f"{self.size:.4f}",
            KEY_PLATE_COLOR: self.plate_color,
            KEY_FG_COLOR: self.fg_color,
            KEY_OUTPUT_FORMAT: self.output_format,
        }


def from_map(m: dict) -> QrRenderConfig:
    """Build a config from a raw {key: value} settings map."""
    shape = m.get(KEY_SHAPE) or "square"
    if shape not in SHAPES:
        shape = "square"
    return QrRenderConfig(
        enabled=_as_bool(m.get(KEY_ENABLED)),
        source=m.get(KEY_SOURCE) or "none",
        shape=shape,
        blur_enabled=_as_bool(m.get(KEY_BLUR_ENABLED), default=True),
        blur_amount=_as_int(m.get(KEY_BLUR_AMOUNT), 40, 0, 100),
        plate_enabled=_as_bool(m.get(KEY_PLATE_ENABLED)),
        plate_radius=_as_int(m.get(KEY_PLATE_RADIUS), 18, 0, 100),
        plate_padding=_as_int(m.get(KEY_PLATE_PADDING), 8, 0, 100),
        pos_x=_as_float(m.get(KEY_POS_X), 0.5, 0.0, 1.0),
        pos_y=_as_float(m.get(KEY_POS_Y), 0.5, 0.0, 1.0),
        size=_as_float(m.get(KEY_SIZE), 0.6, 0.1, 1.0),
        plate_color=m.get(KEY_PLATE_COLOR) or "#FFFFFFFF",
        fg_color=m.get(KEY_FG_COLOR) or "#FF000000",
        output_format=m.get(KEY_OUTPUT_FORMAT) or "auto",
    )


def from_payload(p: dict) -> QrRenderConfig:
    """Build a config from a panel payload (friendly field names), coercing and
    clamping every value so nothing invalid reaches the renderer."""
    from . import presets

    shape = p.get("shape") or "square"
    if shape not in SHAPES:
        shape = "square"
    source = str(p.get("source") or "none")
    if source not in ("none", "custom") and source not in presets.PRESETS:
        source = "none"
    return QrRenderConfig(
        enabled=bool(p.get("enabled")),
        source=source,
        shape=shape,
        blur_enabled=bool(p.get("blur_enabled")),
        blur_amount=_as_int(p.get("blur_amount"), 40, 0, 100),
        plate_enabled=bool(p.get("plate_enabled")),
        plate_radius=_as_int(p.get("plate_radius"), 18, 0, 100),
        plate_padding=_as_int(p.get("plate_padding"), 8, 0, 100),
        pos_x=_as_float(p.get("pos_x"), 0.5, 0.0, 1.0),
        pos_y=_as_float(p.get("pos_y"), 0.5, 0.0, 1.0),
        size=_as_float(p.get("size"), 0.6, 0.1, 1.0),
        plate_color=str(p.get("plate_color") or "#FFFFFFFF"),
        fg_color=str(p.get("fg_color") or "#FF000000"),
    )


def load_config() -> QrRenderConfig:
    """Read the current config from the settings table (sync, single query)."""
    return from_map(db.get_settings_sync(_ALL_KEYS))
