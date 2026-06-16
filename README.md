# wiregen

Declarative generator for beautiful, modern wiring diagrams.

You describe **parts** (from a library of ICs and boards) and **pin-to-pin
wiring**; wiregen owns every coordinate and produces a clean SVG. No SVG
bookkeeping, no guesswork. It understands signal standards (I2S, SPDIF, I2C,
SPI, ...) so wires are colour-coded and a single bus line expands into several.

The goal is to show **how things connect** (like a breadboard wiring guide),
not to design or validate circuits.

## Install

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

## Use

```bash
wiregen render examples/pcm1808_to_dspi.yaml -o out.svg --table
wiregen render examples/pcm1808_to_dspi.yaml --theme light
wiregen validate examples/pcm1808_to_dspi.yaml
wiregen list-parts
wiregen describe-part pico2     # pin names, sides, buses
wiregen list-themes            # neutral-dark (default), carbon, midnight, light
wiregen list-buses
```

## Colour schemes

Selectable per diagram. `--theme <name>` overrides the diagram's `theme:`
field, which overrides the default (`neutral-dark`). Built in:
`neutral-dark`, `carbon` (pure black), `midnight` (blue-grey), `light`.
Each theme defines its own wire/net palette, so ground and power colours adapt
to the background (light on dark schemes, dark on light). Add a scheme by
appending a `Theme` to `THEMES` in `wiregen/theme.py`.

## Authoring a diagram

A diagram is one YAML (or JSON) document:

```yaml
title: PCM1808 ADC to DSPi (I2S input)
parts:
  adc:  { part: pcm1808, region: left }
  pico: { part: pico2,   region: right }
connections:
  - bus: i2s            # expands via the signal registry, auto-coloured
    from: pico
    to: adc
    map: { GP14: BCK, GP15: LRC, GP13: SCK, GP4: OUT }
  - { from: pico.3V3, to: adc.VCC }
  - { from: pico.GND, to: adc.GND }
annotations:
  - card: DSPi I2S input
    rows: { Input source: I2S, Sample rate: 48 kHz }
```

You only ever give **coarse intent**: `region` (left/center/right), `order`
within a region, and optional `flip` to face a board's header toward the wiring
channel. wiregen computes all exact positions, pin spacing, routing, and bounds.

Multiple pins may share a name (e.g. several `GND` pads); a reference like
`pico.GND` resolves to the pad physically nearest the other end of the wire.

## For LLMs

1. `wiregen list-parts` / `wiregen describe-part <id>` to ground yourself in the
   real pin names, sides, and buses before writing anything.
2. Author the YAML.
3. `wiregen validate <file>` returns structured `[ERROR]/[warn]` lines with
   "did you mean" suggestions for self-correction. Errors block rendering;
   warnings (e.g. an unconnected part) do not.

## Adding a part

Drop a YAML file in `wiregen/parts/`. A part is metadata plus an ordered pin
list; each pin declares its physical `side` and (optionally) `signal`, `role`,
`net`, `number`. No code change required. See `wiregen/parts/pico2.yaml`.

## Architecture

Layered, each stage independent:

| Module | Responsibility |
|---|---|
| `model.py` | Pydantic schema for parts and diagrams |
| `parts/*.yaml` | data-driven part library |
| `standards.py` | signal registry (buses, roles, colours) |
| `library.py` | part loading + forgiving pin resolution |
| `connections.py` | expand explicit + bus connections to a flat wire list |
| `validate.py` | advisory wiring-sanity checks |
| `layout.py` | hint-driven placement + routing -> geometry |
| `render.py` | geometry -> SVG |
| `theme.py` | visual tokens (one place to retune the look) |
| `table.py` | from->to connection checklist |
| `cli.py` | render / validate / list-parts / describe-part |

## Roadmap

- **M1 (done):** model, signal registry, Pico 2 + PCM1808, abstract+PCB
  renderer, hint layout, jumper routing, connection table, validation, CLI,
  selectable colour schemes (neutral-dark / carbon / midnight / light).
- **M2:** PNG/PDF export, external YAML theme files, richer cards, more parts
  (ESP32).
- **M3:** crossing-minimising orthogonal router + bus bundling.
- **M4:** optional realistic board art for marquee boards (per-part SVG +
  pin-anchor map; falls back to abstract when absent).
- **M5:** web UI over the same model.
