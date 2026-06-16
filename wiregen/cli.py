"""Command-line interface.

    wiregen render  <diagram.yaml> [-o out.svg] [--table]
    wiregen validate <diagram.yaml>
    wiregen list-parts
    wiregen describe-part <id>

The list/describe commands let an LLM ground itself in the real part library
(pin names, sides, buses) before authoring a diagram.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from .layout import build
from .library import Library
from .model import Diagram
from .render import render
from .standards import STANDARDS
from .table import as_text
from .theme import THEMES, get_theme
from .validate import validate


def _load(path: str) -> Diagram:
    data = yaml.safe_load(Path(path).read_text())
    return Diagram.model_validate(data)


def cmd_render(args) -> int:
    lib = Library.load()
    diagram = _load(args.diagram)
    issues = validate(diagram, lib)
    errors = [i for i in issues if i.severity == "error"]
    for i in issues:
        print(i, file=sys.stderr)
    if errors:
        print(f"\n{len(errors)} error(s); not rendering.", file=sys.stderr)
        return 1
    try:
        theme = get_theme(args.theme or diagram.theme)
    except KeyError as e:
        print(e, file=sys.stderr)
        return 1
    svg = render(build(diagram, lib, theme), theme)
    out = args.out or str(Path(args.diagram).with_suffix(".svg"))
    Path(out).write_text(svg)
    print(f"wrote {out}")
    if args.table:
        print("\nConnection table:")
        print(as_text(diagram, lib))
    return 0


def cmd_validate(args) -> int:
    lib = Library.load()
    diagram = _load(args.diagram)
    issues = validate(diagram, lib)
    if not issues:
        print("OK: no issues.")
        return 0
    for i in issues:
        print(i)
    return 1 if any(i.severity == "error" for i in issues) else 0


def cmd_list_parts(args) -> int:
    lib = Library.load()
    for pid in lib.ids():
        p = lib.get(pid)
        print(f"{pid:<16} {p.name}  ({p.package}, {len(p.pins)} pins)")
    return 0


def cmd_describe_part(args) -> int:
    lib = Library.load()
    p = lib.get(args.id)
    print(f"{p.id}: {p.name}  [{p.package}/{p.style or 'default'}]")
    if p.description:
        print(f"  {p.description}")
    print("  pins:")
    for pin in p.pins:
        bits = [pin.side]
        if pin.signal:
            bits.append(pin.signal)
        if pin.role:
            bits.append(f"role={pin.role}")
        if pin.net:
            bits.append(f"net={pin.net}")
        num = f"#{pin.number} " if pin.number else ""
        print(f"    {num}{pin.text:<12} ({', '.join(bits)})")
    return 0


def cmd_list_themes(args) -> int:
    for name, t in THEMES.items():
        print(f"{name:<14} bg {t.bg}")
    return 0


def cmd_list_buses(args) -> int:
    for name, bus in STANDARDS.items():
        roles = ", ".join(sorted(bus.roles)) or "-"
        print(f"{name:<8} {bus.label:<8} {bus.color}  roles: {roles}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="wiregen",
                                 description="Beautiful wiring diagrams from a "
                                             "declarative description.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("render", help="render a diagram to SVG")
    r.add_argument("diagram")
    r.add_argument("-o", "--out")
    r.add_argument("--theme", help=f"colour scheme ({', '.join(THEMES)})")
    r.add_argument("--table", action="store_true",
                   help="also print the connection table")
    r.set_defaults(func=cmd_render)

    v = sub.add_parser("validate", help="check a diagram for wiring issues")
    v.add_argument("diagram")
    v.set_defaults(func=cmd_validate)

    lp = sub.add_parser("list-parts", help="list available parts")
    lp.set_defaults(func=cmd_list_parts)

    dp = sub.add_parser("describe-part", help="show a part's pins")
    dp.add_argument("id")
    dp.set_defaults(func=cmd_describe_part)

    lt = sub.add_parser("list-themes", help="list available colour schemes")
    lt.set_defaults(func=cmd_list_themes)

    lb = sub.add_parser("list-buses", help="list known signal standards")
    lb.set_defaults(func=cmd_list_buses)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
