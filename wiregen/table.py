"""Connection table: a plain from -> to checklist a builder can tick off while
wiring. Generated from the same model as the diagram, so it never drifts."""

from __future__ import annotations

from .connections import expand
from .library import Library
from .model import Diagram
from .standards import get_bus


def _label(diagram: Diagram, lib: Library, instance: str) -> str:
    inst = diagram.parts[instance]
    try:
        return inst.label or lib.get(inst.part).name
    except KeyError:
        return instance


def build_rows(diagram: Diagram, lib: Library) -> list[tuple[str, str, str, str, str]]:
    rows = []
    for w in expand(diagram):
        bus = get_bus(w.bus or w.signal)
        sig = bus.label if bus else (w.signal or "")
        rows.append((
            _label(diagram, lib, w.a.instance), w.a.token,
            _label(diagram, lib, w.b.instance), w.b.token,
            sig,
        ))
    return rows


def as_text(diagram: Diagram, lib: Library) -> str:
    rows = build_rows(diagram, lib)
    if not rows:
        return "(no connections)"
    left = [f"{a} {ap}" for a, ap, _, _, _ in rows]
    right = [f"{b} {bp}" for _, _, b, bp, _ in rows]
    sig = [s for *_, s in rows]
    lw = max(len(x) for x in left)
    rw = max(len(x) for x in right)
    out = []
    for l, r, s in zip(left, right, sig):
        tail = f"   [{s}]" if s else ""
        out.append(f"  {l:<{lw}}  ->  {r:<{rw}}{tail}")
    return "\n".join(out)


def as_markdown(diagram: Diagram, lib: Library) -> str:
    rows = build_rows(diagram, lib)
    out = ["| From | Pin | To | Pin | Signal |", "|---|---|---|---|---|"]
    for a, ap, b, bp, s in rows:
        out.append(f"| {a} | {ap} | {b} | {bp} | {s} |")
    return "\n".join(out)
