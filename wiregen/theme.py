"""Visual tokens and the selectable theme registry.

A Theme is the single place that defines the look: canvas, bodies, pins, wires,
cards, plus the wire/net colour palette (so colours adapt to the background; a
ground wire is light on a dark scheme and dark on a light one). Bus family
colours come from standards.py but a theme may override them via ``signals``.

Pick a theme with the diagram's ``theme:`` field or the CLI ``--theme`` flag;
``list-themes`` enumerates them. Default: ``neutral-dark``.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

# Net palettes; ground/power must stay legible against the background.
DARK_NETS = {
    "gnd": "#cbd5e1", "agnd": "#cbd5e1", "3v3": "#fbbf24",
    "5v": "#f87171", "vbus": "#f87171", "vcc": "#f87171", "vin": "#f87171",
}
LIGHT_NETS = {
    "gnd": "#334155", "agnd": "#334155", "3v3": "#d97706",
    "5v": "#dc2626", "vbus": "#dc2626", "vcc": "#dc2626", "vin": "#dc2626",
}

# Wire "hue" palettes: one harmonious, complementary set per theme. The I2S
# lines split by role (cool clocks + a warm data accent); other buses get a
# single hue. Keys are referenced from standards.py (bus role -> hue name).
DARK_HUES = {
    "bclk": "#f472b6", "wclk": "#38bdf8", "mclk": "#a78bfa", "data": "#2dd4bf",
    "spdif": "#fb923c", "i2c": "#c084fc", "spi": "#818cf8", "uart": "#4ade80",
    "pdm": "#fb7185", "gpio": "#94a3b8", "analog": "#9ca3af",
}
CARBON_HUES = {
    "bclk": "#ff5fb0", "wclk": "#38c0ff", "mclk": "#b794ff", "data": "#2ee6c6",
    "spdif": "#ff9d4d", "i2c": "#cf8cff", "spi": "#8c9bff", "uart": "#4dee86",
    "pdm": "#ff6f8a", "gpio": "#a1a1aa", "analog": "#a8a8b0",
}
MIDNIGHT_HUES = {
    "bclk": "#ec6fa8", "wclk": "#5ab8f5", "mclk": "#9b8cf0", "data": "#34d3c0",
    "spdif": "#f0974d", "i2c": "#b88cf0", "spi": "#7d8cf0", "uart": "#5cd687",
    "pdm": "#ef7390", "gpio": "#8da0bd", "analog": "#93a3b8",
}
LIGHT_HUES = {
    "bclk": "#db2777", "wclk": "#0284c7", "mclk": "#7c3aed", "data": "#0d9488",
    "spdif": "#ea580c", "i2c": "#9333ea", "spi": "#4f46e5", "uart": "#16a34a",
    "pdm": "#e11d48", "gpio": "#64748b", "analog": "#6b7280",
}


@dataclass(frozen=True)
class Theme:
    name: str = "neutral-dark"

    # canvas
    bg: str = "#161619"
    grid_line: str = "#26262c"     # faint background grid (when enabled)
    grid_size: float = 64.0
    margin: float = 48.0
    font: str = "'Inter', 'Helvetica Neue', Arial, sans-serif"
    mono: str = "'SF Mono', 'JetBrains Mono', Menlo, monospace"

    title_color: str = "#f4f4f5"
    subtitle_color: str = "#a1a1aa"

    # bodies
    body_radius: float = 14.0
    body_stroke: str = "#3f3f46"
    body_stroke_w: float = 1.5
    body_fill: str = "#232327"
    body_title: str = "#f4f4f5"
    shadow: bool = True

    # board (PCB) style
    pcb_fill: str = "#26262b"
    pcb_stroke: str = "#3f3f46"
    pcb_title: str = "#f4f4f5"
    pcb_pad: str = "#d4d4d8"
    pcb_pad_stroke: str = "#71717a"

    # module / card style
    module_fill: str = "#232327"
    module_accent: str = "#3f3f46"
    module_pad: str = "#d4d4d8"
    module_pad_stroke: str = "#71717a"

    # chip (IC) style
    chip_fill: str = "#1c1c20"
    chip_title: str = "#e4e4e7"
    chip_pad: str = "#d4d4d8"

    # pins
    pin_label: str = "#e4e4e7"
    pin_number: str = "#c4c4cc"
    pin_pad_r: float = 4.0

    # wires (casing is the background: a clean knockout at crossings)
    wire_w: float = 3.0
    wire_casing: str = "#161619"
    wire_casing_w: float = 6.0
    wire_radius: float = 9.0
    endpoint_r: float = 4.0

    # cards
    card_fill: str = "#232327"
    card_stroke: str = "#3f3f46"
    card_title_bg: str = "#2f2f35"
    card_title_fg: str = "#f4f4f5"
    card_key: str = "#a1a1aa"
    card_value: str = "#e4e4e7"
    card_radius: float = 12.0

    # legend
    legend_fill: str = "#232327"
    legend_stroke: str = "#3f3f46"

    # wire/net palette
    nets: dict = field(default_factory=lambda: dict(DARK_NETS))
    hues: dict = field(default_factory=lambda: dict(DARK_HUES))
    signals: dict = field(default_factory=dict)   # optional bus-family overrides
    default_wire: str = "#94a3b8"


_NEUTRAL_DARK = Theme(name="neutral-dark")

_CARBON = replace(
    _NEUTRAL_DARK, name="carbon",
    bg="#0a0a0a", wire_casing="#0a0a0a", grid_line="#191919",
    body_fill="#18181b", body_stroke="#2a2a2e",
    pcb_fill="#171717", pcb_stroke="#2a2a2e", pcb_pad="#e5e5e5", pcb_pad_stroke="#525252",
    module_fill="#18181b", module_accent="#27272a", module_pad="#e5e5e5",
    chip_fill="#101012",
    card_fill="#18181b", card_stroke="#2a2a2e", card_title_bg="#27272a",
    legend_fill="#18181b", legend_stroke="#2a2a2e",
    hues=dict(CARBON_HUES),
)

_MIDNIGHT = replace(
    _NEUTRAL_DARK, name="midnight",
    bg="#0b1120", wire_casing="#0b1120", grid_line="#16203a",
    title_color="#e2e8f0", subtitle_color="#94a3b8",
    body_fill="#111a30", body_stroke="#1f2a44", body_title="#e2e8f0",
    pcb_fill="#0f1830", pcb_stroke="#1f2a44", pcb_title="#e2e8f0",
    pcb_pad="#cbd5e1", pcb_pad_stroke="#475569",
    module_fill="#111a30", module_accent="#1e293b", module_pad="#cbd5e1",
    module_pad_stroke="#475569",
    chip_fill="#0c1426", chip_title="#e2e8f0",
    pin_label="#e2e8f0", pin_number="#a3b2c8",
    card_fill="#111a30", card_stroke="#1f2a44", card_title_bg="#1e293b",
    card_title_fg="#e2e8f0", card_key="#94a3b8", card_value="#e2e8f0",
    legend_fill="#111a30", legend_stroke="#1f2a44",
    hues=dict(MIDNIGHT_HUES),
)

_LIGHT = replace(
    _NEUTRAL_DARK, name="light",
    bg="#fbfcfe", wire_casing="#fbfcfe", grid_line="#e7ecf3",
    title_color="#0f172a", subtitle_color="#64748b",
    body_fill="#ffffff", body_stroke="#cbd5e1", body_title="#0f172a",
    pcb_fill="#1f6f4a", pcb_stroke="#14532d", pcb_title="#ecfdf5",
    pcb_pad="#f4d27a", pcb_pad_stroke="#b88a2a",
    module_fill="#ffffff", module_accent="#6366f1", module_pad="#6366f1",
    module_pad_stroke="#4f46e5",
    chip_fill="#1e293b", chip_title="#e2e8f0",
    pin_label="#0f172a", pin_number="#475569",
    card_fill="#ffffff", card_stroke="#e2e8f0", card_title_bg="#6366f1",
    card_title_fg="#ffffff", card_key="#475569", card_value="#0f172a",
    legend_fill="#ffffff", legend_stroke="#e2e8f0",
    nets=dict(LIGHT_NETS), hues=dict(LIGHT_HUES), default_wire="#64748b",
)

THEMES: dict[str, Theme] = {
    t.name: t for t in (_NEUTRAL_DARK, _CARBON, _MIDNIGHT, _LIGHT)
}

DEFAULT_THEME = _NEUTRAL_DARK


def get_theme(name: str | None) -> Theme:
    if not name:
        return DEFAULT_THEME
    if name not in THEMES:
        raise KeyError(
            f"unknown theme '{name}'. Available: {', '.join(THEMES)}"
        )
    return THEMES[name]


def list_themes() -> list[str]:
    return list(THEMES)
