# cad-parts Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ein Claude-Code-Skill `cad-parts` (Workflow + 4 Referenzdateien), der aus NL-Beschreibungen zuverlässig druckbare technische Bauteile über den stl-cad-server erzeugt — validiert per RED-Baseline und GREEN-E2E gegen den laufenden Server.

**Architecture:** Ein Skill in `skills/cad-parts/` (Muster `enterprise-ui`): schlanke `SKILL.md` (6-Phasen-Checkliste + Iterationsregeln) + `references/` (Denk-Methode, Helfer-Snippets, Rezepte, Diagnose). Alle Geometrie-Behauptungen werden gegen den live verbundenen MCP-Server gemessen, nie angenommen.

**Tech Stack:** Claude-Code-Skill (Markdown + Python-Snippets), MCP-Server `stl-cad-server-http` (Tools `render_model`/`check_model`, Resources `cadkit://*`, `spec://schema`), cadkit/build123d-Subset.

**Spec:** `docs/superpowers/specs/2026-07-10-cad-parts-skill-design.md` (abgenommen)

## Global Constraints

- **Iron Law (writing-skills):** Task 2 (RED-Baseline) MUSS abgeschlossen und committet sein, bevor irgendein Skill-Inhalt (Tasks 4–10) geschrieben wird.
- Skill-Inhalt auf **Englisch**; Frontmatter: `name: cad-parts`; `description` startet mit "Use when", dritte Person, deutsche+englische Trigger, ≤ 1024 Zeichen, **keine Workflow-Zusammenfassung** in der description.
- `SKILL.md` < **500 Wörter** (writing-skills-Wortbudget).
- `helpers.py`: nur erlaubte Imports (`cadkit`, `build123d`, `math`); **keine** Bounding-Box-Introspektion (alle Maße explizite Parameter); `at`-Konvention der cadkit-Primitive spiegeln (`at=(x, y)` planar, `at=(x, y, z)` mit `axis`); jede Funktion mit Docstring inkl. Volumenformel; keine Duplikate zu cadkit-Primitiven (Senkung = `counterbore_hole`, Raster = `pattern_holes`).
- Alle Render-/Check-Aufrufe gegen den **verbundenen** `stl-cad-server*`-Alias. In dieser Umgebung: `stl-cad-server-http`. MCP-Tools zuerst via ToolSearch laden: `select:mcp__stl-cad-server-http__render_model,mcp__stl-cad-server-http__check_model` (bzw. den vorhandenen Alias). Resources via `ListMcpResourcesTool`/`ReadMcpResourceTool`.
- Server-Fakten (verifiziert, nicht ändern): Überhang-Check flaggt alle nach unten weisenden Flächen (horizontale Bohrungen ⇒ `max_overhang_deg` weglassen); `must_be_through` misst gegen die **globale** Bauteilausdehnung; Hole-Erkennung matcht **alle** Zylinderflächen (auch Außenflächen); BBox-Toleranz default 0,5 mm, Loch-Toleranz default 0,2 mm.
- Commit nach jedem Task (Conventional-Commit-Stil wie bisher im Repo).
- Volumen-Toleranzen in Validierungen: rein polyedrische Teile ±0,1 %, Teile mit Zylinderflächen ±1,0 % um den analytischen Wert; BBox je Achse ±0,1 mm.

## File Structure

```
skills/cad-parts/
├── SKILL.md                                    # Task 10
└── references/
    ├── spatial-reasoning.md                    # Task 7
    ├── helpers.py                              # Tasks 4–6
    ├── recipes.md                              # Task 8
    └── troubleshooting.md                      # Task 9
docs/superpowers/validation/
    ├── 2026-07-10-cad-parts-baseline.md        # Task 2 (RED)
    └── 2026-07-10-cad-parts-validation.md      # Tasks 1,3–9,11 (Messwerte, GREEN, Benchmark-Fälle)
```

---

### Task 1: Preflight & Validierungsgerüst

**Files:**
- Create: `docs/superpowers/validation/2026-07-10-cad-parts-baseline.md`
- Create: `docs/superpowers/validation/2026-07-10-cad-parts-validation.md`

**Interfaces:**
- Produces: funktionierende MCP-Verbindung; die zwei Validierungs-Dokumente, in die alle späteren Tasks Messwerte eintragen.

- [ ] **Step 1: MCP-Tools laden und Server anpingen**

ToolSearch: `select:mcp__stl-cad-server-http__render_model,mcp__stl-cad-server-http__check_model` (falls der Alias anders heißt: den vorhandenen `stl-cad-server*`-Alias nehmen und in beiden Validierungs-Dokumenten notieren).

Dann `render_model` aufrufen mit:

```python
from cadkit import box
result = box(10, 10, 10)
```

Erwartet: `status: "ok"`, `metrics.bbox_mm ≈ (10, 10, 10)`, `volume_mm3 ≈ 1000.0`, `is_watertight: true`. Bei Verbindungsfehler: STOPP, Nutzer informieren (Server starten / Token prüfen), nicht weiterarbeiten.

