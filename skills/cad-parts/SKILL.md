---
name: cad-parts
description: Use when designing 3D-printable technical parts or solid models with an stl-cad-server MCP server (render_model/check_model) — brackets, mounts, adapters, spacers, plates, enclosures. Triggers include "Bauteil", "Halter/Halterung konstruieren", "3D-Druck-Teil", "STL/CAD erzeugen", "design/print a bracket, mount, spacer, enclosure".
---

# CAD Parts

You model blind: you never see the geometry, only numbers. Everything follows
predict -> render -> compare -> diagnose. A mismatch between your analytic
prediction and the measured metrics is a thinking error, found before any
spec check runs.

## Setup gate

Find the connected `stl-cad-server*` MCP server (tools `render_model`,
`check_model`; load via ToolSearch). None connected -> stop; see
references/troubleshooting.md §3. Read the live resources
`cadkit://reference` and `cadkit://build123d-subset` (ReadMcpResourceTool)
before writing any code — they are the only authority on the current API.

## Workflow

1. **Feasibility gate** — expressible with boxes/cylinders + booleans?
   Threads, fillets, cones, freeform -> name what is impossible, offer an
   approximation (nut pocket instead of internal thread), get agreement.
2. **Spec interview** — one question at a time, suggest engineering defaults
   (references/recipes.md tables), until every field the spec JSON and the
   assumptions list need has a value; a user-confirmed default counts. Write
   the check_model spec + explicit assumptions. Name and resolve
   contradictory inputs before finalizing. Get confirmation BEFORE code.
3. **Spatial plan** — read references/spatial-reasoning.md. Declare the
   coordinate frame (Z = print direction). Decomposition table: feature ->
   primitive/helper -> dims -> computed center -> add/cut. Predict bbox,
   volume budget interval, and argue how each add joins: volume overlap or
   full-face contact (line/point tangency forbidden). Holes are mandatory
   budget items.
4. **Code** — prefer cadkit primitives (counterbores: `counterbore_hole`,
   grids: `pattern_holes`, through holes: `through_hole`); copy needed
   helpers from references/helpers.py unchanged; start with the explicit
   import preamble (spatial-reasoning.md §0 — the sandbox injects no
   globals); assign to `result`.
5. **Render & verify** — `render_model`, compare metrics against YOUR
   prediction first (probe by rendering isolated features — print() output
   is discarded). Only when they match, `check_model` against the spec.
6. **Diagnose & accept** — on fail: references/troubleshooting.md, name a
   hypothesis, patch minimally. On pass: report job_id + dashboard link for
   the user's visual inspection; mark each spec point server-checked vs
   sight-checked (hole POSITIONS are never server-checked). Offer saving
   (code, spec, expected_status) as a server benchmark case. User OK = done.

## Iteration rules

- Prediction mismatch is a gate: isolate with single-feature renders; never
  run check_model on an unexplained mismatch.
- Hypothesis before patch; minimal patches; never rewrite from frustration.
- 3 failures on the same check -> back to step 3, re-plan the decomposition.
- A fix that reverts an earlier fix -> stop, re-plan.

References: spatial-reasoning.md (method), helpers.py (validated snippets),
recipes.md (archetypes, screw/FDM tables, spec subtleties),
troubleshooting.md (error taxonomy, check-fail diagnosis).
