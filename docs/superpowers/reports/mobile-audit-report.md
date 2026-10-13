<!-- skill: skill-forge | schema: 1 | generated: von Hand nach skills/skill-forge/assets/skill-template/report.md -->
# mobile-audit — Abschlussbericht

Gebaut nach `specs/Spec 15 – mobile-audit.md` am 2026-08-20/21 (Commits 15edc88 bis
403ae42). Dieser Bericht ist am 2026-10-12 nachgetragen, als der Lint-Registertest die
fehlende Datei meldete. Er stützt sich auf Spec 15, die Docstrings und die
Commit-Nachrichten; was dort nicht steht, ist nicht überliefert und steht hier nicht.

## Was entstanden ist

- `skills/mobile-audit/SKILL.md` mit dem Findings-Contract: jeder Befund mit Fundstelle,
  Messwert gegen Grenzwert und Rezept, markiert als gemessen, modelliert, begutachtet
  oder ungeprüft.
- Stufe 1, `scripts/audit_static.py`: vier Quelltext-Checks (`100vh`, Schriftgröße von
  Eingabefeldern, Zoom-Sperre, Hover ohne Touch-Pfad), läuft immer.
- Stufe 2, `scripts/audit_devices.py`: Overflow, Hit-Areas, Safe-Areas und die
  modellierte Tastatur über drei Geräteprofile; Bewertung (`evaluate`) und
  Browser-Ansteuerung (`run_matrix`) getrennt.
- `references/fixes.md` (ein Rezept je Befund), `references/device-matrix.md`
  (Begründung je Profil), `assets/audit-config.json`.
- `references/mobile.md` in enterprise-ui, ui-architect und motion-landing, mit
  Drift-Test über die drei Kopien.
- Sechs Evals mit fünf Fixtures, alle `contract`, alle auf Stufe 1.

## Was gemessen wurde

- **Keyboard-Spike** mit Playwright und Chromium: Die Emulation der Tastatur verschiebt
  eine fixierte Leiste mit (barTop 794 → 450), eine kaputte Seite sähe heil aus. Daraus
  wurde das Modell mit K Pixeln; verifiziert mit einem Treffer im Defektfall
  (`button#submit`, Unterkante 830 > 508) und keinem im Gegenfall.
- **e2e-Tests** mit echtem Chromium fanden einen Defekt, den die Unit-Tests nicht sehen
  konnten: Im mobilen Modus dehnt Chromium `window.innerWidth` auf die Inhaltsbreite,
  der Overflow-Check war dort blind. Gemessen wird seither gegen `visualViewport`.
- **Erster Eval-Lauf: 5 von 6.** Der sechste fiel am Eval, nicht an der Skill: Er
  setzte voraus, dass kein Interpreter mit Playwright da ist, der Agent fand aber einen
  und fuhr die Matrix. Ersetzt durch die Invariante, dass der Stufe-1-Bericht
  `stage_2` immer als „ungeprüft" führt.
- **Anker-Test:** Vier der acht Rezept-Verweise aus Stufe 2 zeigten auf fehlende
  Abschnitte in `fixes.md`. Die Rezepte sind geschrieben, ein Test hält jeden Anker,
  jedes Rezept und jeden `FIX_HINT`-Schlüssel fest.
- **Nachtrag 2026-10-12:** Lint-Befunde behoben (Description in Anführungszeichen ohne
  Prozessverb, Anti-Zeremonie-Eval am Präfix erkennbar, Routing in Spec 00), known-limits
  nachgetragen. `lint_skill.py skills/mobile-audit` ohne Befund.

## Was nicht gemessen wurde

- **Stufe 2 in einem Eval.** Die Evals laufen ohne Browser; die Geräte-Matrix prüfen nur
  Unit- und e2e-Tests.
- **Hover-Menüs per JavaScript** und Bedienelemente aus `div` ohne `role` — beide
  unerkannt (known-limits).
- **Scrollen bei Fokus** — das Tastatur-Modell prüft es nicht.
- **Läufe ohne Skill** (`--without-skill`) sind nicht überliefert.
- **Ob die Familien-Skills mobile-audit am Ende tatsächlich aufrufen**, misst kein Eval.

## Offen für die nächste Runde

- Ein Eval, der Stufe 2 dort misst, wo Playwright verlässlich da ist.
- Läufe ohne Skill für die sechs Evals.