- [ ] **Step 2: Validierungs-Dokumente anlegen**

`docs/superpowers/validation/2026-07-10-cad-parts-baseline.md`:

```markdown
# cad-parts — RED-Baseline (ohne Skill)

Server-Alias: <hier eintragen>. Datum: 2026-07-10.
Protokoll je Teil: Anzahl render_model-Aufrufe, Fehlertypen, gescheiterte
Checks je Iteration, wörtliche Zitate charakteristischer Denkfehler,
Endstatus, finaler Code.

## Teil A — Wandhalter
(ausfüllen in Task 2)

## Teil B — Buchse
(ausfüllen in Task 2)

## Teil C — Gehäuseschale
(ausfüllen in Task 2)

## Musteranalyse
(ausfüllen in Task 2: wiederkehrende Fehlerklassen, verbatim)
```

`docs/superpowers/validation/2026-07-10-cad-parts-validation.md`:

```markdown
# cad-parts — Validierung (Messwerte & GREEN)

Server-Alias: <hier eintragen>. Datum: 2026-07-10.

## Tesselation-Kalibrierung
(ausfüllen in Task 3)

## Helfer-Validierung
(ausfüllen in Tasks 4–6: Funktion, V_analytisch, V_gemessen, Abweichung %, bbox, watertight)

## Fehlertaxonomie-Trigger
(ausfüllen in Task 9)

## GREEN-E2E (mit Skill)
(ausfüllen in Task 11)

## Benchmark-Fälle (code, spec, expected_status)
(ausfüllen in Task 11)
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/validation/
git commit -m "chore(cad-parts): Preflight + Validierungsgerüst"
```

---

### Task 2: RED-Baseline — 3 Teile ohne Skill (Iron Law)

**Files:**
- Modify: `docs/superpowers/validation/2026-07-10-cad-parts-baseline.md`

**Interfaces:**
- Produces: wörtlich dokumentierte Fehlermuster (Primärquelle für Task 9 troubleshooting.md und die Iterationsregeln in Task 10); Baseline-Metriken (Iterationszahlen) für den GREEN-Vergleich in Task 11.
- Consumes: Teil-Definitionen A/B/C (unten, verbatim — dieselben werden in Task 11 wiederverwendet).

Die drei Aufgaben-Prompts enthalten **vollständige Maße** (Baseline-Scheitern soll räumliches Denken messen, nicht fehlende Angaben). Je Teil ein **frischer Subagent** (Agent-Tool, general-purpose), der den Skill nicht kennt (er existiert noch nicht — genau deshalb läuft dieser Task zuerst).

- [ ] **Step 1: Subagent für Teil A dispatchen (Wandhalter)**

Agent-Prompt (verbatim, nur `<ALIAS>` ersetzen):

```
Du bist mit einem CAD-MCP-Server verbunden. Lade zuerst via ToolSearch:
"select:mcp__<ALIAS>__render_model,mcp__<ALIAS>__check_model" und lies die
Resources cadkit://reference und cadkit://build123d-subset via
ReadMcpResourceTool (Server: <ALIAS>).

Aufgabe: Konstruiere einen Wandhalter (L-Winkel) als Volumenkörper:
- Breite 60 mm (X), Auflage-Schenkel 40 mm (Y), Wand-Schenkel 60 mm hoch (Z),
  Materialdicke 4 mm.
- Im Wand-Schenkel 4 Durchgangsbohrungen ø 4,5 mm entlang Y, Raster 40 mm (X)
  × 30 mm (Z), Rasterzentrum bei x=0, z=30 (also Positionen x=±20, z=15 und z=45).
Rendere mit render_model und prüfe mit check_model gegen exakt diese Spec:
{"bounding_box": {"x": 60, "y": 40, "z": 60, "tolerance_mm": 0.5},
 "min_wall_thickness_mm": 3.5, "require_watertight": true,
 "require_manifold": true,
 "holes": [{"diameter_mm": 4.5, "axis": "Y", "tolerance_mm": 0.2},
           {"diameter_mm": 4.5, "axis": "Y", "tolerance_mm": 0.2},
           {"diameter_mm": 4.5, "axis": "Y", "tolerance_mm": 0.2},
           {"diameter_mm": 4.5, "axis": "Y", "tolerance_mm": 0.2}],
 "min_volume_mm3": 22400, "max_volume_mm3": 23100}
Iteriere selbständig bis pass, maximal 8 render_model-Aufrufe. Keine Rückfragen.
Berichte am Ende als Rohdaten: (1) Anzahl render-Aufrufe, (2) jeder Fehler
(error.type + message), (3) je Iteration die gescheiterten Checks
(name/expected/actual), (4) dein finaler Code, (5) Endstatus pass/fail.
```

- [ ] **Step 2: Subagent für Teil B dispatchen (Buchse)**

Gleicher Prompt-Rahmen (ToolSearch/Resources/Bericht identisch), Aufgabe + Spec ersetzt durch:

