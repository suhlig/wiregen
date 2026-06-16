"""Part library: loads ``wiregen/parts/*.yaml`` and resolves pin references.

Pin resolution is intentionally forgiving (good for LLMs): exact name first,
then display label, then electrical net tag, then a fuzzy suggestion list so a
caller can self-correct. Multiple physical pins may share a name (e.g. several
GND pads); resolution returns *all* candidates and the layout picks the nearest
one to the other end of the wire.
"""

from __future__ import annotations

import difflib
from pathlib import Path

import yaml

from .model import PartDef, PinDef

PARTS_DIR = Path(__file__).parent / "parts"


class Library:
    def __init__(self, parts: dict[str, PartDef]):
        self._parts = parts

    @classmethod
    def load(cls, extra_dirs: list[Path] | None = None) -> "Library":
        parts: dict[str, PartDef] = {}
        dirs = [PARTS_DIR] + list(extra_dirs or [])
        for d in dirs:
            if not d.exists():
                continue
            for f in sorted(d.glob("*.yaml")):
                data = yaml.safe_load(f.read_text())
                part = PartDef.model_validate(data)
                if part.id in parts:
                    raise ValueError(f"duplicate part id '{part.id}' in {f}")
                parts[part.id] = part
        return cls(parts)

    def ids(self) -> list[str]:
        return sorted(self._parts)

    def get(self, part_id: str) -> PartDef:
        if part_id not in self._parts:
            close = difflib.get_close_matches(part_id, self._parts, n=3)
            hint = f" Did you mean: {', '.join(close)}?" if close else ""
            raise KeyError(f"unknown part '{part_id}'.{hint}")
        return self._parts[part_id]

    # --- pin resolution ----------------------------------------------------

    @staticmethod
    def candidates(part: PartDef, token: str) -> list[PinDef]:
        """All pins on ``part`` matching ``token`` by name, label, then net."""
        t = token.strip().lower()
        by_name = [p for p in part.pins if p.name.lower() == t]
        if by_name:
            return by_name
        by_label = [p for p in part.pins if p.text.lower() == t]
        if by_label:
            return by_label
        by_net = [p for p in part.pins if p.net and p.net.lower() == t]
        return by_net

    @staticmethod
    def suggest(part: PartDef, token: str, n: int = 4) -> list[str]:
        names = [p.name for p in part.pins]
        return difflib.get_close_matches(token, names, n=n, cutoff=0.3)
