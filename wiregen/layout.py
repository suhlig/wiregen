"""Hint-driven layout. The author supplies coarse intent (region, order, flip);
this module owns every coordinate: part sizes, pin positions, channel routing,
card placement, and the final canvas bounds. No pixel bookkeeping upstream.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .connections import expand
from .library import Library
from .model import Diagram, PartDef, PartInstance
from .standards import HUE_LABEL, get_bus, wire_color, wire_hue
from .theme import DEFAULT_THEME, Theme

# tunables (px)
PIN_PITCH = 24.0
PAD_TOP = 34.0
PAD_BOTTOM = 16.0
MIN_BODY_H = 70.0
DEFAULT_W = 150.0
CHANNEL = 240.0
VGAP = 64.0
STUB = 18.0
TRACK_GAP = 19.0        # minimum elbow spacing
TRACK_GAP_MAX = 36.0    # cap on elbow spacing when spreading
LANE_GAP = 18.0
WRAP_GAP = 12.0
WRAP_CLEAR = 30.0       # wrap clearance for parts with pin numbers
WRAP_CLEAR_MIN = 13.0   # wrap clearance for parts with nothing protruding
TRACK_MARGIN = 30.0     # keep elbow tracks this far inside the channel edges
TOP = 48.0 + 54.0 + 30.0   # margin + title band + lane band
LEFT = 48.0
CARD_W = 236.0
CARD_GAP = 24.0
ROW_H = 24.0
CARD_PAD = 14.0         # inner horizontal padding for card content
TEXT_LH = 15.0          # line height for wrapped free-text notes
FIRST_ROW = 48.0        # first content baseline below the card top (30 band + 18)
_TEXT_CHAR_W = 5.05     # ~avg glyph width at the 10.5px note font, for wrapping


def wrap_card_text(text: str) -> list[str]:
    """Greedy word-wrap a free-text note to the card's inner width. Newlines in
    the source separate paragraphs, rendered with a blank line between them."""
    max_chars = max(1, int((CARD_W - 2 * CARD_PAD) / _TEXT_CHAR_W))
    lines: list[str] = []
    paragraphs = [p for p in text.split("\n") if p.strip()]
    for pi, para in enumerate(paragraphs):
        if pi > 0:
            lines.append("")        # blank line between paragraphs
        cur = ""
        for word in para.split():
            cand = f"{cur} {word}".strip()
            if not cur or len(cand) <= max_chars:
                cur = cand
            else:
                lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
    return lines


@dataclass
class Box:
    x: float
    y: float
    w: float
    h: float

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
        return self.y + self.h

    @property
    def cx(self) -> float:
        return self.x + self.w / 2


@dataclass
class PlacedPin:
    name: str
    text: str
    number: str | None
    net: str | None
    signal: str | None
    role: str | None
    x: float
    y: float
    side: str  # effective side after flip


@dataclass
class PlacedPart:
    iid: str
    part: PartDef
    label: str
    box: Box
    pins: list[PlacedPin]
    style: str
    package: str
    color: str | None = None
    connector: str | None = None


@dataclass
class RoutedWire:
    points: list[tuple[float, float]]
    color: str
    label: str | None


@dataclass
class PlacedCard:
    box: Box
    title: str
    rows: dict[str, str]
    text: str | None


@dataclass
class Geometry:
    parts: list[PlacedPart]
    wires: list[RoutedWire]
    cards: list[PlacedCard]
    legend: list[tuple[str, str]]
    width: float
    height: float
    title: str | None
    subtitle: str | None


def _eff_side(side: str, flip: bool) -> str:
    if not flip:
        return side
    return {"left": "right", "right": "left"}.get(side, side)


def _placed_candidates(part: PlacedPart, token: str) -> list[PlacedPin]:
    t = token.strip().lower()
    for key in ("name", "text", "net"):
        hits = [p for p in part.pins
                if (getattr(p, key) or "").lower() == t]
        if hits:
            return hits
    return []


def _body_size(part: PartDef, inst: PartInstance) -> tuple[float, float]:
    left_n = sum(1 for p in part.pins if _eff_side(p.side, inst.flip) == "left")
    right_n = sum(1 for p in part.pins if _eff_side(p.side, inst.flip) == "right")
    rows = max(left_n, right_n, 1)
    computed_h = max(MIN_BODY_H, rows * PIN_PITCH + PAD_TOP + PAD_BOTTOM)
    # honour an explicit height override, but never shrink below what the pins
    # need (would crowd them)
    h = max(computed_h, float(part.height)) if part.height else computed_h
    w = inst.width if getattr(inst, "width", None) else (part.width or DEFAULT_W)
    return float(w), float(h)


def _place_pins(part: PartDef, inst: PartInstance, box: Box) -> list[PlacedPin]:
    sides: dict[str, list] = {"left": [], "right": [], "top": [], "bottom": []}
    for p in part.pins:
        sides[_eff_side(p.side, inst.flip)].append(p)
    placed: list[PlacedPin] = []
    # all pins use the same fixed pitch (matching every board); a taller body
    # just gains margin. Side pins centre vertically in the padded region;
    # top/bottom pins centre on the body width.
    pitch = PIN_PITCH
    for side, pins in sides.items():
        n = len(pins)
        if n == 0:
            continue
        if side in ("left", "right"):
            x = box.x if side == "left" else box.right
            center = box.y + box.h / 2   # true body centre, not the padded region
            for i, p in enumerate(pins):
                y = center + (i - (n - 1) / 2) * pitch
                placed.append(PlacedPin(p.name, p.text, p.number, p.net,
                                        p.signal, p.role, x, y, side))
        else:
            y = box.y if side == "top" else box.bottom
            start = box.cx - (n - 1) / 2 * pitch
            for i, p in enumerate(pins):
                x = start + i * pitch
                placed.append(PlacedPin(p.name, p.text, p.number, p.net,
                                        p.signal, p.role, x, y, side))
    return placed


def build(diagram: Diagram, lib: Library, theme: Theme = DEFAULT_THEME) -> Geometry:
    # 1. size every instance
    sized: dict[str, tuple[PartDef, PartInstance, float, float]] = {}
    for iid, inst in diagram.parts.items():
        pdef = lib.get(inst.part)
        w, h = _body_size(pdef, inst)
        sized[iid] = (pdef, inst, w, h)

    # 2. group into region columns, ordered within each
    regions: dict[str, list[str]] = {"left": [], "center": [], "right": []}
    for iid, inst in diagram.parts.items():
        regions[inst.region].append(iid)
    for r in regions:
        regions[r].sort(key=lambda iid: (
            diagram.parts[iid].order if diagram.parts[iid].order is not None
            else list(diagram.parts).index(iid)))

    present = [r for r in ("left", "center", "right") if regions[r]]
    colw = {r: max(sized[i][2] for i in regions[r]) for r in present}
    colx: dict[str, float] = {}
    cursor = LEFT
    for r in present:
        colx[r] = cursor
        cursor += colw[r] + CHANNEL

    # vertical: centre each column around a common mid
    colh = {r: sum(sized[i][3] for i in regions[r])
            + VGAP * (len(regions[r]) - 1) for r in present}
    max_h = max(colh.values()) if colh else 0.0
    mid = TOP + max_h / 2

    placed: dict[str, PlacedPart] = {}
    for r in present:
        y = mid - colh[r] / 2
        for iid in regions[r]:
            pdef, inst, w, h = sized[iid]
            x = colx[r] + (colw[r] - w) / 2
            box = Box(x + inst.offset_x, y + inst.offset_y, w, h)
            pins = _place_pins(pdef, inst, box)
            placed[iid] = PlacedPart(iid, pdef, inst.label or pdef.name,
                                     box, pins, pdef.style or "card",
                                     pdef.package, pdef.color, pdef.connector)
            y += h + VGAP

    parts_top = min((p.box.y for p in placed.values()), default=TOP)
    parts_bottom = max((p.box.bottom for p in placed.values()), default=TOP)
    # wrap clearance per part: hug the edge unless pin numbers protrude
    part_clear = {id(p.box): (WRAP_CLEAR if any(pin.number for pin in p.pins)
                              else WRAP_CLEAR_MIN) for p in placed.values()}

    # 3. resolve + route wires
    wires: list[RoutedWire] = []
    legend: dict[str, str] = {}
    specs = expand(diagram)

    # pre-resolve endpoints to placed pins (with proximity for duplicates)
    resolved: list[tuple[PlacedPin, PlacedPin, str, str | None, str | None]] = []
    for w in specs:
        pa = placed.get(w.a.instance)
        pb = placed.get(w.b.instance)
        if not pa or not pb:
            continue
        ca = _placed_candidates(pa, w.a.token)
        cb = _placed_candidates(pb, w.b.token)
        if not ca or not cb:
            continue
        pin_a, pin_b = _nearest_pair(ca, cb)
        net = pin_a.net or pin_b.net
        sig = w.signal or pin_a.signal or pin_b.signal
        role = pin_a.role or pin_b.role
        color = wire_color(sig, role, net, w.color, theme)
        resolved.append((pin_a, pin_b, color, w.label, w.route))
        # legend entry: nets first, then per-role / per-bus signal lines
        bus = get_bus(w.bus or sig)
        if net and net.lower() in ("gnd", "agnd"):
            legend.setdefault("GND", color)
        elif net and net.lower() in ("3v3",):
            legend.setdefault("3V3", color)
        elif net and net.lower() in ("5v", "vbus", "vcc", "vin"):
            legend.setdefault("5V / VIN", color)
        elif bus:
            hue = wire_hue(sig, role)
            sub = HUE_LABEL.get(hue or "")
            legend.setdefault(f"{bus.label} {sub}" if sub else bus.label, color)

    # classify every wire: jumper (same edge), wrap (a detour), or channel
    items = []
    for pa_pin, pb_pin, color, label, route in resolved:
        box_a = _owner_box(placed, pa_pin)
        box_b = _owner_box(placed, pb_pin)
        if box_a is box_b and pa_pin.side == pb_pin.side:
            kind = "jumper"
        elif (route is not None
              or _faces_away(pa_pin, box_a, box_b)
              or _faces_away(pb_pin, box_b, box_a)):
            kind = "wrap"
        else:
            kind = "channel"
        items.append([pa_pin, pb_pin, color, label, route, box_a, box_b, kind])

    # channel wires get elbow tracks. Straight wires (no vertical run) need
    # none. The rest are packed: wires whose vertical spans don't overlap can
    # share one elbow column, so e.g. an up-going wire aligns with a disjoint
    # down-going one instead of claiming its own track.
    chan = [it for it in items if it[7] == "channel"]
    straight_eps = 1.5

    def _cc(it):
        a, b = it[5], it[6]
        lo, hi = (a, b) if a.cx <= b.cx else (b, a)
        return (lo.right + hi.x) / 2

    elbow = [it for it in chan if abs(it[0].y - it[1].y) > straight_eps]
    # nested-fan order: wires to lower endpoints take outer (earlier) tracks
    elbow.sort(key=lambda it: -max(it[0].y, it[1].y))
    tracks = []                      # each track holds the (y0, y1) spans on it
    track_of = {}
    for it in elbow:
        y0, y1 = sorted((it[0].y, it[1].y))
        chosen = None
        for t in range(len(tracks) - 1, -1, -1):   # prefer the rightmost free track
            if all(y1 < s0 or y0 > s1 for s0, s1 in tracks[t]):
                chosen = t
                break
        if chosen is None:
            chosen = len(tracks)
            tracks.append([])
        tracks[chosen].append((y0, y1))
        track_of[id(it)] = chosen
    # space the tracks out for readability: widen toward TRACK_GAP_MAX as the
    # channel allows, then centre the band (wires sharing a track move together)
    n_tracks = len(tracks)
    for it in elbow:
        a, b = it[5], it[6]
        lo, hi = (a, b) if a.cx <= b.cx else (b, a)
        cc = (lo.right + hi.x) / 2
        if n_tracks <= 1:
            x = cc
        else:
            avail = (hi.x - TRACK_MARGIN) - (lo.right + TRACK_MARGIN)
            gap = min(TRACK_GAP_MAX, max(TRACK_GAP, avail / (n_tracks - 1)))
            x = cc + (track_of[id(it)] - (n_tracks - 1) / 2) * gap
        it.append(x)
    for it in chan:
        if len(it) == 8:            # straight wire: centre track -> flat run
            it.append(_cc(it))

    lane_top = 0
    lane_bottom = 0
    for it in items:
        pa_pin, pb_pin, color, label, route, box_a, box_b, kind = it[:8]
        if kind == "jumper":
            dist = abs(pa_pin.y - pb_pin.y) + abs(pa_pin.x - pb_pin.x)
            pts = _side_jumper(pa_pin, pb_pin, box_a, 12 + dist * 0.16)
            wires.append(RoutedWire(_clean(pts), color, label))
            continue
        if kind == "channel":
            track_x = it[8]
            appr_a = _approach(pa_pin, box_a, box_b, track_x, 0)
            appr_b = _approach(pb_pin, box_b, box_a, track_x, 0)
            wires.append(RoutedWire(_clean(appr_a + list(reversed(appr_b))),
                                    color, label))
            continue
        # wrap around the top (default) or bottom; each wrap gets its own lane
        # and its own outward offset so verticals never coincide
        if route == "bottom":
            lane_y = parts_bottom + 16 + lane_bottom * LANE_GAP
            off = lane_bottom * WRAP_GAP
            lane_bottom += 1
        else:
            lane_y = parts_top - 16 - lane_top * LANE_GAP
            off = lane_top * WRAP_GAP
            lane_top += 1
        pts = _route_around(pa_pin, box_a, pb_pin, box_b, lane_y, off,
                            part_clear[id(box_a)], part_clear[id(box_b)])
        wires.append(RoutedWire(_clean(pts), color, label))

    # 4. cards in a far-right column
    cards: list[PlacedCard] = []
    right_edge = max((p.box.right for p in placed.values()), default=LEFT)
    cx = right_edge + CHANNEL * 0.55
    cy = TOP
    for ann in diagram.annotations:
        rows = ann.rows
        n = len(rows)
        lines = wrap_card_text(ann.text) if ann.text else []
        # baseline of the last drawn line; +18 below matches the header gap above
        if lines:
            last = FIRST_ROW + n * ROW_H + (len(lines) - 1) * TEXT_LH
        else:
            last = FIRST_ROW + (n - 1) * ROW_H
        h = last + 18
        cards.append(PlacedCard(Box(cx, cy, CARD_W, h), ann.card, rows, ann.text))
        cy += h + CARD_GAP

    # 5. bounds
    xs = [p.box.x for p in placed.values()] + [p.box.right for p in placed.values()]
    ys = [p.box.y for p in placed.values()] + [p.box.bottom for p in placed.values()]
    for wr in wires:
        for (px, py) in wr.points:
            xs.append(px)
            ys.append(py)
    for c in cards:
        xs += [c.box.x, c.box.right]
        ys += [c.box.y, c.box.bottom]
    width = (max(xs) if xs else 400) + LEFT
    # leave a clear gap below the workspace, then room for the legend band
    height = (max(ys) if ys else 300) + 56 + 52

    return Geometry(
        parts=list(placed.values()),
        wires=wires,
        cards=cards,
        legend=list(legend.items()),
        width=width,
        height=height,
        title=diagram.title,
        subtitle=diagram.subtitle,
    )


def _owner_box(placed: dict[str, PlacedPart], pin: PlacedPin) -> Box:
    for p in placed.values():
        if pin in p.pins:
            return p.box
    raise KeyError("pin has no owner")


def _faces_away(pin: PlacedPin, own: Box, other: Box) -> bool:
    """True if the pin is on the side pointing away from the other part."""
    other_is_right = other.cx >= own.cx
    if pin.side == "right":
        return not other_is_right
    if pin.side == "left":
        return other_is_right
    return False  # top/bottom always need a small detour, handled in approach


def _approach(pin: PlacedPin, own: Box, other: Box,
              track_x: float, lane_y: float) -> list[tuple[float, float]]:
    dir_right = other.cx >= own.cx  # channel is to the right of own part
    facing = "right" if dir_right else "left"
    pts: list[tuple[float, float]] = [(pin.x, pin.y)]
    if pin.side == facing:
        ex = own.right + STUB if dir_right else own.x - STUB
        pts.append((ex, pin.y))
        pts.append((track_x, pin.y))
        return pts
    # route around via the lane above the parts
    if pin.side == "left":
        sx = own.x - STUB
        pts.append((sx, pin.y))
        pts.append((sx, lane_y))
    elif pin.side == "right":
        sx = own.right + STUB
        pts.append((sx, pin.y))
        pts.append((sx, lane_y))
    elif pin.side == "top":
        pts.append((pin.x, lane_y))
    else:  # bottom
        pts.append((pin.x, own.bottom + STUB))
        pts.append((pin.x, lane_y))
    pts.append((track_x, lane_y))
    return pts


def _drop_to_lane(pin: PlacedPin, box: Box, lane_y: float, off: float,
                  clear: float) -> list[tuple[float, float]]:
    """Exit a pin on its own edge and run to a horizontal lane above/below the
    parts. ``clear`` is the base outward clearance (large enough to clear pin
    numbers, small to hug an edge with nothing protruding); ``off`` pushes the
    vertical run further out so parallel wraps on the same edge never share x."""
    if pin.side == "left":
        x = box.x - clear - off
        return [(pin.x, pin.y), (x, pin.y), (x, lane_y)]
    if pin.side == "right":
        x = box.right + clear + off
        return [(pin.x, pin.y), (x, pin.y), (x, lane_y)]
    # top / bottom pins drop straight to the lane
    return [(pin.x, pin.y), (pin.x, lane_y)]


def _route_around(pa: PlacedPin, box_a: Box, pb: PlacedPin, box_b: Box,
                  lane_y: float, off: float, clear_a: float,
                  clear_b: float) -> list[tuple[float, float]]:
    """Route a wire around the top/bottom: both ends drop to a shared lane near
    their own part edge, then meet along the lane (kept out of the channel)."""
    a = _drop_to_lane(pa, box_a, lane_y, off, clear_a)
    b = _drop_to_lane(pb, box_b, lane_y, off, clear_b)
    return a + list(reversed(b))


def _side_jumper(a: PlacedPin, b: PlacedPin, box: Box,
                 depth: float) -> list[tuple[float, float]]:
    """A short orthogonal jumper between two pins on the same edge of one part,
    bulging ``depth`` px outward from that edge."""
    if a.side == "left":
        x = box.x - depth
        return [(a.x, a.y), (x, a.y), (x, b.y), (b.x, b.y)]
    if a.side == "right":
        x = box.right + depth
        return [(a.x, a.y), (x, a.y), (x, b.y), (b.x, b.y)]
    if a.side == "top":
        y = box.y - depth
        return [(a.x, a.y), (a.x, y), (b.x, y), (b.x, b.y)]
    y = box.bottom + depth
    return [(a.x, a.y), (a.x, y), (b.x, y), (b.x, b.y)]


def _nearest_pair(ca: list[PlacedPin], cb: list[PlacedPin]):
    best = None
    best_d = None
    for a in ca:
        for b in cb:
            d = (a.x - b.x) ** 2 + (a.y - b.y) ** 2
            if best_d is None or d < best_d:
                best_d = d
                best = (a, b)
    return best


def _clean(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for p in points:
        if not out or (abs(p[0] - out[-1][0]) > 0.01 or abs(p[1] - out[-1][1]) > 0.01):
            out.append(p)
    return out