```
Aufgabe: Konstruiere eine Distanzbuchse: Außen-ø 12 mm, Innen-ø 6 mm
(durchgängig, Achse Z), Höhe 10 mm.
Spec für check_model:
{"bounding_box": {"x": 12, "y": 12, "z": 10, "tolerance_mm": 0.5},
 "min_wall_thickness_mm": 2.5, "max_overhang_deg": 45,
 "require_watertight": true, "require_manifold": true,
 "holes": [{"diameter_mm": 6, "must_be_through": true, "axis": "Z",
            "tolerance_mm": 0.2}],
 "min_volume_mm3": 800, "max_volume_mm3": 880}
```

- [ ] **Step 3: Subagent für Teil C dispatchen (Gehäuseschale)**

Gleicher Prompt-Rahmen, Aufgabe + Spec:

```
Aufgabe: Konstruiere eine oben offene Gehäuseschale: außen 50 × 30 × 20 mm
(X×Y×Z), Wand- und Bodenstärke 2,5 mm, Öffnung nach +Z.
Spec für check_model:
{"bounding_box": {"x": 50, "y": 30, "z": 20, "tolerance_mm": 0.5},
 "min_wall_thickness_mm": 2.0, "max_overhang_deg": 45,
 "require_watertight": true, "require_manifold": true,
 "min_volume_mm3": 9900, "max_volume_mm3": 10700}
```

- [ ] **Step 4: Baseline-Dokument ausfüllen**

Für jedes Teil in `2026-07-10-cad-parts-baseline.md` eintragen: Render-Anzahl, Fehlertypen, gescheiterte Checks je Iteration, **wörtliche Zitate** charakteristischer Denk-/Platzierungsfehler aus den Berichten, Endstatus, finaler Code. Abschnitt „Musteranalyse": wiederkehrende Fehlerklassen benennen (z. B. Zentrierung vergessen, Cutter zu kurz, must_be_through-Missverständnis, Volumen nicht vorhergesagt).

**Ehrlichkeits-Gate (writing-skills):** Wenn alle drei Baselines mühelos bestehen (≤ 2 Renders, keine gescheiterten Checks), hat der Skill kein nachgewiesenes Problem zu lösen → STOPP, Befund dem Nutzer berichten und Entscheidung einholen, bevor weitergebaut wird.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/validation/2026-07-10-cad-parts-baseline.md
git commit -m "test(cad-parts): RED-Baseline ohne Skill dokumentiert"
```

---

### Task 3: Tesselation-Kalibrierung

**Files:**
- Modify: `docs/superpowers/validation/2026-07-10-cad-parts-validation.md`

**Interfaces:**
- Produces: gemessene Abweichungs-Prozentwerte (Box/Zylinder/Loch) — Task 7 schreibt sie in `spatial-reasoning.md` fest.

- [ ] **Step 1: Drei Kalibrier-Renders ausführen**

Render 1 (Kontrolle, erwartet ~0 %):

```python
from cadkit import box
result = box(20, 20, 20)
```

Erwartet: `volume_mm3 = 8000.0` (±0,01 %).

Render 2 (konvexer Zylinder, erwartet: gemessen **unter** analytisch):

```python
from cadkit import cylinder
print("V_analytic", 3.141592653589793 * 25 * 20)  # 1570.796
result = cylinder(5, 20)
```

Abweichung notieren: `delta_cyl = (1570.796 - V_gemessen) / 1570.796 * 100` in %.

Render 3 (geschnittenes Loch, erwartet: gemessen **über** analytisch):

```python
from cadkit import plate, through_hole
print("V_analytic", 4800 - 3.141592653589793 / 4 * 4.5**2 * 3)  # 4752.287
result = through_hole(plate(40, 40, 3), diameter=4.5, axis="Z")
```

Abweichung notieren: `delta_hole = (V_gemessen - 4752.287) / 4752.287 * 100` in %.

- [ ] **Step 2: Werte im Validierungs-Dokument festhalten**

Abschnitt „Tesselation-Kalibrierung": Tabelle mit den drei Messungen (Form, V_analytisch, V_gemessen, Abweichung %, Vorzeichen). Daraus abgeleitete Budget-Regel als Satz formulieren, z. B. „Zylindervolumen im Mesh liegt X % unter πr²h; Budget-Intervalle für Teile mit Zylinderflächen: ±max(2·X, 0,5) %" — mit den tatsächlich gemessenen X.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/validation/2026-07-10-cad-parts-validation.md
git commit -m "test(cad-parts): Tesselation-Kalibrierung gemessen"
```

---

### Task 4: helpers.py — Platzierung & Grundkörper

**Files:**
- Create: `skills/cad-parts/references/helpers.py`
- Modify: `docs/superpowers/validation/2026-07-10-cad-parts-validation.md`

**Interfaces:**
- Produces: `bottom_at_zero(h) -> Pos`, `on_top_of(z_top, h) -> Pos`, `grid_positions(nx, ny, sx, sy) -> list[tuple[float, float]]`, `bushing(outer_d, inner_d, h) -> Part`, `l_bracket(width, leg_a, leg_b, t) -> Part`. Tasks 5–8 und 11 verwenden exakt diese Signaturen.

