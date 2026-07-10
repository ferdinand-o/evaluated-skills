# cad-parts — Validierung (Messwerte & GREEN)

Server-Alias: stl-cad-server-http. Datum: 2026-07-10.

## Tesselation-Kalibrierung

Drei Kalibrier-Renders gegen den Live-Server (`stl-cad-server-http`), Formeln aus dem Task-3-Brief.

| Form | V_analytisch (mm³) | V_gemessen (mm³) | Abweichung (%) | Vorzeichen |
|---|---|---|---|---|
| Box 20×20×20 (Kontrolle) | 8000,000000 | 8000,0 | 0,000 % | keine (exakte Übereinstimmung) |
| Zylinder r=5, h=20 (konvex) | 1570,796327 | 1570,145393886328 | −0,0414 % | negativ — gemessen **unter** analytisch (wie erwartet) |
| Platte 40×40×3, Ø4,5-Durchgangsloch (Z) | 4752,287061573605 | 4752,306833253323 | +0,000416 % | positiv — gemessen **über** analytisch (wie erwartet) |

Berechnung:
- Box: `(8000,000000 − 8000,0) / 8000,000000 × 100 = 0,000 %` — innerhalb ±0,01 % Toleranz, bestätigt den Kontrollfall.
- Zylinder: `delta_cyl = (1570,796327 − 1570,145393886328) / 1570,796327 × 100 = 0,0414 %` (gemessen liegt 0,0414 % unter πr²h — Polygon-Approximation des Kreisquerschnitts unterschätzt die Fläche, konsistent mit der leicht abweichenden bbox `[10,0 / 9,996891975402832 / 20,0]`).
- Loch: `delta_hole = (4752,306833253323 − 4752,287061573605) / 4752,287061573605 × 100 = 0,000416 %` (gemessen liegt 0,000416 % über dem analytischen Wert — Tesselation des Lochrands entfernt geringfügig weniger Material als der ideale Zylinderabzug).

**Abgeleitete Budget-Regel:** Zylindervolumen im Mesh liegt 0,0414 % unter πr²h; Budget-Intervalle für Teile mit Zylinderflächen: ±max(2·0,0414, 0,5) % = ±0,5 %. Für geschnittene Löcher (Abweichung 0,000416 % über analytisch) reicht dasselbe ±0,5 %-Budget mit deutlicher Marge.

## Helfer-Validierung

Task 4 (Platzierung & Grundkörper), Renders A–D gegen `stl-cad-server-http`, Helferquelle jeweils inline aus `skills/cad-parts/references/helpers.py` kopiert. Keine Korrektur an den Helfern nötig — alle vier Renders lagen beim ersten Versuch innerhalb der Budget-Toleranz aus der Tesselation-Kalibrierung (±0,5 % für Zylinderflächen, ±0,1 % für Polyeder).

| Funktion | V_analytisch (mm³) | V_gemessen (mm³) | Abweichung (%) | bbox (mm) | watertight |
|---|---|---|---|---|---|
| bottom_at_zero (Render A, stack = b1+b2) | 4600 | 4600,0 | 0,000 % | (20, 20, 16) | true |
| on_top_of (Render A, stack = b1+b2) | 4600 | 4600,0 | 0,000 % | (20, 20, 16) | true |
| grid_positions (Render B, holes_plate) | 9345,5 | 9345,636420211435 | +0,00146 % | (60, 40, 4) | true |
| bushing (Render C) | 848,2300164692441 | 847,8785144489898 | −0,04144 % | (12; 11,996270179748535; 10) | true |
| l_bracket (Render D) | 23040 | 23040,0 | 0,000 % | (60, 40, 60) | true |
| u_channel (Render E) | 9600 | 9600,0 | 0,000 % | (30, 50, 20) | true |
| enclosure_shell open_top=True (Render F) | 10312,5 | 10312,5 | 0,000 % | (50, 30, 20) | true |
| enclosure_shell open_top=False (Render G) | 13125 | 13125,0 | 0,000 % | (50, 30, 20) | true |
| slot_cut (Render H) | 3651,82523 | 3651,8659158606515 | +0,00111 % | (40, 20, 5) | true |
| hex_prism (Render I) | 277,128129 | 277,12812423706055 | −0,0000019 % | (8; 9,237604141235352; 5) | true |
| nut_pocket (Render J) | 2252,3057 | 2252,318420686445 | +0,000565 % | (20, 20, 6) | true |
| gusset (Render K) | 800 | 800,0 | 0,000 % | (4, 20, 20) | true |

