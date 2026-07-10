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
