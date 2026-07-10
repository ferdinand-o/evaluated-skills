"""cad-parts helper snippets — COPY the needed functions (plus their imports
and module constants) verbatim into render_model code. This file is never
imported as a module. Allowed sandbox imports: cadkit, build123d, math.
Every docstring states the exact volume formula for the volume budget.
Placement convention mirrors cadkit: at=(x, y) planar, at=(x, y, z) + axis.
Do not re-implement cadkit primitives: counterbores -> counterbore_hole,
hole grids -> pattern_holes, guaranteed through holes -> through_hole."""

import math

from build123d import Pos, Rot
from cadkit import box, cylinder, plate, through_hole


# --- placement shortcuts (all primitives are origin-centered!) ---

def bottom_at_zero(h):
    """Pos that lifts a solid of height h so its base sits on z=0."""
    return Pos(0, 0, h / 2)


def on_top_of(z_top, h):
    """Pos that stacks a solid of height h onto an existing top face at z_top."""
    return Pos(0, 0, z_top + h / 2)


def grid_positions(nx, ny, sx, sy):
    """Centered nx x ny grid of (x, y) positions with spacing sx, sy.
    Use for custom per-position features; for plain hole grids prefer
    cadkit.pattern_holes."""
    return [
        ((i - (nx - 1) / 2) * sx, (j - (ny - 1) / 2) * sy)
        for i in range(nx)
        for j in range(ny)
    ]


# --- basic solids ---

def bushing(outer_d, inner_d, h):
    """Sleeve / spacer around Z, centered at origin.
    Volume = pi/4 * (outer_d**2 - inner_d**2) * h."""
    return through_hole(cylinder(outer_d / 2, h), diameter=inner_d, axis="Z")


def l_bracket(width, leg_a, leg_b, t):
    """L-profile: horizontal leg on z=0 (y in [0, leg_a]), vertical leg on
    y=0 (z in [0, leg_b]), width along X, thickness t. Corner overlap is a
    full t x t solid, never tangent. Requires leg_a > t and leg_b > t.
    Volume = width * t * (leg_a + leg_b - t)."""
    horizontal = Pos(0, leg_a / 2, t / 2) * box(width, leg_a, t)
    vertical = Pos(0, t / 2, leg_b / 2) * box(width, t, leg_b)
    return horizontal + vertical


# --- profiles & shells ---

def u_channel(w, d, h, wall):
    """U-profile extruded along Y (full depth d), opening towards +Z,
    floor thickness = wall. Requires w > 2*wall and h > wall.
    Volume = w*d*h - (w - 2*wall) * d * (h - wall)."""
    outer = box(w, d, h)
    cavity = Pos(0, 0, wall) * box(w - 2 * wall, 2 * d, h)
    return outer - cavity


def enclosure_shell(w, d, h, wall, open_top=True):
    """Rectangular enclosure, walls and floor = wall thick.
    open_top=True: cavity breaks through +Z.
      Volume = w*d*h - (w-2*wall)*(d-2*wall)*(h-wall)
    open_top=False: fully closed hollow box (two nested shells, watertight).
      Volume = w*d*h - (w-2*wall)*(d-2*wall)*(h-2*wall)."""
    outer = box(w, d, h)
    if open_top:
        cavity = Pos(0, 0, wall) * box(w - 2 * wall, d - 2 * wall, h)
    else:
        cavity = box(w - 2 * wall, d - 2 * wall, h - 2 * wall)
    return outer - cavity


# --- cut features & emulation tricks ---
# Intersection is not in the allowed subset; emulate: a & b == a - (a - b).

def slot_cut(part, width, length, cut_h, at=(0.0, 0.0), along_deg=0.0):
    """Cut a slot (stadium shape) along Z through the part. length = overall
    (incl. end radii), width = slot width, cut_h = cutter height — pass
    2 * material thickness so the cut fully penetrates. at=(x, y) is the slot
    center, along_deg rotates the slot in the XY plane (0 = along X).
    Removed volume (full penetration through thickness t):
      (width * (length - width) + pi/4 * width**2) * t."""
    straight = length - width
    cutter = box(straight, width, cut_h)
    cutter = cutter + Pos(-straight / 2, 0, 0) * cylinder(width / 2, cut_h)
    cutter = cutter + Pos(straight / 2, 0, 0) * cylinder(width / 2, cut_h)
    return part - Pos(at[0], at[1], 0) * (Rot(0, 0, along_deg) * cutter)


def hex_prism(across_flats, h):
    """Hexagonal prism around Z (flats at x = +/- across_flats/2) via
    intersection of three slabs rotated 0/60/120 deg.
    Volume = (sqrt(3)/2) * across_flats**2 * h.
    BBox = (across_flats, 2*across_flats/sqrt(3), h)."""
    s0 = box(across_flats, 2 * across_flats, h)
    s60 = Rot(0, 0, 60) * box(across_flats, 2 * across_flats, h)
    s120 = Rot(0, 0, 120) * box(across_flats, 2 * across_flats, h)
    r = s0 - (s0 - s60)      # s0 & s60
    return r - (r - s120)    # ... & s120


NUT_AF = {"M3": 5.5, "M4": 7.0, "M5": 8.0, "M6": 10.0, "M8": 13.0}


def nut_pocket(part, size, at, depth, clearance=0.3):
    """Hex pocket for a DIN 934 nut, cut along Z. at=(x, y, z) is the point ON
    the surface where the pocket opens (cutter is 2*depth tall and centered
    there -> exactly `depth` goes into the material). size e.g. "M4".
    Removed volume = (sqrt(3)/2) * (NUT_AF[size] + clearance)**2 * depth."""
    af = NUT_AF[size] + clearance
    cutter = Pos(at[0], at[1], at[2]) * hex_prism(af, 2 * depth)
    return part - cutter


def gusset(size, t):
    """Triangular stiffener rib: right triangle in the YZ plane (legs = size
    on y=0 wall and z=0 floor), thickness t along X. Hypotenuse via a 45deg
    rotated cutter box on the plane y + z = size.
    Volume = t * size**2 / 2. BBox = (t, size, size)."""
    block = Pos(0, size / 2, size / 2) * box(t, size, size)
    c = size / 2 + size / math.sqrt(2)
    cutter = Pos(0, c, c) * (Rot(45, 0, 0) * box(2 * t, 2 * size, 2 * size))
    return block - cutter
