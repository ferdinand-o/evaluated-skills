# Troubleshooting: Error Taxonomy & Check-Fail Diagnosis

## 1. Server error type -> cause -> fix

| error.type | typical cause | fix |
|---|---|---|
| runtime_error (missing import) | sandbox injects NO globals — `cadkit://reference` shows no import lines; message `name 'X' is not defined` — **the dominant baseline failure: 12 wasted renders across 5 probes, every probe affected** | standard preamble: `from build123d import Pos, Rot, Box, Cylinder` / `from cadkit import box, cylinder, plate, through_hole, counterbore_hole, pattern_holes` / `import math` |
| static_check_failed | forbidden import (evidenced in this skill: cadkit, build123d, math; the server's error message names the offending import — trust it and the live resources over any hardcoded list) or forbidden call (open/eval/getattr/...) — measured (T1, `import os`): `message = "Import nicht erlaubt: os"` | remove import; use plain arithmetic |
| syntax_error | unbalanced parens/quotes — measured (T2, unclosed `(`): `message = "'(' was never closed (Zeile 2)"` | fix syntax; keep code short |
| runtime_error (bad primitive args) | negative radius, zero dims, wrong signature — measured (T4, `cylinder(-5, 10)`): type confirmed `runtime_error`, but **`message` was an empty string** (no diagnostic text returned) | check signature and value ranges against `cadkit://reference` BEFORE calling; do not expect the error message to explain what was wrong |
| export_failed (degenerate/empty result) | a boolean cut that removes everything, or `result` never assigned — measured (T3, `box(10,10,10) - box(20,20,20)`, second box fully engulfs the first): type was **`export_failed`**, `message = "Artefakte konnten nicht aus dem Container übertragen werden (docker cp/cat)"`, **not** `empty_geometry` as one might expect | predict the remainder before cutting; assign `result`; if you see this exact export_failed message, suspect an empty/degenerate solid first — it is not necessarily an infra problem |
| export_failed (tangent contact) | degenerate geometry from tangent-only contact between solids | ensure real overlap (>= 0.5 mm), never tangent |
| empty_geometry | documented type, but never observed in testing — the empty-result condition (cut removed everything) measurably surfaces as export_failed instead | treat like export_failed: predict what remains before cutting; assign result |
| timeout / resource_limit | too many booleans (large hole loops) | use pattern_holes; merge cutters with + before subtracting |

Trigger evidence (verbatim, `stl-cad-server-http`, 2026-07-10):
- T1 `import os` / `from cadkit import box` / `result = box(10,10,10)` -> `{"type": "static_check_failed", "message": "Import nicht erlaubt: os"}`
- T2 `from cadkit import box` / `result = box(10, 10, 10` -> `{"type": "syntax_error", "message": "'(' was never closed (Zeile 2)"}`
- T3 `from cadkit import box` / `result = box(10,10,10) - box(20,20,20)` -> `{"type": "export_failed", "message": "Artefakte konnten nicht aus dem Container übertragen werden (docker cp/cat)"}` (reproduced twice, jobs run_451f5fa751c3 / run_fb1e4358ab9f)
- T4 `from cadkit import cylinder` / `result = cylinder(-5, 10)` -> `{"type": "runtime_error", "message": ""}` (reproduced twice, jobs run_104c5149af20 / run_bb8d85fe0708)

## 2. Failed check -> most likely thinking error

| symptom | most likely cause | verify with | fix |
|---|---|---|---|
| volume below budget | adds do not overlap (multi-body) or cutter too big | isolation render per feature | recompute overlap positions |
| volume above budget | a cut missed the material (wrong axis/position) | render the cutter alone, check its bbox | fix cutter placement |
| bbox axis 2x expected | forgot origin-centering, placed by corner math | recompute intended centers on paper | apply Pos(dim/2) rule |
| bbox axis = expected + t | leg attached outside instead of overlapping | decomposition table | subtract t in position |
| hole check: "keine passende Bohrung" | wrong axis, or hole blocked by later add | isolation render | reorder ops: cuts last |
| hole check fails only on must_be_through | hole through a LOCAL wall, but server measures GLOBAL extent | compare hole length vs part extent | drop must_be_through |
| hole check fails on must_be_through, hole carries a counterbore/pocket | stepped bore (counterbore, nut pocket) shortens the pilot's cylindrical face to the remaining depth -> through=false ALWAYS, regardless of construction | A/B against `cadkit.counterbore_hole` on the same dims | drop must_be_through for any hole with a counterbore/pocket — this is not fixable by better modeling |
| hole passes but part looks wrong | matched an OUTER cylindrical face | distinct diameters in spec | treat positions as sight-checked |
| watertight/manifold false | tangent contact between solids | overlap argument in plan | add volume overlap (>= 0.5 mm) or full-face contact; eliminate line/point tangency |
| overhang fail despite "no overhangs" | horizontal hole ceilings / cavity ceilings are downward faces | — | omit max_overhang_deg; mark sight-checked |
| wall_thickness fail unexpectedly | thin web created by a cut near a wall | recompute local wall = distance cut edge to face | move cut or thicken wall |
| wall_thickness fail with absurd actual (e.g. 0.001 mm) despite nominal wall >= 2 mm | cone-ray wall estimator artifact at knife-edge corners of boolean cuts (server itself flags this as unreliable for organic shapes); values scatter between runs (nondeterministic across runs; see evidence: same-job re-check), not a geometry bug | recompute the nominal wall analytically (design dims, not the server number); vary the cutting parameter and see the same artifact recur | omit min_wall_thickness_mm for this geometry; mark it sight-checked instead |
| expecting probe output in logs | print() is discarded by the sandbox — `logs` stays empty (verified, job run_86b6cd6ac62f) | — | do not rely on print for diagnosis; isolation renders (render one feature/cutter alone, read its own metrics) ARE the probe |
| no way to sanity-check a render after the fact | no volume/bbox prediction was written down before rendering, so a failure or a lucky pass can't be told apart from a thinking error | — | always write the decomposition + prediction table (spatial-reasoning.md §4-5) before the first render of a part |

Baseline evidence (verbatim, `2026-07-10-cad-parts-baseline.md`, Musteranalyse):
1. Imports (see Table 1 above): *"Imports sind der dominante Fehlermodus (12 verschwendete Renders in 5 Proben; jede Probe betroffen) […] laut Referenz-Dokument ohne Import-Hinweis."*
2. must_be_through vs. global extent: *"Der Checker definiert must_be_through offenbar als 'Bohrkanal-Länge entspricht der gesamten Bauteilausdehnung entlang der Achse' […] nicht 'geht durch das lokal vorhandene Material'."* (Teil D)
2b. Stepped bores never pass must_be_through: *"jede gestufte Bohrung (Senkung, Tasche) macht must_be_through unerfüllbar, unabhängig von der Konstruktion […] Ein 'pass' auf exakt diese Spec ist mit einer physikalisch korrekten Mutternfalle nach meiner Analyse nicht erreichbar."* (Teil E, A/B-bewiesen auch gegen `cadkit.counterbore_hole`)
3. Verbatim: *"Räumliches Denken war in allen 5 Proben fehlerfrei"* (centering, overlap, cavity offsets, hole-circle trig, even intersection emulation) — this does not refute the diagnostic rows above (they remain valid safety nets for more complex parts), it shifts the skill's emphasis away from "teach spatial reasoning" and toward "secure prediction discipline + API/check semantics".
4. Verbatim: *"Kein Agent hat vor dem Render eine Volumen-/BBox-Vorhersage aufgeschrieben"* (only Teil D calculated, because the task demanded it) — harmless on simple parts here, but the GREEN criterion "prediction table present" stays in place as the safeguard for more complex parts.

Additional evidence beyond the Musteranalyse (recipe validation, Task 8):
- wall_thickness artifact: Kabelclip recipe, `min_wall_thickness_mm` reported 0.001 mm (an independent re-check of the SAME job (run_2fb7b2509f73) during task review yielded 0.003 mm instead of 0.001 mm — the estimator samples the surface randomly (unseeded), so values scatter between runs on identical geometry; a 4 mm-opening variant measured 0.017 mm) against a nominal wall of 2.0 mm — the artifact recurs across parameter changes while its magnitude is nondeterministic, confirming a detector artifact rather than a geometry bug; removed from the spec.
- print() discarded: confirmed via job run_86b6cd6ac62f (empty `logs`) and the subsequent isolation-render fix (job run_76e413f6aadb, identical metrics).

## 3. Connection / setup

No `render_model`/`check_model` tools -> server not connected: register
`http://<host>:8000/mcp` with header `Authorization: Bearer <token>`
(see stl-mcp-server README), then retry. Dashboard for visual checks:
`http://<host>:8080`.

## 4. Iteration discipline (summary — normative version in SKILL.md)

Hypothesis before patch; minimal patches; 3 fails on the same check -> back
to the spatial plan; a fix reverting an earlier fix -> stop and re-plan.
