# Part Archetypes & Engineering Tables

## Screw clearance table (DIN-medium through holes, DIN 912 cyl-head)

| size | through hole | cbore dia (head+1) | cbore depth (head h + 0.2) | nut AF (DIN 934) |
|---|---|---|---|---|
| M2.5 | 2.9 | 5.5 | 2.7 | 5.0 |
| M3 | 3.4 | 6.5 | 3.2 | 5.5 |
| M4 | 4.5 | 8.0 | 4.2 | 7.0 |
| M5 | 5.5 | 9.5 | 5.2 | 8.0 |
| M6 | 6.6 | 11.0 | 6.2 | 10.0 |
| M8 | 9.0 | 14.0 | 8.2 | 13.0 |

Counterbores: use cadkit `counterbore_hole(part, diameter, cbore_diameter,
cbore_depth, at=(x, y))` — never stack cylinders manually.

## FDM defaults (assume unless user says otherwise)

- wall/floor >= 1.2 mm (0.4 nozzle); recommended 2.4+ for structural parts
- overhang limit 45 deg — BUT: the server's overhang check flags ALL
  downward faces. Horizontal holes and closed cavity ceilings always exceed
  it -> omit `max_overhang_deg` from the spec for such parts (note it as
  sight-checked instead).
- horizontal holes: +0.2..0.4 mm diameter compensation
- clearance fit 0.2 mm (snug) / 0.4 mm (loose)
- model in print orientation: Z = build direction, largest flat face on z=0

## Spec subtleties (server-verified)

- `must_be_through` compares hole length to the GLOBAL part extent — only set
  it for holes through the whole part.
- Hole detection matches ALL cylindrical faces incl. OUTER ones (a bushing's
  outer wall can satisfy a hole spec) — keep diameters distinct in specs.
- Hole POSITIONS are never checked by the server (no position field in
  HoleSpec) — verify via cutter-bbox probes + human visual check.
- Stepped bores (counterbore, nut pocket) SHORTEN the pilot's cylindrical
  face to the remaining depth -> through=false. Never set must_be_through
  for a hole that carries a counterbore or pocket (proven: even cadkit's
  counterbore_hole cannot pass it).
- print() output is discarded by the sandbox (logs stays empty) — probes
  are isolation renders, see spatial-reasoning.md §6.

## Archetypes

Each: params -> decomposition -> default spec. Volumes: state the analytic
formula, set the spec window per spatial-reasoning.md §5.

### 1. Wall bracket (Wandhalter)
See the fully computed worked example in spatial-reasoning.md §7 (params:
width, leg_a, leg_b, t, hole grid). Default spec = bbox exact, min_wall
= t - 0.5, watertight+manifold, holes d+axis only (no must_be_through,
no max_overhang_deg — horizontal holes).

### 2. Mounting plate (Montageplatte)
plate(W, D, T) + `pattern_holes` or per-position `counterbore_hole`.
Default: 80x60x6, 4x M4 cbore (4.5/8.0/4.2), grid 60x40.
V = 80*60*6 - 4*(pi/4*4.5^2*6 + pi/4*8^2*4.2 - pi/4*4.5^2*4.2) = 27841.
Spec: bbox (80, 60, 6); holes 4x {diameter_mm: 4.5, axis: "Z"} — NO
must_be_through: the cbore shortens the pilot's cylindrical face to
T - cbore_depth (baseline probe E proved stepped bores can never satisfy
must_be_through); min_wall 1.5; max_overhang_deg 45 (cbore shoulders
face UP -> fine); volume [27300, 28200].

```python
from cadkit import plate, counterbore_hole
part = plate(80, 60, 6)
for x, y in [(-30, -20), (-30, 20), (30, -20), (30, 20)]:
    part = counterbore_hole(part, diameter=4.5, cbore_diameter=8.0,
                            cbore_depth=4.2, at=(x, y))
result = part
```

### 3. Spacer / bushing (Distanzstueck)
helpers `bushing(outer_d, inner_d, h)`. Default 12/6/10:
V = pi/4*(144-36)*10 = 848.2 -> spec volume [800, 880], bbox (12, 12, 10),
hole {6, through, Z}, min_wall 2.5, max_overhang_deg 45.

