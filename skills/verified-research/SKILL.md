---
name: verified-research
description: Use for research where source provenance must survive scrutiny — regulatory, financial, scientific, or technical claims that need a Tier-1/2 primary source, not the first search hit. Consults a curated source registry before free search, tags every claim with its trust tier, spot-checks a sample of claims against their sources, and keeps a per-topic knowledge file so a follow-up run only researches the delta. Not for open-ended exploratory research without a provenance requirement (use deep-research, globally installed — same process skeleton, but no registry, no tiers, no memory across runs) and not for summarizing an existing document or chat (use visual-summary). Triggers include "recherchiere mit Quellenregister", "verifizierte Recherche", "Tier-Bewertung der Quellen", "Primärquelle prüfen", "Delta-Recherche zu X".
---

# verified-research — Register vor Suche, Tier vor Claim, Delta vor Wiederholung

Fork/Adaption von [samber/cc-skills](https://github.com/samber/cc-skills), Skill `deep-research`
(MIT-Lizenz): Prozessgerüst, Recherche-Typen (`references/research-types.md`),
Konfidenz-Tracking und Prose-first-Doktrin bleiben. Neu: Quellenregister, Tiers,
Truth-Bewertung, Verifikations-Pass und Delta-Modus.

Die beste bestehende Recherche-Skill überlässt die Quellen*wahl* dem
Suchmaschinen-Ranking. Diese Skill nicht: Sie fragt zuerst ein kuratiertes Register,
bevor sie frei sucht, und sie hält fest, wie viel eine Quelle wert ist — nicht nur, was
sie sagt.

## Ablauf

1. **Scope.** Nur bei vagen Aufträgen nachfragen (eine Frage, nicht drei).
2. **Register-Phase — zuerst und verpflichtend.** `python "${CLAUDE_SKILL_DIR}/scripts/registry.py" lookup <adresse>`
   für jede in Frage kommende Domäne/Quelle, *bevor* frei gesucht wird. Ein Treffer
   liefert Tier und `notiz` direkt; in der Antwort an den Nutzer (der Prosa-Bericht,
   nicht die Wissensdatei — die hat ihr eigenes Schema, `references/delta-mode.md`)
   wird er als `(laut Register: <name>)` zitiert — das ist der Beleg, dass diese Phase
   wirklich stattfand.
3. **Freie Suche** ergänzt, wo das Register nichts liefert. Jeder Treffer wird getiert:
   Registertreffer übernehmen ihr Tier, alles andere ist Tier 3, bis bewertet.
4. **Unbekannte Quelle bewerten.** Nach `references/rating-rubric.md` einordnen, dann
   `python "${CLAUDE_SKILL_DIR}/scripts/registry.py" add --domain … --pattern … --name … --tier … --notiz …`
   eintragen. Einmal bewerten, nicht bei jedem Lauf neu.
5. **Synthese mit Tier-Tag pro Claim.** Format, Zeile für Zeile:
   `- <Aussage>. [Tier <1-3>{, kritisch}?, Quelle: <adresse>]`
   Beispiel: `- Die Konfigurationsdatei heißt config.toml. [Tier 1, Quelle: docs.example/config]`
6. **Verifikations-Pass.** `python "${CLAUDE_SKILL_DIR}/scripts/spotcheck.py" --report <pfad>` auf dem fertigen
   Bericht laufen lassen. Für jeden Claim der Stichprobe: Quelle öffnen, prüfen, ob der
   Wert dort im selben Kontext steht. Abweichung → Tag durch `[VERWORFEN nach Spotcheck,
   Quelle: <adresse>]` ersetzen, nie still stehen lassen.
7. **Wissensdatei aktualisieren.** Nach `references/delta-mode.md`. Jeder Lauf endet
   damit — Recherche ohne Gedächtnis-Update ist unvollständig.

## Contract

- **Register vor Suche.** Keine freie Suche für eine Domäne, die das Register schon
  kennt, ohne den Registereintrag erst nachzuschlagen.
- **Kritische Claims brauchen mindestens eine Tier-1/2-Quelle.** Ist nur Tier 3
  auffindbar, steht das wörtlich im Bericht: **„Nur Sekundärquellen gefunden."** Kein
  Claim wird stillschweigend hochgestuft, weil eine bessere Quelle bequemer wäre.
- **Aggregator-Zitate werden zur Primärquelle zurückverfolgt.** Wer zitiert, ist nicht
  die Quelle — der Bericht nennt die Primärquelle, nicht den Aggregator, der sie
  zusammenfasst.
- **Jeder Claim trägt sein Tier-Tag**, auch unkritische. Ein Claim ohne Tag gehört
  nicht in den Bericht.
- **Neue Registereinträge tragen eine begründete `notiz`** (Primär-/Sekundärstatus,
  redaktionelle Standards, Anreizlage, Track Record oder Aktualität benannt) —
  `registry.py add` erzwingt das mechanisch.
- **Delta-Modus ist Pflicht, kein Bonus.** Existiert eine Wissensdatei zum Thema, liest
  der Lauf sie zuerst und recherchiert nur die Differenz; der Bericht trennt `## Bekannt`
  von `## Neu`. Ohne Neuigkeiten bleibt der Lauf kurz — das ist der Erfolgsfall, keine
  Enttäuschung.
- **Wissensdatei-Ort:** `.skills/verified-research/` projektlokal, falls es das
  Verzeichnis im Projekt schon gibt — sonst `~/.skills/verified-research/`. Erster Lauf
  kündigt die Anlage an (Pfad nennen). Ab 30 Themen-Dateien warnt `registry.py topics`,
  gliedert aber nicht automatisch um (`references/delta-mode.md`).

## Anti-Rationalisierung

| Gedanke | Realität |
| --- | --- |
| „Der Blog fasst das Paper gut zusammen" | Paper öffnen. Der Blog ist Tier 3, das Paper Tier 1. |
| „Steht in drei Artikeln, also stimmt es" | Drei Abschriften derselben Pressemitteilung sind eine Quelle. |
| „Die Quelle kenne ich nicht, wirkt aber seriös" | Rubrik anwenden, eintragen, dann verwenden — „wirkt seriös" ist keine `notiz`. |
| „Delta sparen wir uns, ich recherchiere frisch" | Frisch heißt: bezahlt dasselbe zweimal und verliert den Vergleich zum letzten Stand. |
| „Register überspringen, ich kenne die Primärquelle eh" | Registerpflicht gilt unabhängig vom eigenen Vorwissen — sonst wird dieser Schritt beim nächsten Thema lautlos ausgelassen. |

## Abgrenzung

- **deep-research** (global installiert) — gleiches Prozessgerüst, aber kein Register,
  keine Tiers, kein Gedächtnis über frühere Läufe. Wenn Quellenqualität und
  Nachvollziehbarkeit zählen, diese Skill statt deep-research.
- **visual-summary** — fasst vorhandene Dokumente/Chats zusammen, recherchiert nicht.
- Ohne belastbare Quellen (reines Brainstorming, Meinungsfrage) ist diese Skill zu
  schwer — dann reicht ein normales Gespräch.