- [ ] **Step 1: Datei mit Kopf und erster Funktionsgruppe schreiben**

```python
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
```

- [ ] **Step 2: Validierungs-Render für Platzierung + grid_positions**

`render_model` mit (Helfer-Funktionen inline kopiert, dann):

```python
b1 = bottom_at_zero(10) * box(20, 20, 10)
b2 = on_top_of(10, 6) * box(10, 10, 6)
stack = b1 + b2
print("grid", grid_positions(2, 2, 40, 20))
holes_plate = plate(60, 40, 4)
for x, y in grid_positions(2, 2, 40, 20):
    holes_plate = through_hole(holes_plate, diameter=4.5, at=(x, y, 0.0), axis="Z")
print("V_pred_stack", 4600, "V_pred_plate", 9345.5)
result = stack + Pos(0, 0, 40) * holes_plate
```

Erwartet: `status ok`; logs enthalten `grid [(-20.0, -10.0), (-20.0, 10.0), (20.0, -10.0), (20.0, 10.0)]`. (Das kombinierte `result` dient nur dem einen Render; Stack-BBox-Anteil z ∈ [0,16].)

Besser prüfbar: zwei getrennte Renders — Render A nur `result = stack`: bbox (20, 20, 16), V = 4600 ±0,1 %. Render B nur `result = holes_plate`: bbox (60, 40, 4), V = 9345,5 +0/+1 % (Löcher im Mesh minimal kleiner). Beide Varianten ausführen, Werte notieren.

- [ ] **Step 3: Validierungs-Render bushing + l_bracket**

Render C: Helfer inline + `result = bushing(12, 6, 10)` → bbox (12, 12, 10) ±0,1; V = 848,23 ±1 %; watertight true.
Render D: Helfer inline + `result = l_bracket(60, 40, 60, 4)` → bbox (60, 40, 60) ±0,1; V = 23040 ±0,1 %; watertight true.

Bei Abweichung: Helfer korrigieren (nicht die Erwartung), erneut rendern, erst dann weiter.

- [ ] **Step 4: Messwerte in Validierungs-Dokument eintragen, Commit**

Tabelle „Helfer-Validierung" ergänzen (5 Zeilen: bottom_at_zero/on_top_of [Render A], grid_positions [Render B], bushing [C], l_bracket [D]).

```bash
git add skills/cad-parts/references/helpers.py docs/superpowers/validation/2026-07-10-cad-parts-validation.md
git commit -m "feat(cad-parts): helpers — Platzierung & Grundkörper, servervalidiert"
```

---

### Task 5: helpers.py — Profile & Schalen

**Files:**
- Modify: `skills/cad-parts/references/helpers.py`
- Modify: `docs/superpowers/validation/2026-07-10-cad-parts-validation.md`

**Interfaces:**
- Consumes: Datei + Konventionen aus Task 4.
- Produces: `u_channel(w, d, h, wall) -> Part`, `enclosure_shell(w, d, h, wall, open_top=True) -> Part`.

- [ ] **Step 1: Funktionen anhängen**

```python
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
```

(`u_channel`-Cavity: Höhe h, Zentrum z=wall → Unterkante wall−h/2 = Boden dick `wall`, Oberkante wall+h/2 > h/2 → sauberer Überschuss. Gleiches Muster bei `enclosure_shell` open_top.)

- [ ] **Step 2: Validierungs-Renders**

Render E: `result = u_channel(30, 50, 20, 3)` → bbox (30, 50, 20) ±0,1; V = 30000 − 24·50·17 = **9600** ±0,1 %.
Render F: `result = enclosure_shell(50, 30, 20, 2.5, open_top=True)` → bbox (50, 30, 20); V = 30000 − 45·25·17,5 = **10312,5** ±0,1 %.
Render G: `result = enclosure_shell(50, 30, 20, 2.5, open_top=False)` → bbox (50, 30, 20); V = 30000 − 45·25·15 = **13125** ±0,1 %; **watertight true** (verschachtelte Schalen — genau das wird hier bewiesen).

- [ ] **Step 3: Messwerte eintragen, Commit**

```bash
git add skills/cad-parts/references/helpers.py docs/superpowers/validation/2026-07-10-cad-parts-validation.md
git commit -m "feat(cad-parts): helpers — Profile & Schalen, servervalidiert"
```

---

### Task 6: helpers.py — Schnitt-Features & Emulations-Tricks

**Files:**
- Modify: `skills/cad-parts/references/helpers.py`
- Modify: `docs/superpowers/validation/2026-07-10-cad-parts-validation.md`

**Interfaces:**
- Consumes: Task-4/5-Datei.
- Produces: `slot_cut(part, width, length, cut_h, at=(0,0), along_deg=0.0) -> Part`, `hex_prism(across_flats, h) -> Part`, `NUT_AF: dict`, `nut_pocket(part, size, at, depth, clearance=0.3) -> Part`, `gusset(size, t) -> Part`.

