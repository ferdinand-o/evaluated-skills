# Spatial Reasoning for Blind Solid Modeling

You never see the part. Every claim about geometry must be arithmetic you can
write down BEFORE rendering. Deviation between prediction and metrics = a
thinking error, found before any spec check.

## 0. Sandbox preamble

The sandbox injects NO global names. Every render script starts with explicit
imports, e.g.: `from build123d import Pos, Rot, Box, Cylinder` /
`from cadkit import box, cylinder, plate, through_hole, counterbore_hole,
pattern_holes` / `import math`. Missing imports are the single most common
wasted render (`name 'X' is not defined`).

## 1. Centering discipline

Every primitive (cadkit and raw build123d) is centered at the origin.
Standard formulas (h = solid height):
- base on z=0: `Pos(0, 0, h/2) * solid`
- stack onto top face at z_top: `Pos(0, 0, z_top + h/2) * solid`
- attach to a wall at y=0, solid depth d: `Pos(0, d/2, ...) * solid`
- transform order: `Pos(...) * Rot(...) * solid` — rotate first, then place.
  `Rot` takes degrees.

## 2. Cut rules

- Cutters must be LONGER than the material: use 2x the local thickness.
  For guaranteed through holes use `through_hole` (server extends the cutter
  beyond the part automatically).
- A cut that removes everything surfaces as `export_failed` (NOT
  `empty_geometry` — measured). Predict what remains before cutting.
- CAUTION `must_be_through`: the server measures hole length against the
  GLOBAL part extent along the axis. A hole through a 4 mm wall of a 40 mm
  deep part is NOT "through" — omit `must_be_through` for local walls.
- Stepped bores (counterbore, nut pocket) SHORTEN the pilot hole's
  cylindrical face to the remaining depth — the server then reports
  through=false. Never set must_be_through for a hole that carries a
  counterbore or pocket (baseline-proven: even cadkit's counterbore_hole
  cannot pass it).

## 3. Emulation tricks (narrow API)

- Intersection: `a & b == a - (a - b)`
- Hexagonal prism: intersection of 3 slabs rotated 0/60/120 deg (see
  helpers.py `hex_prism`)
- Triangular rib: box cut by a 45deg-rotated box on the hypotenuse plane
  (see helpers.py `gusset`)

## 4. Decomposition table (write it, always)

| feature | primitive/helper | dims | center position (computed) | op |
|---|---|---|---|---|

Every add must OVERLAP the union built so far (state the overlap solid and
its volume) — tangent contact produces non-watertight or multi-body results.

## 5. Volume budget

V_pred = sum(adds) - sum(overlap corrections) - sum(cuts inside material).
Every hole is a mandatory budget item (its docstring/formula tells you the
term). Tessellation rule (measured against this server, build123d default
export tolerances): cylinder side faces are inscribed facets —
- convex cylinder volume measures ~0.04 % BELOW pi*r^2*h
- parts with cut holes measure ~0.0004 % ABOVE the analytic value
Budget interval: polyhedral-only parts +/-0.1 %; parts with cylinder faces
+/-0.5 %. Wider deviation = placement or boolean error, not tessellation.

## 6. Probes (self-measurement without eyes)

- print() output is DISCARDED by the sandbox (logs stays empty) — do not
  rely on it. Your probes are renders themselves: metrics of an isolated
  feature ARE the measurement.
- Isolation render: render a single feature (or the cutter union) alone; its
  bbox verifies pattern spacing/extents. Example: 2x2 hole cutter grid,
  spacing 40x20, d=4.5 -> cutter-union bbox = (44.5, 24.5, L).
- Hole positions are NEVER verified by check_model (no position field) — use
  cutter-bbox probes + the final human visual check in the dashboard.

## 7. Worked example — wall bracket (fully computed)

Requirements: width 60 (X), base leg 40 (Y), wall leg 60 high (Z), t=4;
4 through holes d4.5 along Y in the wall leg, grid 40 (X) x 30 (Z) centered
at x=0, z=30 -> positions x=+/-20, z in {15, 45}.

Decomposition:
| feature | helper | dims | center | op |
|---|---|---|---|---|
| base leg | box | 60x40x4 | (0, 20, 2) | add |
| wall leg | box | 60x4x60 | (0, 2, 30) | add (overlap 60x4x4 at y,z in [0,4]) |
| 4 holes | through_hole | d4.5, axis Y | (+/-20, -, 15/45) | cut |

Budget: 9600 + 14400 - 960 = 23040; holes 4 * (pi/4 * 4.5^2 * 4) = 254.5
-> V_pred = 22785.5, interval [22400, 23100] (holes -> measured slightly above).
BBox prediction: (60, 40, 60). Edge clearance check: z=15-2.25=12.75 > 4 (wall
leg only), x=20+2.25=22.25 < 30. OK.

```python
from build123d import Pos
from cadkit import box, through_hole

W, LEG_A, LEG_B, T = 60.0, 40.0, 60.0, 4.0
base = Pos(0, LEG_A / 2, T / 2) * box(W, LEG_A, T)
wall = Pos(0, T / 2, LEG_B / 2) * box(W, T, LEG_B)
part = base + wall
for x, z in [(-20, 15), (20, 15), (-20, 45), (20, 45)]:
    part = through_hole(part, diameter=4.5, at=(x, 0.0, z), axis="Y")
result = part
```
