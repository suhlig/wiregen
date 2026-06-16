"""Wiring-sanity checks (advisory). These help a builder/LLM catch mistakes;
they are deliberately NOT electrical design rules. Errors block rendering;
warnings do not."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .connections import Endpoint, expand
from .library import Library
from .model import Diagram
from .standards import get_bus


@dataclass
class Issue:
    severity: Literal["error", "warning"]
    message: str

    def __str__(self) -> str:
        mark = "ERROR" if self.severity == "error" else "warn "
        return f"[{mark}] {self.message}"


def validate(diagram: Diagram, lib: Library) -> list[Issue]:
    issues: list[Issue] = []

    # parts resolve
    for inst_id, inst in diagram.parts.items():
        try:
            lib.get(inst.part)
        except KeyError as e:
            issues.append(Issue("error", f"part '{inst_id}': {e}"))

    def check_endpoint(ep: Endpoint, where: str) -> None:
        if ep.instance not in diagram.parts:
            issues.append(Issue("error",
                f"{where}: no placed part '{ep.instance}'"))
            return
        try:
            part = lib.get(diagram.parts[ep.instance].part)
        except KeyError:
            return  # already reported
        cands = Library.candidates(part, ep.token)
        if not cands:
            sug = Library.suggest(part, ep.token)
            hint = f" Did you mean: {', '.join(sug)}?" if sug else ""
            issues.append(Issue("error",
                f"{where}: pin '{ep.token}' not found on "
                f"'{part.name}'.{hint}"))

    # connections expand + resolve
    try:
        wires = expand(diagram)
    except ValueError as e:
        issues.append(Issue("error", f"connection: {e}"))
        wires = []

    connected: set[str] = set()
    for w in wires:
        check_endpoint(w.a, "connection.from")
        check_endpoint(w.b, "connection.to")
        if w.bus and not get_bus(w.bus):
            issues.append(Issue("error", f"unknown bus '{w.bus}'"))
        connected.add(w.a.instance)
        connected.add(w.b.instance)

    # advisory: a placed part with no wires at all is probably a mistake
    for inst_id in diagram.parts:
        if inst_id not in connected:
            issues.append(Issue("warning",
                f"part '{inst_id}' has no connections"))

    # advisory: anchors point at real instances
    for ann in diagram.annotations:
        if ann.anchor and ann.anchor not in diagram.parts:
            issues.append(Issue("warning",
                f"annotation '{ann.card}': anchor '{ann.anchor}' "
                f"is not a placed part"))

    return issues
