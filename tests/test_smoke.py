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


def test_unknown_pin_is_error():
    lib = Library.load()
    d = Diagram.model_validate({
        "parts": {"pico": {"part": "pico2", "region": "left"},
                  "adc": {"part": "pcm1808", "region": "right"}},
        "connections": [{"from": "pico.GP999", "to": "adc.BCK"}],
    })
    issues = validate(d, lib)
    assert any(i.severity == "error" and "GP999" in i.message for i in issues)