### 4. Cable clip (Kabelclip)
C-ring: bushing minus a front opening cut.
Default: cable d8 -> inner 8, wall 2 (outer 12), h 8, opening 6 wide (+Y).
Removed opening ~ arc*wall*h with arc = 2*asin(3/r_mid)*r_mid, r_mid=5
-> 6.44*2*8 = 103. V = pi/4*(144-64)*8 - 103 = 399.7 -> window [370, 430].
No max_overhang_deg (axis is Z, walls vertical -> 45 is fine, but a local
feature like the rest of the archetypes: omit and sight-check).

BBox correction (server-verified, deviation from an earlier draft): the box
cutter's flat faces at x=+-opening/2 (here +-3) do NOT reach the ring's
outer radius, so the top of the bbox is the arc height at the cut boundary,
not the full outer radius: y_max = sqrt(outer_r^2 - (opening/2)^2) =
sqrt(36-9) = 5.196; combined with the untouched bottom arc (-outer_r = -6):
bbox_y = outer_r + sqrt(outer_r^2 - (opening/2)^2) = 11.196 -> spec bbox
(12, 11.2, 8), NOT (12, 12, 8) (measured 11.194287, matches to 0.02%).

```python
from build123d import Pos
from cadkit import box, cylinder, through_hole
ring = through_hole(cylinder(6, 8), diameter=8, axis="Z")
result = ring - Pos(0, 6, 0) * box(6, 12, 16)
```
Spec: bbox (12, 11.2, 8); watertight; volume [370, 430]; holes: [] omitted
(opening breaks the inner cylinder into a partial face — do NOT spec the d8
bore, detection of split cylindrical faces is unreliable; mark bore as
sight-checked). min_wall_thickness_mm OMITTED (server-verified): the
cone-ray wall estimator reports a near-zero value at the notch/outer-surface
corner edge regardless of opening width (reproduced at 6 mm and 4 mm
openings: 0.001 mm resp. 0.017 mm, confidence 1.00 both times) — a
detection artifact at this corner geometry (self-flagged by the server as
unreliable for non-simple shapes), not a real defect; nominal wall by
construction is (outer_d - inner_d)/2 = 2 mm. Sight-check the physical wall
instead of specing it.

### 5. Enclosure shell (Gehaeuse)
helpers `enclosure_shell(w, d, h, wall, open_top)`. Default 50x30x20, wall
2.5, open top: V = 30000 - 45*25*17.5 = 10312.5 -> window [9900, 10700];
bbox (50, 30, 20); min_wall 2.0; max_overhang_deg 45 (open top: cavity floor
faces up). Closed variant: volume 13125; omit max_overhang_deg (cavity
ceiling faces down = flagged).

### 6. Flange adapter (Flansch-Adapter)
Disc + hub + center bore + bolt circle (4 bolts on axes: no trig needed).
Default: flange d60x5, hub d30x15 on top, center bore d20 through, 4x d5.5
on bolt circle r22.5 at 0/90/180/270 deg.
V = pi/4*(60^2*5 + 30^2*15 - 20^2*20) - 4*(pi/4*5.5^2*5) = 17982
-> window [17500, 18400]; bbox (60, 60, 20); holes: center
{20, through, Z} + 4x {5.5, axis Z} (bolt holes pierce only the 5 mm flange
-> NO must_be_through); min_wall 2.0; max_overhang_deg 45.

```python
from build123d import Pos
from cadkit import cylinder, through_hole
flange = Pos(0, 0, 2.5) * cylinder(30, 5)
hub = Pos(0, 0, 12.5) * cylinder(15, 15)
part = flange + hub
part = through_hole(part, diameter=20, axis="Z")
for x, y in [(22.5, 0), (0, 22.5), (-22.5, 0), (0, -22.5)]:
    part = through_hole(part, diameter=5.5, at=(x, y, 0.0), axis="Z")
result = part
```
