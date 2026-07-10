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
(ausfüllen in Tasks 4–6: Funktion, V_analytisch, V_gemessen, Abweichung %, bbox, watertight)

## Fehlertaxonomie-Trigger
(ausfüllen in Task 9)

## GREEN-E2E (mit Skill)
(ausfüllen in Task 11)

## Benchmark-Fälle (code, spec, expected_status)
(ausfüllen in Task 11)
