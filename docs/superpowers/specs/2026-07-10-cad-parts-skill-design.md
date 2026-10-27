# cad-parts — Skill für räumliches Denken & Volumenkörpererstellung

- **Datum:** 2026-07-10
- **Status:** Entwurf (zur Review)
- **Autor:** ferdinand-o + Claude (brainstorming)
- **Repo:** `evaluated-skills`
- **Abhängigkeit:** MCP-Server `stl-cad-server-http` (Repo `stl-mcp-server`, dort Teilprojekt 1)

---

## 1. Kontext & Ziel

Der stl-mcp-server stellt zwei Werkzeuge bereit — `render_model(code)` und
`check_model(job_id, spec)` — sowie Grounding-Resources (`cadkit://reference`,
`cadkit://examples`, `cadkit://build123d-subset`, `spec://schema`). Die Server-Spec
legt fest: „Die Intelligenz lebt im Client." Das ursprünglich geplante Teilprojekt 2
(Orchestrator + Vision-Loop) wird hier durch einen **Claude-Code-Skill** ersetzt bzw.
vorweggenommen: Claude Code selbst ist der intelligente MCP-Client.

Die zentrale Schwierigkeit: Das Modell arbeitet **blind**. Es sieht die Geometrie nie —
es bekommt nur Zahlen zurück (Bounding-Box, Volumen, watertight/manifold,
Dreieckszahl) plus deterministische Check-Ergebnisse. Der Skill kompensiert diese
Blindheit durch eine explizite Denk-Methode: **vorhersagen → rendern → vergleichen →
diagnostizieren**. Jede Abweichung zwischen analytischer Vorhersage und gemessener
Realität ist ein entdeckter Denkfehler.

