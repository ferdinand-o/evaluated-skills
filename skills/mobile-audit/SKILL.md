---
name: mobile-audit
description: "Use when checking or repairing how an existing web page behaves on phones — \"funktioniert das auf dem Handy?\", \"mobile kaputt\", \"prüf das mal mobil\", \"Touch-Targets\", \"is this broken on mobile\", \"mobile audit\". Two stages: source-level checks that always apply (100vh, input font size, zoom lock, hover-only interaction) plus an optional device matrix for what only exists in layout (overflow, hit areas, safe areas). Every finding carries file/line or device/selector, a measured value against its threshold, and a fix recipe. Not for building or converting a view — \"responsive machen\", \"mobile Ansicht bauen\" belong to enterprise-ui, ui-architect or motion-landing, which call this skill at the end. Not for performance budgets (motion-landing) or React Native."
---

# mobile-audit — zwei Stufen, eine Wahrheit pro Stufe

**Was du nicht gemessen hast, hast du nicht geprüft.** Jede Stufe spricht nur für
sich: Stufe 1 sagt nichts über Layout, Stufe 2 nichts über Quelltext, und keine
sagt „grün" für die andere.

## Der Contract

```
KEIN BEFUND OHNE FUNDSTELLE. KEINE STUFE SPRICHT FÜR EINE ANDERE.
```

- Jeder Befund trägt **Fundstelle** (`datei:zeile` in Stufe 1, `gerät + selektor`
  in Stufe 2), **Messwert gegen Grenzwert** und ein **Fix-Rezept** aus
  `references/fixes.md`.
- Jeder Befund trägt seine Herkunft: `gemessen` (deterministisch), `begutachtet`
  (Screenshot-Sichtprüfung) oder `ungeprüft` (Stufe nicht gelaufen). Eine
  ausgelassene Stufe meldet nie Erfolg.
- **Grenzwerte stehen in `assets/audit-config.json`, nicht im Kopf.** Der
  Tap-Target-Boden ist 24×24 px (WCAG 2.2 AA, deckungsgleich mit enterprise-ui);
  44 px ist ein Hinweis für primäre Aktionen, kein Verstoß. Wer abweicht,
  überschreibt den Wert unter `.skills/mobile-audit/audit-config.json` — sichtbar,
  nicht stillschweigend.
- **G2, nicht G3** (Spec 00 §4): Die Skripte melden Verstöße, sie blockieren nichts.

## Ablauf

1. **Modus klären.** Selbst-Modus (eigene Views vor der Lieferung) oder Fremd-Modus
   (bestehende Seite). Im Selbst-Modus wird repariert, im Fremd-Modus berichtet.
2. **Stufe 1 — läuft immer.**
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/audit_static.py" --repo .
   ```
   Findet `100vh`, Eingabefelder unter 16 px, Zoom-Sperren im Viewport-Meta und
   Hover-Interaktionen ohne Touch-Pfad. Exit 1 heißt Befunde, nicht Fehler.
3. **Stufe 2 — wenn die Toolchain da ist.** Geräte-Matrix für horizontales Overflow,
   echte Hit-Areas und Safe-Areas. Fehlt Playwright, meldet die Stufe `ungeprüft`
   mit Werkzeugliste — und Stufe 1 gilt trotzdem.
4. **Screenshots begutachten**, falls Stufe 2 lief: Layout-Brüche, abgeschnittene
   Inhalte, unlesbare Dichte. Diese Befunde sind `begutachtet`, nie `gemessen`.
5. **Selbst-Modus: fixen und erneut prüfen.** Repariert wird nur in Dateien, die der
   laufende Auftrag ohnehin anfasst; fremde Views werden gemeldet, nicht angefasst.

## Anti-Rationalisierung

| Gedanke | Realität |
| --- | --- |
| „Sieht im schmalen Browserfenster gut aus" | Das Fenster emuliert weder Touch noch Tastatur noch Notch. |
| „Hover-Menü hat doch jeder" | Auf Touch existiert kein Hover. Touch-Pfad oder Befund. |
| „24 px sind bei uns halt 20" | Dann als Override in der Config, mit Begründung. |
| „Playwright fehlt, also kann ich nichts sagen" | Stufe 1 läuft immer. „Ungeprüft" gilt für Stufe 2, nicht fürs Audit. |
| „Das Audit mache ich am Ende einmal" | Nach jedem größeren Layout-Schritt. Mobile-Fehler sind früh billig. |
| „Der Check meldet nichts, also ist es sauber" | Nur für die vier Checks. Was Stufe 1 nicht sieht, steht in `docs/known-limits.md`. |

## Abgrenzung

- **enterprise-ui / ui-architect / motion-landing** bauen die Oberfläche und laden
  dafür `references/mobile.md`. „Responsive machen" gehört dorthin — diese Skill
  prüft, sie baut nicht.
- **motion-landing** deckt Performance-Budgets ab (LCP/CLS/INP). Hier geht es um
  Bedienbarkeit auf kleinen Touch-Geräten, nicht um Ladezeit.
