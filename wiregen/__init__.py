"""wiregen: declarative generator for beautiful, modern wiring diagrams."""

from __future__ import annotations

from pathlib import Path

import yaml

from .layout import build
from .library import Library
from .model import Diagram
from .render import render
from .theme import Theme, get_theme
from .validate import validate

__all__ = ["Diagram", "Library", "Theme", "get_theme", "load_diagram",
           "render_diagram", "validate", "build", "render"]

__version__ = "0.1.0"


def load_diagram(path: str | Path) -> Diagram:
    data = yaml.safe_load(Path(path).read_text())
    return Diagram.model_validate(data)


def render_diagram(diagram: Diagram, lib: Library | None = None,
                   theme: str | Theme | None = None) -> str:
    lib = lib or Library.load()
    th = theme if isinstance(theme, Theme) else get_theme(theme or diagram.theme)
    geo = build(diagram, lib, th)
    return render(geo, th)