- [ ] **Step 1: Funktionen anhängen**

```python
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
```

- [ ] **Step 2: Validierungs-Renders**

Render H: Basis `plate(40, 20, 5)`, dann `result = slot_cut(base, 5, 15, cut_h=20)` → bbox (40, 20, 5); V = 4000 − (5·10 + π·6,25)·5 = 4000 − 348,17 = **3651,8** ±1 %.
Render I: `result = hex_prism(8, 5)` → bbox (8; 9,238; 5) ±0,1; V = (√3/2)·64·5 = **277,13** ±0,1 %.
Render J: Basis `plate(20, 20, 6)`, dann `result = nut_pocket(base, "M4", at=(0, 0, 3), depth=3.2)` → bbox (20, 20, 6); V = 2400 − (√3/2)·7,3²·3,2 = 2400 − 147,67 = **2252,3** ±0,1 %.
Render K: `result = gusset(20, 4)` → bbox (4, 20, 20) ±0,1; V = **800** ±0,1 %.

Bei Abweichung: Helfer fixen (typische Kandidaten: Rotationsrichtung, Cutter-Zentrum), erneut rendern.

- [ ] **Step 3: Messwerte eintragen, Commit**

```bash
git add skills/cad-parts/references/helpers.py docs/superpowers/validation/2026-07-10-cad-parts-validation.md
git commit -m "feat(cad-parts): helpers — Schnitt-Features & Tricks, servervalidiert"
```

---

### Task 7: references/spatial-reasoning.md

**Files:**
- Create: `skills/cad-parts/references/spatial-reasoning.md`
- Modify: `docs/superpowers/validation/2026-07-10-cad-parts-validation.md`

