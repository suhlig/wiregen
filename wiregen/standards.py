"""Signal-standard registry.

Teaches the tool what common buses are (their roles + a colour) so it can
colour-code wires, expand bus shorthands, label connections, and emit a
legend. The point here is *legibility*, not electrical design rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .theme import Theme


@dataclass(frozen=True)
class Bus:
    name: str
    label: str
    color: str
    # role -> hue name (resolved against theme.hues); lets one bus colour its
    # lines individually (e.g. I2S BCK/LRCLK/MCLK/Data)
    roles: dict[str, str] = field(default_factory=dict)


# Buses keyed by lowercase family name. The bus `color` is a fallback; actual
# wire colour comes from the theme palette (per role, then per bus).
STANDARDS: dict[str, Bus] = {
    "i2s": Bus("i2s", "I2S", "#14b8a6", {
        "bck": "bclk", "lrck": "wclk", "lrc": "wclk", "ws": "wclk",
        "mck": "mclk", "sck": "mclk",
        "sd": "data", "din": "data", "dout": "data", "out": "data", "data": "data",
    }),
    "spdif": Bus("spdif", "S/PDIF", "#f97316"),
    "i2c": Bus("i2c", "I2C", "#a855f7"),
    "spi": Bus("spi", "SPI", "#3b82f6"),
    "uart": Bus("uart", "UART", "#22c55e"),
    "pdm": Bus("pdm", "PDM", "#ec4899"),
    "gpio": Bus("gpio", "GPIO", "#64748b"),
    "analog": Bus("analog", "Analog", "#9ca3af"),
    "power": Bus("power", "Power", "#ef4444"),
}

# hue name -> short legend label (for the per-role I2S lines)
HUE_LABEL = {"bclk": "BCK", "wclk": "LRCLK", "mclk": "MCLK", "data": "Data"}


def wire_hue(signal: str | None, role: str | None) -> str | None:
    """Resolve the theme-palette hue *name* for a wire, or None."""
    bus = get_bus(signal)
    if not bus:
        return None
    if role:
        hue = bus.roles.get(role.lower())
        if hue:
            return hue
    return bus.name

def get_bus(name: str | None) -> Bus | None:
    if not name:
        return None
    return STANDARDS.get(name.lower())


def wire_color(signal: str | None, role: str | None, net: str | None,
               explicit: str | None, theme: "Theme") -> str:
    """Resolve a wire colour against a theme palette.

    Priority: explicit override > electrical net (theme.nets) > per-role hue
    (theme.hues, e.g. I2S BCK vs LRCLK) > per-bus hue > theme override/default.
    Net colours win because on a real build the power/ground insulation colour
    is what a builder reaches for.
    """
    if explicit:
        return explicit
    if net and net.lower() in theme.nets:
        return theme.nets[net.lower()]
    hue = wire_hue(signal, role)
    if hue and hue in theme.hues:
        return theme.hues[hue]
    bus = get_bus(signal)
    if bus:
        if bus.name in theme.signals:
            return theme.signals[bus.name]
        return bus.color
    return theme.default_wire


def expand_bus(bus_name: str) -> Bus | None:
    """Return the bus definition for a shorthand, or None if unknown."""
    return get_bus(bus_name)
