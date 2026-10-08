---
name: dev-report
description: Use when writing a development status report, weekly update, feature or PR wrap-up, or release notes from a git repository — collects facts from local git first, then renders them into an audience-appropriate draft. Triggers include "Wochenreport", "Statusreport", "Release Notes", "was habe ich diese Woche gemacht", "Bericht für den Chef", "Feature-Abschluss". Not for ad-hoc summaries of documents or chats (use visual-summary) and not for session handover (use handoff).
---

# dev-report — Fakten-first Entwicklungs-Reports

**Sammeln ist ein Skript, Schreiben ist ein Rendering.** Du schreibst nichts in
den Report, was nicht in `facts.json` steht oder ausdrücklich als Einschätzung
markiert ist.

## Die eiserne Regel

```
KEIN SATZ ÜBER DAS PROJEKT, BEVOR collect.py GELAUFEN IST.
```

Dein Gedächtnis ist keine Quelle. Auch wenn du die Woche miterlebt hast: Der
Report rendert `facts.json`, nicht deine Erinnerung.

## Ablauf

1. **Modus wählen** — `weekly` (Wochen-/Statusreport), `feature`
   (Feature-/PR-Abschluss), `release` (Release Notes).
2. **Zielgruppe klären**, falls der Nutzer sie nicht nennt. Eine Frage, nicht drei:
   „Für dich, fürs Team, oder für Vorgesetzte?"
3. **Sammeln:**
   ```bash
   python skills/dev-report/scripts/collect.py --mode weekly --since 2026-08-01
   python skills/dev-report/scripts/collect.py --mode feature --branch feature/x
   python skills/dev-report/scripts/collect.py --mode release --range v1.2..HEAD
   ```
   Das Skript schreibt `.skills/cache/facts.json` und nennt den Zielpfad des
   Reports. Meldet es übersprungene Quellen, erwähne das im Report — eine
   ausgelassene Faktenquelle ist eine Einschränkung, keine Nebensache.
4. **Rendern:** Template aus `assets/` nach Modus, Ton nach `references/audience-guide.md`.
5. **Ablegen** unter dem Pfad, den `facts.json` als `report_path` nennt.
6. **Übergeben** — der Report ist ein Entwurf zur Freigabe. Du versendest nichts.

## Contract

- Jede faktische Aussage trägt eine Referenz auf einen `facts.json`-Eintrag:
  Commit-Hash, Tag, oder Artefaktpfad.
- Ein Satz ohne solche Referenz beginnt mit `Einschätzung:` — inline, am Satz
  selbst, im Kontext der Aussage. Das ist die einzige zulässige Form: keine
  eigene Sektion für unbelegte Aussagen, das trennt die Behauptung von ihrem
  Zusammenhang. Ohne die Markierung gehört der Satz nicht in den Report.
- Meldet `collect.py` null Commits, wird kein Report geschrieben. Frag beim
  Nutzer nach — der angegebene Bereich ist dann vermutlich falsch oder für
  git unlesbar, nicht wirklich leer.
- `facts.json` meldet `patterns.quiet` — dann nennt der Report die Ruhe beim
  Namen („3 Commits, Fokus lag auf X") und wird kurz.
- Revert-Ketten und Fix-auf-Fix aus `patterns` erscheinen im Report. Für
  Vorgesetzte abstrahiert als Risiko oder Erkenntnis, nie weggelassen.
- Sind `patterns.reverts` und `patterns.fix_chains` beide leer, gehört keine
  Aussage über Zähigkeit in den Report — dann heißt es „Keine.", wie im
  Template. Ist nur `patterns.fix_chains` leer, bleibt es bei den
  Revert-Einträgen aus der Zeile oben. Hat `patterns.fix_chains` genau einen
  Eintrag, war es eine Stelle, nicht mehrere — sprich nicht von
  „verschiedenen Stellen". Sonst gilt: mehr Einträge in `patterns.fix_chains`
  als der Wert in `patterns.fix_commits` heißt breiter Fix mit Nachzieher —
  schreib das als ein Satz, nie als Aufzählung. Andernfalls war es
  wiederholtes Ringen an verschiedenen Stellen.
- Kein Aufruf von `git` von Hand für Zahlen, die `collect.py` schon hat.

## Anti-Rationalisierung

| Gedanke | Realität |
| --- | --- |
| „Ich erinnere mich, was diese Woche war" | Erinnerung ist keine Quelle. `collect.py` zuerst. |
| „Die Zahl macht es überzeugender" | Zahlen ohne `facts.json`-Referenz fliegen raus. |
| „Für den Chef schönreden" | Risiken zu benennen ist der Wert des Reports. Revert-Ketten erscheinen als Lessons Learned, nicht gar nicht. |
| „Drei Commits sind zu wenig für einen Report" | Dann ist der Report drei Zeilen lang. Aufblähen ist der Hauptfehler dieser Skill. |
| „Die Quelle war unlesbar, lass ich weg" | Übersprungene Quellen werden genannt. Stille Auslassung ist die verbotene Variante. |
| „Ein Diagramm wertet es auf" | Der Report ist Text. Für gerenderte Zusammenfassungen gibt es visual-summary. |

## Abgrenzung

- **visual-summary** — ad-hoc „fass das zusammen", beliebige Inhalte, gestaltete Ausgabe.
- **handoff** — Sitzungszustand für die nächste Session, kein Bericht an Menschen.
- **human-prose** — „mach den Wochenreport menschlicher": Modus B über den Fließtext;
  Kopfzeilen und Marker des Reports bleiben.
- Diese Skill braucht ein Git-Repository. Ohne Repo sagst du das und hörst auf.