**Interfaces:**
- Consumes: gemessene Tesselation-Werte aus Task 3 (Validierungs-Dokument, Abschnitt „Tesselation-Kalibrierung"); Helfer-Namen aus Tasks 4–6.
- Produces: die Denk-Methode, auf die `SKILL.md` (Task 10) in Phase 3 verweist; Worked Example = Referenzlösung für Teil A.

- [ ] **Step 1: Datei schreiben**

Vollständiger Inhalt (die zwei `<DELTA_*>`-Token durch die in Task 3 gemessenen Prozentwerte ersetzen — Quelle: Validierungs-Dokument):

````markdown
# Spatial Reasoning for Blind Solid Modeling

You never see the part. Every claim about geometry must be arithmetic you can
write down BEFORE rendering. Deviation between prediction and metrics = a
thinking error, found before any spec check.

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
- A cut that removes everything -> `empty_geometry`. Predict what remains.
- CAUTION `must_be_through`: the server measures hole length against the
  GLOBAL part extent along the axis. A hole through a 4 mm wall of a 40 mm
  deep part is NOT "through" — omit `must_be_through` for local walls.

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
- convex cylinder volume measures ~<DELTA_CYL> % BELOW pi*r^2*h
- parts with cut holes measure ~<DELTA_HOLE> % ABOVE the analytic value
Budget interval: polyhedral-only parts +/-0.1 %; parts with cylinder faces
+/-1 %. Wider deviation = placement or boolean error, not tessellation.

## 6. Probes (self-measurement without eyes)

- `print()` any computed control value — it returns in `logs`.
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
print("V_pred", 22785.5)
result = part
```
````

- [ ] **Step 2: Worked Example gegen den Server verifizieren**

Den Beispiel-Code exakt wie in der Datei rendern. Erwartet: bbox (60, 40, 60) ±0,1; V in [22400, 23100]; watertight true. Ergebnis in Validierungs-Dokument notieren (Zeile „worked example"). Weicht es ab: Datei korrigieren, nicht das Ergebnis.

- [ ] **Step 3: Commit**

```bash
git add skills/cad-parts/references/spatial-reasoning.md docs/superpowers/validation/2026-07-10-cad-parts-validation.md
git commit -m "feat(cad-parts): spatial-reasoning Referenz, Beispiel servervalidiert"
```

---

### Task 8: references/recipes.md

**Files:**
- Create: `skills/cad-parts/references/recipes.md`
- Modify: `docs/superpowers/validation/2026-07-10-cad-parts-validation.md`

**Interfaces:**
- Consumes: Helfer-Signaturen (Tasks 4–6), Worked Example (Task 7).
- Produces: 6 Archetypen + Engineering-Tabellen; Default-Specs, die Task 11 wiederverwendet.

- [ ] **Step 1: Datei schreiben**

Vollständiger Inhalt:

````markdown
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
No max_overhang_deg (horizontal cylinder ceiling if printed upright is fine —
axis is Z, walls vertical: 45 is OK here; include it).

```python
from build123d import Pos
from cadkit import box, cylinder, through_hole
ring = through_hole(cylinder(6, 8), diameter=8, axis="Z")
result = ring - Pos(0, 6, 0) * box(6, 12, 16)
```
Spec: bbox (12, 12, 8); min_wall 1.6; watertight; volume [370, 430];
holes: [] omitted (opening breaks the inner cylinder into a partial face —
do NOT spec the d8 bore, detection of split cylindrical faces is unreliable;
mark bore as sight-checked).

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
````

- [ ] **Step 2: Die drei nicht E2E-gedeckten Rezepte gegen den Server validieren**

(Wandhalter/Buchse/Gehäuse werden in Task 11 E2E geprüft; hier die übrigen drei.)

Render L — Montageplatte-Code aus Rezept 2, dann `check_model` mit der dort angegebenen Spec → erwartet `pass` (Volumen gemessen nahe 27841).
Render M — Kabelclip-Code aus Rezept 4, `check_model` mit Rezept-Spec → `pass`.
Render N — Flansch-Code aus Rezept 6, `check_model` mit Rezept-Spec → `pass`.

Fails: zuerst prüfen, ob die Rezept-Vorhersage falsch ist (Formel korrigieren und Fenster nachziehen — Abweichung dokumentieren) oder der Code; Datei entsprechend fixen und erneut validieren. Ergebnisse ins Validierungs-Dokument (3 Zeilen).

- [ ] **Step 3: Commit**

```bash
git add skills/cad-parts/references/recipes.md docs/superpowers/validation/2026-07-10-cad-parts-validation.md
git commit -m "feat(cad-parts): recipes + Engineering-Tabellen, 3 Rezepte servervalidiert"
```

---

### Task 9: references/troubleshooting.md (aus Baseline abgeleitet)

**Files:**
- Create: `skills/cad-parts/references/troubleshooting.md`
- Modify: `docs/superpowers/validation/2026-07-10-cad-parts-validation.md`

**Interfaces:**
- Consumes: `2026-07-10-cad-parts-baseline.md` (Task 2, Abschnitt Musteranalyse) — Primärquelle für Tabelle 2.
- Produces: Diagnose-Referenz, auf die `SKILL.md` Phase 6 verweist.

- [ ] **Step 1: Fehlertaxonomie real triggern (4 Mini-Renders)**

| Render | Code | erwarteter error.type |
|---|---|---|
| T1 | `import os` + `from cadkit import box` + `result = box(10,10,10)` | `static_check_failed` („Import nicht erlaubt: os") |
| T2 | `from cadkit import box` + `result = box(10, 10, 10` | `syntax_error` |
| T3 | `from cadkit import box` + `result = box(10,10,10) - box(20,20,20)` | `empty_geometry` |
| T4 | `from cadkit import cylinder` + `result = cylinder(-5, 10)` | `runtime_error` |

Tatsächliche `error.type` + `message` im Validierungs-Dokument („Fehlertaxonomie-Trigger") festhalten. Weicht ein Typ ab: die Tabelle in Schritt 2 mit dem **gemessenen** Verhalten schreiben.

- [ ] **Step 2: Datei schreiben**

Gerüst (Tabelle 1 mit den in Schritt 1 gemessenen Meldungen füllen; Tabelle 2: die Zeilen unten sind Startpunkte — **jede in der Baseline beobachtete Fehlerklasse wird als eigene Zeile mit wörtlichem Zitat ergänzt**, Quelle: `2026-07-10-cad-parts-baseline.md` Musteranalyse; Startzeilen, die die Baseline widerlegt, streichen):

````markdown
# Troubleshooting: Error Taxonomy & Check-Fail Diagnosis

## 1. Server error type -> cause -> fix

| error.type | typical cause | fix |
|---|---|---|
| static_check_failed | forbidden import (allowed: cadkit, build123d, math, numpy, typing) or forbidden call (open/eval/getattr/...) | remove import; use plain arithmetic |
| syntax_error | unbalanced parens/quotes | fix syntax; keep code short |
| runtime_error | bad primitive args (negative radius, zero dims), wrong signature | check signature against cadkit://reference |
| empty_geometry | cut removed everything, or `result` never assigned | predict remainder before cutting; assign `result` |
| export_failed | degenerate geometry (tangent-only contact) | ensure real overlap, never tangent |
| timeout / resource_limit | too many booleans (large hole loops) | use pattern_holes; merge cutters with + before subtracting |

## 2. Failed check -> most likely thinking error

| symptom | most likely cause | verify with | fix |
|---|---|---|---|
| volume below budget | adds do not overlap (multi-body) or cutter too big | isolation render per feature | recompute overlap positions |
| volume above budget | a cut missed the material (wrong axis/position) | render the cutter alone, check its bbox | fix cutter placement |
| bbox axis 2x expected | forgot origin-centering, placed by corner math | print intended centers | apply Pos(dim/2) rule |
| bbox axis = expected + t | leg attached outside instead of overlapping | decomposition table | subtract t in position |
| hole check: "keine passende Bohrung" | wrong axis, or hole blocked by later add | isolation render | reorder ops: cuts last |
| hole check fails only on must_be_through | hole through a LOCAL wall, but server measures GLOBAL extent | compare hole length vs part extent | drop must_be_through |
| hole passes but part looks wrong | matched an OUTER cylindrical face | distinct diameters in spec | treat positions as sight-checked |
| watertight/manifold false | tangent contact between solids | overlap argument in plan | add real overlap (>= 0.5 mm) |
| overhang fail despite "no overhangs" | horizontal hole ceilings / cavity ceilings are downward faces | — | omit max_overhang_deg; mark sight-checked |
| wall_thickness fail unexpectedly | thin web created by a cut near a wall | recompute local wall = distance cut edge to face | move cut or thicken wall |

## 3. Connection / setup

No `render_model`/`check_model` tools -> server not connected: register
`http://<host>:8000/mcp` with header `Authorization: Bearer <token>`
(see stl-mcp-server README), then retry. Dashboard for visual checks:
`http://<host>:8080`.

## 4. Iteration discipline (summary — normative version in SKILL.md)

Hypothesis before patch; minimal patches; 3 fails on the same check -> back
to the spatial plan; a fix reverting an earlier fix -> stop and re-plan.
````

- [ ] **Step 3: Baseline-Muster einarbeiten**

Jede Fehlerklasse aus der Baseline-Musteranalyse als Zeile in Tabelle 2 ergänzen (Symptom, Ursache, Fix — mit dem wörtlichen Baseline-Zitat als Beleg im Zeilen-Kommentar oder darunter). Prüfen: keine Baseline-Klasse ohne Zeile.

- [ ] **Step 4: Commit**

```bash
git add skills/cad-parts/references/troubleshooting.md docs/superpowers/validation/2026-07-10-cad-parts-validation.md
git commit -m "feat(cad-parts): troubleshooting aus Baseline + getriggerter Taxonomie"
```

---

### Task 10: SKILL.md

**Files:**
- Create: `skills/cad-parts/SKILL.md`

**Interfaces:**
- Consumes: alle references/-Dateien (Tasks 4–9).
- Produces: den Skill-Einstiegspunkt; Task 11 lädt genau diese Datei in die GREEN-Subagenten.

- [ ] **Step 1: Datei schreiben**

Vollständiger Inhalt (< 500 Wörter; bei Anpassungen Wortbudget halten):

````markdown
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
   the check_model spec + explicit assumptions; get confirmation BEFORE code.
3. **Spatial plan** — read references/spatial-reasoning.md. Declare the
   coordinate frame (Z = print direction). Decomposition table: feature ->
   primitive/helper -> dims -> computed center -> add/cut. Predict bbox,
   volume budget interval, and argue pairwise overlap (never tangent).
   Holes are mandatory budget items.
4. **Code** — prefer cadkit primitives (counterbores: `counterbore_hole`,
   grids: `pattern_holes`, through holes: `through_hole`); copy needed
   helpers from references/helpers.py unchanged; add `print()` probes;
   assign to `result`.
5. **Render & verify** — `render_model`, compare metrics against YOUR
   prediction first. Only when they match, `check_model` against the spec.
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
````

- [ ] **Step 2: Wortbudget und Frontmatter prüfen**

PowerShell: `((Get-Content skills\cad-parts\SKILL.md -Raw) -split '\s+').Count`
Erwartet: < 500. Frontmatter-Check: name nur Kleinbuchstaben/Bindestrich ✓; description beginnt mit "Use when", dritte Person, < 1024 Zeichen, keine Workflow-Zusammenfassung ✓. Über Budget → kürzen (zuerst: Workflow-Sätze straffen), nicht Referenzverweise streichen.

- [ ] **Step 3: Commit**

```bash
git add skills/cad-parts/SKILL.md
git commit -m "feat(cad-parts): SKILL.md — 6-Phasen-Workflow + Iterationsregeln"
```

---

### Task 11: GREEN — E2E mit Skill + Benchmark-Fälle

**Files:**
- Modify: `docs/superpowers/validation/2026-07-10-cad-parts-validation.md`

**Interfaces:**
- Consumes: Teil-Definitionen + Specs aus Task 2 (verbatim wiederverwenden); `skills/cad-parts/SKILL.md` + references (Tasks 4–10); Baseline-Metriken (Task 2) als Vergleichsmaßstab.
- Produces: GREEN-Nachweis + Benchmark-Tabelle `(code, spec, expected_status)`.

- [ ] **Step 1: 3 GREEN-Subagenten dispatchen**

Je Teil A/B/C ein frischer Subagent. Prompt = **identischer** Aufgaben-/Spec-Text wie in Task 2, mit diesem Zusatz VOR der Aufgabe:

```
Lies zuerst vollständig skills/cad-parts/SKILL.md (im Repo-Root) und folge
dem Workflow strikt. Die Referenzdateien liegen unter
skills/cad-parts/references/. Alle Maße sind vollständig gegeben — Phase 2
reduziert sich auf das Aufschreiben von Spec + Annahmen (keine Rückfragen).
```

Bericht-Anforderung identisch zu Task 2 (Rohdaten: Render-Anzahl, Fehler, Checks je Iteration, finaler Code, Endstatus), zusätzlich: die Vorhersagetabelle (bbox/V_pred) aus Phase 3.

- [ ] **Step 2: GREEN vs. RED auswerten**

Akzeptanzkriterien (alle drei Teile):
1. Endstatus `pass` via `render_model` → `check_model`.
2. Render-Anzahl ≤ Baseline-Render-Anzahl des jeweiligen Teils.
3. Keine Wiederholung der in der Baseline dokumentierten Fehlerklassen (Abgleich gegen Musteranalyse).
4. Vorhersagetabelle vorhanden und Metriken innerhalb der vorhergesagten Intervalle.

Ergebnis als Vorher/Nachher-Tabelle ins Validierungs-Dokument („GREEN-E2E"). Kriterium verletzt → REFACTOR: betroffene Skill-/Referenzdatei anpassen (z. B. fehlende Diagnose-Zeile, unklare Formel), Subagent für das betroffene Teil **erneut frisch** dispatchen, bis Kriterien erfüllt. Jede Anpassung committen.

- [ ] **Step 3: Benchmark-Fälle dokumentieren**

Abschnitt „Benchmark-Fälle": je Teil A/B/C ein Block mit `code` (finaler GREEN-Code), `spec` (JSON aus Task 2), `expected_status: "pass"` — copy-paste-fähig für `tests/benchmark/test_regression.py` im stl-mcp-server (Übernahme dorthin ist NICHT Teil dieses Plans).

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/validation/2026-07-10-cad-parts-validation.md
git commit -m "test(cad-parts): GREEN-E2E bestanden, Benchmark-Fälle dokumentiert"
```

---

### Task 12: Qualitäts-Gate & Abschluss

**Files:**
- Modify: ggf. `skills/cad-parts/SKILL.md`, `skills/cad-parts/references/*` (nur bei Befunden)

**Interfaces:**
- Consumes: alles Vorherige.
- Produces: abnahmereifer Skill.

- [ ] **Step 1: writing-skills-Checkliste durchgehen**

Prüfen und Befunde direkt fixen:
- Frontmatter: name/description-Regeln (siehe Task 10 Step 2) — erneut prüfen nach etwaigen REFACTOR-Edits.
- Wortbudget SKILL.md < 500 (Kommando aus Task 10 Step 2).
- Keine @-Links, Referenzen nur als Pfadnennung.
- Keine narrativen Einmal-Geschichten in den Referenzen; Tabellen statt Prosa wo scanbar.
- Alle in SKILL.md referenzierten Dateien existieren; alle Helfer-Namen in recipes/spatial-reasoning stimmen mit helpers.py überein (`grep -n "helpers.py\|hex_prism\|l_bracket\|enclosure_shell\|slot_cut\|nut_pocket\|gusset\|bushing\|u_channel\|grid_positions\|bottom_at_zero\|on_top_of" skills/cad-parts/ -r`).

- [ ] **Step 2: Frische-Session-Hinweis an den Nutzer**

Dem Nutzer melden: Skill ist committet; zum finalen Abnahmetest eine **neue** Claude-Code-Session starten und z. B. „Konstruiere mir einen Wandhalter für eine 25-mm-Stange" eingeben — erwartet: Skill triggert, Spec-Interview beginnt. (Manueller Schritt des Nutzers; Ergebnis abwarten, Befunde ggf. als REFACTOR einarbeiten.)

- [ ] **Step 3: Abschluss-Commit**

```bash
git add -A
git commit -m "feat(cad-parts): Qualitaets-Gate abgeschlossen"
```

(Nur committen, wenn Step 1 Änderungen erzeugt hat; sonst entfällt der Commit.)

---

## Self-Review (durchgeführt beim Schreiben des Plans)

**Spec-Abdeckung:** §4 Architektur/Dateien → Tasks 4–10; §5 Workflow-Phasen → Task 10; §5 „Grenzen der deterministischen Abnahme" → spatial-reasoning §6, recipes „Spec subtleties", SKILL.md Phase 6; §6.1–6.4 → Tasks 7, 4–6, 8, 9; §7 Iterationsregeln → SKILL.md; §8 Fehlerbehandlung → troubleshooting §1/§3 + SKILL.md Setup-Gate; §9 RED → Task 2, GREEN 1–4 → Tasks 4–6 (Helfer), 11 (E2E + Benchmark), 3+7 (Tesselation messen & festschreiben), 12 (writing-skills-Qualität + frische Session). Keine offenen Spec-Punkte.

**Platzhalter:** Die `<DELTA_*>`-Token in Task 7 und die „ausfüllen in Task N"-Marker in Task 1 sind definierte Datenflüsse mit exakter Quelle, keine offenen Arbeitsaufträge.

**Typ-/Namenskonsistenz:** Helfer-Signaturen identisch in Tasks 4–6 (Definition), 7 (§3/§7), 8 (Rezepte 3/5), 12 (grep-Liste). Teil-Specs A/B/C identisch in Task 2 und Task 11 (verbatim-Wiederverwendung). Validierungs-Dokumentpfade konsistent.
