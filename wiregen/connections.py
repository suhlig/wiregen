"""Connection expansion shared by validation, layout, and the table writer.

Turns the diagram's ``connections`` list (explicit wires and bus shorthands)
into a flat list of ``WireSpec`` entries, each a resolved pair of endpoints
plus a colour/label. This is the single source of truth for "what wires exist".
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import Connection, Diagram
from .standards import expand_bus


@dataclass
class Endpoint:
    instance: str   # diagram instance id
    token: str      # pin reference token (resolved against the part later)


@dataclass
class WireSpec:
    a: Endpoint
    b: Endpoint
    signal: str | None
    color: str | None      # explicit override; None means "derive from pins"
    label: str | None
    bus: str | None        # bus family this wire belongs to, if any
    route: str | None = None  # "top"/"bottom" detour preference for wraps


def _split(token: str) -> tuple[str, str]:
    if "." not in token:
        raise ValueError(
            f"endpoint '{token}' must be 'instance.pin' (e.g. 'pico.GP14')"
        )
    inst, pin = token.split(".", 1)
    return inst.strip(), pin.strip()


def expand(diagram: Diagram) -> list[WireSpec]:
    wires: list[WireSpec] = []
    for c in diagram.connections:
        if c.bus is not None:
            wires.extend(_expand_bus(c))
        else:
            wires.append(_expand_explicit(c))
    return wires


def _expand_explicit(c: Connection) -> WireSpec:
    if not c.from_ or not c.to:
        raise ValueError("explicit connection needs both 'from' and 'to'")
    ai, ap = _split(c.from_)
    bi, bp = _split(c.to)
    return WireSpec(
        a=Endpoint(ai, ap),
        b=Endpoint(bi, bp),
        signal=c.signal,
        color=c.color,
        label=c.label,
        bus=None,
        route=c.route,
    )


def _expand_bus(c: Connection) -> list[WireSpec]:
    bus = expand_bus(c.bus or "")
    if bus is None:
        raise ValueError(f"unknown bus '{c.bus}'")
    if not c.from_ or not c.to or not c.map:
        raise ValueError(
            f"bus '{c.bus}' needs 'from', 'to' (instance ids) and a 'map'"
        )
    out: list[WireSpec] = []
    for host_pin, dev_pin in c.map.items():
        out.append(
            WireSpec(
                a=Endpoint(c.from_.strip(), host_pin.strip()),
                b=Endpoint(c.to.strip(), dev_pin.strip()),
                signal=c.signal or bus.name,
                color=c.color,   # None -> resolved per role/theme downstream
                label=c.label,
                bus=bus.name,
                route=c.route,
            )
        )
    return out