Anmerkungen:
- Render A/B waren im Brief als zwei separate Renders vorgesehen (statt des kombinierten `result`), um Stack- und Platten-BBox getrennt prüfbar zu machen; `grid_positions`-Log bestätigte `[(-20.0, -10.0), (-20.0, 10.0), (20.0, -10.0), (20.0, 10.0)]`.
- bushing-Abweichung (−0,04144 %) deckt sich mit der Zylinder-Kalibrierung aus Task 3 (−0,0414 %) — reine Tesselationsabweichung, keine Logikfehler.
- l_bracket und die Stack-Boxen sind reine Polyeder (Box-Ecken), daher exakte Übereinstimmung mit der analytischen Formel.
- Renders E–G (`u_channel`, `enclosure_shell`) sind ebenfalls reine Polyeder-Boolesche (Box minus Box), daher exakte Übereinstimmung (0,000 %) ohne Korrekturbedarf am ersten Versuch.
- Render G (`enclosure_shell(..., open_top=False)`) beweist verschachtelte Schalen: äußere Box minus vollständig innenliegende Kavität-Box liefert `is_watertight: true` und `is_manifold: true` (Server-Metriken) — die geschlossene Hülle ist ein sauberes, wasserdichtes Mesh trotz komplett eingeschlossener Kavität.
- Task 6 (Schnitt-Features & Emulations-Tricks), Renders H–K gegen `stl-cad-server-http`. Keine Korrektur an den Helfern nötig — alle vier Renders lagen beim ersten Versuch innerhalb der Budget-Toleranz (±1 % für den Langloch-Schnitt mit Zylinder-Enden, ±0,1 % für die reinen Hex-/Polyeder-Booleschen).
- Render H (`slot_cut`) bestätigt die stadium-förmige Cutter-Emulation (Box + 2 Zylinder) bei voller Durchdringung entlang Z.
- Render I (`hex_prism`) bestätigt die Intersection-Emulation `a & b == a - (a - b)` über drei 0/60/120°-rotierte Slabs; gemessene bbox-Y (9,237604) trifft `2*8/sqrt(3) = 9,237604307` praktisch exakt.
- Render J (`nut_pocket`) baut direkt auf `hex_prism` und `NUT_AF["M4"] = 7,0` auf; Cutter-Zentrierung bei `at=(0,0,3)` mit `2*depth`-Höhe durchdringt die Platte exakt `depth=3,2` tief.
- Render K (`gusset`) bestätigt die 45°-Hypotenusen-Schnittebene (`y + z = size`); reines Polyeder-Boolesches, daher exakte Übereinstimmung (0,000 %).
- Task 7 (`references/spatial-reasoning.md`), Worked Example (Wall Bracket, l_bracket-Muster + 4 through_hole d4,5) gegen `stl-cad-server-http` verifiziert: V_pred 22785,5, V_gemessen 22785,636418532406 mm³ (+0,0006 %, innerhalb Budget-Intervall [22400, 23100]), bbox (60, 40, 60) exakt wie prognostiziert, watertight true, manifold true — Datei musste nicht korrigiert werden (erster Versuch GREEN).

## Fehlertaxonomie-Trigger
(ausfüllen in Task 9)

## GREEN-E2E (mit Skill)
(ausfüllen in Task 11)

## Benchmark-Fälle (code, spec, expected_status)
(ausfüllen in Task 11)