**Ziel:** Ein Skill, mit dem Claude Code aus natürlichsprachlichen Beschreibungen
zuverlässig korrekte, druckbare technische Bauteile erzeugt — mit messbarer Abnahme
(„TDD für CAD") statt Trial-and-Error.

## 2. Scope & Nicht-Ziele

**In Scope**
- Ein Skill `cad-parts` in `skills/cad-parts/` mit `SKILL.md` + `references/`.
- Voller Workflow: Spec-Interview → räumlicher Bauplan → Code → Render → Check →
  Diagnose-Iteration → Sichtabnahme.
- Geprüfte Hilfsfunktionen als Copy-Paste-Snippets (`references/helpers.py`), die
  bei Bedarf inline in den `render_model`-Code eingefügt werden.
- Zielgruppe Bauteile: **funktionale FDM-Druckteile** — Halter, Winkel, Adapter,
  Distanzstücke, Montageplatten, einfache Gehäuse; Schraubbilder und Durchbrüche.

**Nicht-Ziele**
- Keine Änderungen am stl-mcp-server (keine neuen cadkit-Primitive, kein Deployment).
  Bewährte Helfer können *später* in einem eigenen Zyklus zu cadkit-Primitiven
  promoted werden; dieser Pfad ist explizit offen, aber nicht Teil dieses Projekts.
- Kein lokales Validierungs-Script (keine Duplikation der Server-Logik im Skill).
- Keine Teile außerhalb der API-Möglichkeiten: Gewinde, Fasen/Fillets, Kegel,
  Freiformen, Sweeps. Der Skill erkennt das früh und bietet Annäherungen an
  (z. B. Muttern-Tasche statt Innengewinde).
- Kein VLM-/Bild-Loop. Sichtprüfung macht der Mensch im Dashboard des Servers.

## 3. Getroffene Grundentscheidungen (aus dem Brainstorming)

| Frage | Entscheidung |
|---|---|
| Rolle des Skills | Voller Workflow („Orchestrator im Kopf") |
| Ort der Hilfsfunktionen | Snippets im Skill, kein Server-Umbau |
| Bauteil-Domäne | Funktionale FDM-Druckteile |
| Umgang mit unvollständigen Angaben | Spec-Interview **so lange, bis 100 % aller relevanten Angaben vorliegen** |
| Abnahmekriterium | `check_model` pass **und** Sichtprüfung durch den Nutzer im Server-Dashboard |
| Architektur | Ein Skill + Referenzdateien (progressive Disclosure) |

## 4. Architektur & Dateien

```
skills/cad-parts/
├── SKILL.md                       # Workflow (6 Phasen) + Iterationsregeln
└── references/
    ├── spatial-reasoning.md       # Denk-Methode: Koordinaten, Platzierung, Vorhersage
    ├── helpers.py                 # geprüfte Copy-Paste-Hilfsfunktionen
    ├── recipes.md                 # Bauteil-Archetypen + Engineering-Tabellen
    └── troubleshooting.md         # Diagnose-Tabellen (Fehlertypen, Check-Fails)
```

**Progressive Disclosure & Wortbudget:** `SKILL.md` bleibt schlank (Ziel gemäß
writing-skills: < 500 Wörter). Die 6 Phasen werden als kompakte Checkliste
formuliert; die Fehlerbehandlung (§8) wandert bis auf den Verbindungs-Abbruch
nach `troubleshooting.md`; die Iterationsregeln (§7) bleiben als Disziplin-Kern
in der `SKILL.md`. Die Referenzen werden nur in der jeweils passenden Phase
gelesen (`spatial-reasoning.md` in Phase 3, `troubleshooting.md` nur bei Fails
usw.).

**Kein API-Drift:** `SKILL.md` dupliziert die cadkit-API-Signaturen **nicht**. Sie
weist an, zu Beginn `cadkit://reference` und `cadkit://build123d-subset` live vom
Server zu lesen — diese Resources sind die einzige Autorität für die aktuelle
API-Oberfläche. Die Referenzdateien des Skills bauen nur auf dem **stabilen Kern**
auf und lehren Nutzungsmuster darauf. Der stabile Kern umfasst das
build123d-Subset (Box/Cylinder, `+`/`-`, `Pos`/`Rot`, Zentrierung im Ursprung)
**und die cadkit-Primitive der gepinnten Version** (`box`, `cylinder`, `plate`,
`through_hole`, `counterbore_hole`, `pattern_holes`); bei Widerspruch gewinnen
die Live-Resources. Der Skill liefert, was der Server nicht liefern kann:
Methode, Helfer, Rezepte, Diagnose.

**Operationalisierung des Resource-Zugriffs:** `SKILL.md` nennt den konkreten
Mechanismus in Claude Code — `ListMcpResourcesTool`/`ReadMcpResourceTool` mit
Servername + URI — und legt sich **nicht** auf einen festen Servernamen fest:
Es zählt der tatsächlich verbundene `stl-cad-server*`-Alias (z. B.
`stl-cad-server` oder `stl-cad-server-http`); erkennbar an den verfügbaren
`render_model`/`check_model`-Tools.

**Frontmatter-Entwurf (Trigger deutsch + englisch, Muster wie `handoff`):**

```yaml
name: cad-parts
description: Use when designing 3D-printable technical parts with the
  stl-cad-server MCP server (render_model/check_model) — brackets, mounts,
  adapters, spacers, plates, enclosures. Triggers include "Bauteil",
  "Halter/Halterung konstruieren", "3D-Druck-Teil", "STL erzeugen", "CAD",
  "design/print a bracket, mount, spacer, enclosure".
```

## 5. Workflow (Inhalt der SKILL.md) — 6 Phasen

### Phase 1 — Machbarkeits-Gate
Prüfen, ob das Teil mit Quader/Zylinder + Booleans (Vereinigung, Differenz,
emulierte Schnittmenge) ausdrückbar ist. Nicht machbar (Gewinde, Fillets, Kegel,
Freiform) → sofort benennen und Annäherung anbieten. Erst wenn der Nutzer die
Annäherung akzeptiert, weiter. MCP-Tools nicht verfügbar → sauberer Abbruch mit
Verbindungshinweis (HTTP-URL + Bearer-Token, siehe Server-README).

### Phase 2 — Spec-Interview
Fragen (eine nach der anderen, mit sinnvollen Ingenieurs-Defaults als Vorschlag),
**bis alle relevanten Angaben zu 100 % vorliegen**: Funktion & Einbausituation,
Schraubengrößen/Lochbilder, kritische Maße, Passungen/Spiel, Wandstärken,
Druckrichtung/Orientierung. „Vollständig" ist operational definiert: jedes Feld,
das Spec-JSON **und** Annahmenliste benötigen, hat einen Wert; ein vom Nutzer
bestätigter Default zählt als vorhanden. Ergebnis:
1. eine messbare **Spec** (JSON gemäß `spec://schema`: bounding_box, holes,
   min_wall_thickness_mm, max_overhang_deg, Volumen-Fenster, watertight/manifold),
2. eine explizite **Annahmenliste**.
Beides wird dem Nutzer zur Bestätigung vorgelegt, **bevor** Code entsteht.

### Phase 3 — Räumlicher Bauplan
`references/spatial-reasoning.md` lesen. Dann, vor jeder Zeile Code:
- **Koordinatensystem deklarieren** (Konvention: Z = Druckrichtung, Ursprung benannt).
- **Zerlegungstabelle:** je Feature eine Zeile — Primitiv/Helfer, Maße,
  Mittelpunkt-Position (ausgerechnet, da alle Primitive im Ursprung zentriert sind),
  Operation (add/cut).
- **Analytische Vorhersage:** erwartete Bounding-Box, Volumen-Budget
  (Summe Adds − Cuts ± Überlappungskorrekturen, als Intervall) und ein
  **Konnektivitäts-Argument**: jeder hinzugefügte Körper überlappt die bisherige
  Vereinigung nachweislich flächig, nicht nur tangential.

### Phase 4 — Code
cadkit-Primitive bevorzugen; rohes build123d nur wenn nötig. Benötigte Helfer aus
`references/helpers.py` unverändert inline einfügen. Mess-Sonden (`print` von
berechneten Kontrollwerten) einbauen — sie kommen im `logs`-Feld zurück.
Ergebnis MUSS in `result` liegen.

### Phase 5 — Render & Verify (zweistufiges Gate)
1. `render_model` aufrufen. **Zuerst** Metriken gegen die eigene Vorhersage prüfen:
   BBox innerhalb Toleranz, Volumen im Budget-Intervall, watertight/manifold.
   Abweichung ⇒ Denkfehler ⇒ **nicht** zur Spec-Prüfung weitergehen, sondern
   Ursache klären (Isolations-Renders, Sonden).
2. Erst bei Übereinstimmung: `check_model` mit der Spec aus Phase 2.

### Phase 6 — Diagnose-Iteration & Abnahme
Bei Fail: `references/troubleshooting.md` lesen, Hypothese benennen, minimal
patchen (Regeln siehe §7). Bei Pass: Job-ID + Dashboard-Link zur **Sichtprüfung**
an den Nutzer, dazu Zusammenfassung (finale Maße, Annahmen, Spec-Ergebnis).
Nutzer-OK = fertig. Optional anbieten, das Teil als Regressions-Benchmark-Fall
für den Server zu dokumentieren (Code + Spec + expected_status).

### Grenzen der deterministischen Abnahme (explizit)
`check_model` matcht Löcher nur über **Durchmesser + Achse + Durchgängigkeit** —
`HoleSpec` hat kein Positionsfeld. Lochpositionen und Lochbild-Geometrie
(Abstände, Symmetrie) sind serverseitig **unverifiziert**, obwohl sie der
wahrscheinlichste Fehler eines blind arbeitenden Modells sind. Zusätzlich meldet
die Locherkennung *alle* Zylinderflächen, auch Außenflächen (z. B. den Mantel
einer Buchse) — ein Hole-Check kann daran fälschlich matchen. Der Skill
kompensiert:
- **Lochvolumina sind Pflichtposten im Volumen-Budget** (Phase 3) — fängt
  fehlende/zu viele Bohrungen, aber nicht falsche Positionen;
- **Lochbild-Probe:** Isolations-Render nur der Cutter (Vereinigung der
  Bohrzylinder); deren Bounding-Box verifiziert Abstände und Ausdehnung des
  Musters analytisch (Beispiel: 2×2-Raster, spacing 40×20, ø 4,5 →
  BBox 44,5 × 24,5 × L);
- die **Phase-6-Zusammenfassung kennzeichnet je Spec-Punkt**, ob er
  *servergeprüft* oder *nur sichtgeprüft* ist — Lochpositionen sind immer
  „sichtgeprüft" und damit Teil der menschlichen Abnahme im Dashboard.

## 6. Referenzdateien

### 6.1 `spatial-reasoning.md` — die Denk-Methode
- **Zentrierungs-Disziplin:** alle Primitive im Ursprung zentriert; Standard-Formeln
  („Boden auf z=0" → `Pos(0, 0, h/2)`; Stapeln → `Pos(0, 0, h1 + h2/2)`; Anbau an
  Kante/Fläche mit Überlappung).
- **Schnitt-Regeln:** Cutter länger als das Material (2×-Regel); garantierte
  Durchgänge mit `through_hole`; `Rot` arbeitet in Grad, erst rotieren, dann
  positionieren (`Pos(...) * Rot(...) * shape`).
- **Emulations-Tricks:** Schnittmenge `a & b` = `a - (a - b)`; Sechskant-Prisma aus
  3 um 0°/60°/120° rotierten Boxen (Schnittmenge); Dreiecks-Rippe aus rotierter Box
  + Schnittmengen-Trick.
- **Volumen-Budget-Methode:** jedes Feature mit Volumenformel; Überlappungen
  abziehen; Ergebnis als Intervall. Toleranzregel konkret: Die STL-Tesselation
  beschreibt Zylinderflächen mit einbeschriebenen Facetten — Zylinder-Volumen im
  Mesh liegt systematisch **unter** πr²h; bei geschnittenen Löchern liegt das
  Teilvolumen entsprechend leicht **über** der analytischen Vorhersage. Der
  Export nutzt build123d-Defaults (lineare Toleranz ~10⁻³ mm), die erwartete
  Abweichung ist damit deutlich unter 1 %; der konkrete Zahlenwert wird bei der
  Helfer-Validierung (§9) **gemessen** und dann hier festgeschrieben.
- **2–3 vollständig durchgerechnete Beispiele** (u. a. Wandhalter: jede Position,
  jede Zwischensumme, Vorhersagetabelle → tatsächliche Metriken).

### 6.2 `helpers.py` — geprüfte Hilfsfunktionen
Design-Regeln: nur erlaubte API; explizite Maß-Parameter (keine
Bounding-Box-Introspektion); jede Funktion pur (Part rein → Part raus bzw. Maße
rein → Part raus); Docstring enthält Volumenformel fürs Budget; jede Funktion ist
gegen den laufenden Server validiert (siehe §9). Platzierungsparameter spiegeln
die cadkit-Konvention (`at=(x, y)` planar bzw. `at=(x, y, z)` mit `axis`), damit
keine zweite Konvention neben den Primitiven entsteht. Keine Duplikate zu
vorhandenen Primitiven: Senkungen macht `counterbore_hole`, Lochraster
`pattern_holes` — Helfer füllen nur echte Lücken.

| Funktion | Zweck |
|---|---|
| `bushing(outer_d, inner_d, h)` | Hülse / Distanzstück |
| `l_bracket(width, leg_a, leg_b, t)` | L-Winkel mit korrekter Ecküberlappung |
| `u_channel(w, d, h, wall)` | U-Profil |
| `enclosure_shell(w, d, h, wall, open_top=True)` | Gehäuseschale |
| `slot_cut(part, width, length, at, axis="Z")` | Langloch (Box + 2 Zylinder) |
| `hex_prism(across_flats, h)` | Sechskant-Prisma (3-Boxen-Schnittmenge) |
| `nut_pocket(part, size, at, depth)` | Muttern-Tasche (nutzt M-Tabelle) |
| `gusset(size, t)` | Dreiecks-Rippe zur Versteifung |
| `grid_positions(nx, ny, sx, sy)` | Rasterkoordinaten für eigene Muster |
| `bottom_at_zero(h)` u. ä. Platzierungs-Kurzformeln | geben `Pos` zurück |

Die endgültige Signaturen-Liste darf bei der Implementierung angepasst werden
(z. B. wenn der Static-Check des Servers eine Konstruktion ablehnt); Streichungen
oder Ergänzungen werden im Plan dokumentiert.

### 6.3 `recipes.md` — Archetypen & Engineering-Tabellen
Archetypen: Wandhalter, Montageplatte, Distanzstück, Kabelclip, Gehäuse,
Flansch-Adapter. Je Rezept: Parametertabelle, Bauplan-Skizze (Zerlegungstabelle),
Default-Spec, typische Annahmen.

Engineering-Tabellen:
- **Schrauben-Durchgangslöcher** M2,5–M8 (Nennmaß → Durchgangsloch mittel,
  Senkungs-Ø/-Tiefe für Zylinderkopf DIN 912, Sechskant-Schlüsselweiten für
  `nut_pocket`). Die DIN-912-Werte sind direkt als Parameter für das vorhandene
  cadkit-Primitiv `counterbore_hole` formuliert — Senkungen werden **nicht**
  manuell aus Zylindern nachgebaut.
- **FDM-Defaults:** Wand ≥ 1,2 mm (0,4er-Düse), Überhang ≤ 45°, horizontale
  Bohrungen +0,2–0,4 mm Zuschlag, Spielpassung 0,2 mm (eng) / 0,4 mm (locker).

### 6.4 `troubleshooting.md` — Diagnose-Tabellen
1. **Server-Fehlertyp → Ursache → Fix** für alle 7 Typen (`static_check_failed`,
   `syntax_error`, `runtime_error`, `empty_geometry`, `export_failed`, `timeout`,
   `resource_limit`), z. B. `empty_geometry` → Cut hat alles entfernt oder `result`
   nicht gesetzt; `timeout`/`resource_limit` → Boolean-Anzahl reduzieren.
2. **Fehlgeschlagener Check → wahrscheinlichste Denkfehler**, z. B. Volumen zu
   niedrig → Körper überlappen nicht / Cutter zu groß; BBox-Z doppelt so groß wie
   erwartet → Zentrierung vergessen; Loch-Check fail → falsche Achse oder Material
   blockiert den Durchgang; Loch-Check pass trotz fehlendem Loch → Match auf einer
   zylindrischen **Außenfläche** (Locherkennung filtert alle Zylinderflächen);
   not watertight → sich berührende, aber nicht überlappende Körper.

Beide Tabellen werden **aus der Baseline abgeleitet** (§9, RED-Phase): Die dort
wörtlich dokumentierten Fehlermuster sind die Primärquelle; die obigen Beispiele
sind Startpunkte und werden ersetzt oder bestätigt.

## 7. Iterationssteuerung (Regeln in SKILL.md)

- **Vorhersage-Gate:** Abweichung Metrik ↔ Vorhersage wird geklärt, bevor
  `check_model` läuft (Isolations-Renders einzelner Features, Sonden in Logs).
- **Hypothese vor Patch:** jede Iteration benennt die vermutete Ursache aus der
  Diagnose-Tabelle; dann minimaler Patch. Kein Neuschreiben aus Frust.
- **Budget:** nach 3 Fehlversuchen am selben Check → zurück zu Phase 3, Zerlegung
  neu planen.
- **Oszillations-Bremse:** macht ein Fix einen früheren Fix rückgängig → Stopp,
  Neuplanung statt Ping-Pong.

## 8. Fehlerbehandlung

Im Skill lebt davon nur der Verbindungs-Abbruch in der `SKILL.md`; der Rest
wandert nach `troubleshooting.md` (Wortbudget, siehe §4).

- MCP-Server nicht verbunden → Abbruch mit Anleitung (Server-URL `http://<host>:8000/mcp`,
  `Authorization: Bearer <token>`, siehe stl-mcp-server-README).
- `timeout`/`resource_limit` → Komplexität reduzieren (weniger Booleans,
  `pattern_holes` statt N einzelner `through_hole`-Aufrufe).
- Widersprüchliche Nutzerangaben im Spec-Interview → benennen und auflösen,
  bevor die Spec finalisiert wird.

## 9. Validierung / Definition of Done

**RED — Baseline zuerst (gemäß writing-skills: kein Skill ohne beobachtetes
Scheitern):**

0. Die 3 End-to-End-Beispielteile (Wandhalter mit Schraubbild, Buchse,
   Gehäuseschale) werden **zuerst in frischen Sessions ohne Skill** gebaut
   (nur MCP-Server + Aufgabenstellung). Die tatsächlichen Fehlermuster werden
   **wörtlich dokumentiert** (Fehlertypen, gescheiterte Checks, Denk- und
   Platzierungsfehler, Rationalisierungen). `troubleshooting.md` (§6.4) und die
   Iterationsregeln (§7) werden aus diesen Mustern abgeleitet statt aus
   Hypothesen. Nebeneffekt: belastbarer Vorher/Nachher-Nachweis für die Abnahme.

**GREEN — mit Skill:**

1. **Helfer-Validierung:** jede Funktion in `helpers.py` wird gegen den laufenden
   Server render-getestet: Status `ok`, watertight, Volumen im per Docstring-Formel
   vorhergesagten Budget. Dabei wird die tatsächliche Tesselation-Abweichung
   gemessen und in `spatial-reasoning.md` festgeschrieben (§6.1).
2. **End-to-End:** dieselben 3 Beispielteile durchlaufen mit Skill den kompletten
   Workflow und bestehen ihre Spec via `render_model` → `check_model` —
   nachweislich besser als die Baseline (weniger Iterationen, keine
   Wiederholung der Baseline-Fehlermuster).
3. **Benchmark-tauglich:** die validierten Beispiele sind als `(code, spec,
   expected_status)` dokumentiert, sodass sie 1:1 ins Regressions-Benchmark des
   Servers übernommen werden können (Nebenprodukt, kein Muss).
4. Skill-Qualität gemäß `superpowers:writing-skills` (Frontmatter, Trigger,
   Struktur, Wortbudget) — der Skill wird vor Abnahme in einer frischen Session
   ausprobiert.

## 10. Spätere Ausbaustufen (außerhalb dieses Projekts)

- Promotion bewährter Helfer zu cadkit-Primitiven im Server (eigener
  Spec→Plan→Umsetzungs-Zyklus im stl-mcp-server).
- Vision-/Snapshot-Plausibilität (ursprüngliches Teilprojekt 2), falls der Server
  später Rendering anbietet.
- Systematischer Benchmark-Ausbau (Workflow + Eval-Fokus).
