from pathlib import Path

import yaml

from wiregen.layout import build
from wiregen.library import Library
from wiregen.model import Diagram
from wiregen.render import render
from wiregen.table import build_rows
from wiregen.theme import THEMES, get_theme
from wiregen.validate import validate

EXAMPLE = Path(__file__).parent.parent / "examples" / "pcm1808_to_dspi.yaml"


def _load():
    lib = Library.load()
    diagram = Diagram.model_validate(yaml.safe_load(EXAMPLE.read_text()))
    return diagram, lib


def test_library_loads():
    lib = Library.load()
    assert "pico2" in lib.ids()
    assert "pcm1808" in lib.ids()          # bare IC
    assert "pcm1808_board" in lib.ids()    # purple breakout


def test_board_has_purple_substrate():
    lib = Library.load()
    board = lib.get("pcm1808_board")
    assert board.color and board.color.startswith("#")
    assert len(board.decorations) > 0


def test_example_validates_clean():
    diagram, lib = _load()
    issues = validate(diagram, lib)
    assert [i for i in issues if i.severity == "error"] == []


def test_example_renders_svg():
    diagram, lib = _load()
    svg = render(build(diagram, lib))
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")
    assert "PCM1808" in svg


def test_bus_expands_to_four_wires():
    diagram, lib = _load()
    geo = build(diagram, lib)
    # 4 i2s + 5v + 3v3 + gnd + 3 strapping jumpers = 10 wires
    assert len(geo.wires) == 10


def test_connection_table_has_rows():
    diagram, lib = _load()
    rows = build_rows(diagram, lib)
    pairs = {(a_pin, b_pin) for _, a_pin, _, b_pin, _ in rows}
    assert ("GP14", "BCK") in pairs
    assert ("GP4", "OUT") in pairs


def test_themes_render_and_adapt():
    diagram, lib = _load()
    for name, theme in THEMES.items():
        svg = render(build(diagram, lib, theme), theme)
        assert f'fill="{theme.bg}"' in svg
    # default (dark) has a light ground wire; light theme a dark one
    assert get_theme("neutral-dark").nets["gnd"] != get_theme("light").nets["gnd"]


def test_unknown_theme_raises():
    try:
        get_theme("does-not-exist")
    except KeyError as e:
        assert "does-not-exist" in str(e)
    else:
        raise AssertionError("expected KeyError")


def test_inmp441_is_a_round_two_row_board():
    lib = Library.load()
    mic = lib.get("inmp441")
    assert mic.shape == "round"
    sides = [p.side for p in mic.pins]
    assert sides.count("top") == 3        # SCK, WS, L/R
    assert sides.count("bottom") == 3     # SD, VDD, GND


def test_round_board_renders_as_a_circle():
    lib = Library.load()
    d = Diagram.model_validate({"parts": {"mic": {"part": "inmp441"}}})
    svg = render(build(d, lib))
    assert 'r="66.0"' in svg               # body = inscribed circle of 132px
    assert any(d.type == "notch" for d in lib.get("inmp441").decorations)


def test_unknown_pin_is_error():
    lib = Library.load()
    d = Diagram.model_validate({
        "parts": {"pico": {"part": "pico2", "region": "left"},
                  "adc": {"part": "pcm1808", "region": "right"}},
        "connections": [{"from": "pico.GP999", "to": "adc.BCK"}],
    })
    issues = validate(d, lib)
    assert any(i.severity == "error" and "GP999" in i.message for i in issues)


# the INMP441 diagram: a round mic (pins on top and bottom) beside a Pi 3
MIC_PI = {
    "parts": {"mic": {"part": "inmp441", "region": "left"},
              "pi": {"part": "raspberry-pi-3", "region": "right"}},
    "connections": [
        {"from": "pi.GPIO18", "to": "mic.SCK"},
        {"from": "pi.GPIO19", "to": "mic.WS"},
        {"from": "pi.GPIO20", "to": "mic.SD"},
        {"from": "pi.3V3", "to": "mic.VDD", "route": "bottom"},
        {"from": "pi.GND", "to": "mic.GND"},
        {"from": "pi.GND", "to": "mic.L/R"},
    ],
}


def _segments(geo):
    return [(a, b) for w in geo.wires for a, b in zip(w.points, w.points[1:])]


def _collinear_overlap(a, b, eps=0.6):
    (ax0, ay0), (ax1, ay1) = a
    (bx0, by0), (bx1, by1) = b
    a_h = abs(ay0 - ay1) < 0.01
    if a_h != (abs(by0 - by1) < 0.01):
        return False
    if a_h:
        if abs(ay0 - by0) > eps:
            return False
        lo = max(min(ax0, ax1), min(bx0, bx1))
        hi = min(max(ax0, ax1), max(bx0, bx1))
    else:
        if abs(ax0 - bx0) > eps:
            return False
        lo = max(min(ay0, ay1), min(by0, by1))
        hi = min(max(ay0, ay1), max(by0, by1))
    return hi - lo > eps


def test_no_two_wire_segments_overlap():
    segs = _segments(build(Diagram.model_validate(MIC_PI), Library.load()))
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            assert not _collinear_overlap(segs[i], segs[j]), (segs[i], segs[j])


def test_wires_leave_each_pin_on_its_own_side():
    geo = build(Diagram.model_validate(MIC_PI), Library.load())
    at = {(round(pin.x, 1), round(pin.y, 1)): pin
          for part in geo.parts for pin in part.pins}
    outward = {"top": (0, -1), "bottom": (0, 1),
               "left": (-1, 0), "right": (1, 0)}
    for w in geo.wires:
        if len(w.points) < 2:
            continue
        for end, nbr in ((0, 1), (-1, -2)):
            pt = w.points[end]
            pin = at.get((round(pt[0], 1), round(pt[1], 1)))
            if pin is None:
                continue
            ox, oy = outward[pin.side]
            dx = w.points[nbr][0] - pt[0]
            dy = w.points[nbr][1] - pt[1]
            assert dx * ox + dy * oy > 0, (pin.name, pin.side, (dx, dy))
