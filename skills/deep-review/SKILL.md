---
name: deep-review
description: Use when a large range, a branch or a plan checkpoint must be reviewed thoroughly and you need proof that every part was looked at — „großen Branch prüfen", „gründlich", „Prüfpunkt", „in Paketen", „wurde jedes Stück angeschaut", „Sicherheitsreview mit deep-review". A Tier-1 script cuts the range into packets, adds the contracts of the called code (definition, raise sites, ownership) to each packet, and audits that every packet has an accepted review result; the review itself is /code-review per packet. Not for a small diff or a path (use /code-review directly), not for a security audit of a whole system (use /security-review), not for gathering context and intended behaviour of a diff (use review-context).
---

# deep-review — `/code-review` in Paketen, mit den Verträgen der Gegenstellen

Große Bereiche verlieren in einem einzigen Review Funde. Diese Skill schneidet den Bereich in
Pakete, gibt jedem Reviewer die Gegenstellen der geänderten Aufrufe mit und weist je Paket
nach, dass ein Ergebnis angenommen wurde. Das Review selbst ist `/code-review`.

## Eiserne Regel

```
Kein Bericht nennt sich vollständig, solange ein Paket des Plans kein vom Skript
angenommenes Ergebnis hat — und kein Fund eines Pakets fehlt in findings.json.
```

Ohne `audit` gibt es keine Übergabe. Dass je Paket ein Review lief, verlangt diese Datei (G1).
Fehlende Pakete, verlorene Funde und einen Bericht, der nicht zu den Daten passt, meldet
`audit` (G2).

## Ablauf

Jeder Befehl nimmt `--repo` (Standard: aktueller Ordner). Die Skill legt
`.skills/cache/deep-review/` (Läufe) und `refs/deep-review/` (Hilfscommits) an. In den
Cache-Ordner schreibt `plan` eine `.gitignore` mit `*`, wenn sie fehlt, damit `git add -A`
keinen Lauf committet; die `.gitignore` des Repos, Arbeitsbaum, Index und HEAD bleiben unberührt.

1. **Bereich, Profil, Fokus.** Bereich `BASIS..ZIEL`, Standard `HEAD`; Profil und Fokus aus der
   Tabelle unten. Ein Pfad statt eines Bereichs geht direkt an `/code-review <pfad>`, ohne Plan.
2. **Plan:**
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/review_kit.py" plan --range <bereich> [--profile …] [--focus …] [--split-at N] [--soll-file <datei>] [--since <lauf>[,<lauf>…]] [--with-tests]
   ```
   Die Lauf-ID steht in der ersten Ausgabezeile (`Lauf: <lauf>`). `plan` legt immer einen
   neuen Lauf an; fortgesetzt wird mit `--run <lauf>` bei den folgenden Befehlen.
   Grenzwerte, Schnittregel, „Nicht reviewt" und `--since`: [packets.md](references/packets.md).
3. **Gegenstellen:**
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/review_kit.py" counterparts --run <lauf>
   ```
   Schreibt `packets/<id>.md` und nennt je Paket `<id>: <von>..<bis> · …`. Dieser Bereich ist
   der des Reviews; den Originalbereich setzt du nicht selbst ein. Zeilenformat und Lesehilfe:
   [counterparts.md](references/counterparts.md).
4. **Review je Paket**, in Plan-Reihenfolge, eines nach dem anderen, mit der Stufe aus dem Auftrag:
   ```
   /code-review <stufe> --max-findings all <von>..<bis>
   ```
   Der Reviewer bekommt `packets/<id>.prompt.md` **unverändert** (Auftrag, Block, Rückgabeformat,
   Marke; den Pfad nennt `counterparts`) und liest es bis zur letzten Zeile. Seine Antwort ist
   das Objekt `{"marke", "stufe", "findings"}` aus dem Rückgabeformat der Datei, ein Paket ohne
   Funde mit `"findings": []` ([review-brief.md](references/review-brief.md)). Dann:
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/review_kit.py" record --run <lauf> --packet <id> --tool code-review <datei|->
   ```
   `--no-block` nur, wenn der Reviewer die Datei nicht bekam; `audit` nennt das Paket dann.
   Das Werkzeug steht ohne Schrägstrich: Git Bash unter Windows schreibt ein Argument mit `/`
   am Anfang in einen Windows-Pfad um; der Bericht nennt es `/code-review`. Eine abgewiesene
   Antwort korrigierst du und rufst `record` erneut auf. Ohne `/code-review` (claude.ai,
   andere Agenten) läuft dieselbe Paketfolge im Hauptkontext nach „Review ohne /code-review"
   in review-brief.md, mit `--tool "Review ohne /code-review"`; der Bericht nennt das wörtlich.
5. **Vereinigen:**
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/review_kit.py" merge --run <lauf>
   ```
   Schreibt `findings.json`; Funde einer Datei bis drei Zeilen auseinander werden einer.
6. **Prüfen** (Profil `checkpoint` oder `--verify`): `verify --run <lauf>`, je Auftrag ein Prüfer
   (Sonnet) mit dem Schlüssel des Funds im Objekt, `verdict --run <lauf> <datei>`, dann `merge`.
7. **Bericht, Audit, Aufräumen.** `report --run <lauf>` schreibt `report.md` im Laufordner;
   eigene Einordnung nur unter `## Einordnung` am Ende, davor änderst du nichts:
   ```bash
   python "${CLAUDE_SKILL_DIR}/scripts/review_kit.py" report --run <lauf>
   python "${CLAUDE_SKILL_DIR}/scripts/review_kit.py" audit --run <lauf>
   python "${CLAUDE_SKILL_DIR}/scripts/review_kit.py" cleanup --run <lauf>
   ```
   `audit` endet mit Exit 1 bei einer Lücke; `audit.json` ist trotzdem geschrieben. Meldet es
   `report_mismatch`, schreibt `report --run` den Bericht neu, oder du berichtigst die
   Einordnung; dann erneut `audit`. `cleanup --stale --run
   <lauf>` löscht die Refs aller anderen Läufe, `cleanup --stale` ohne `--run` löscht die
   Refs **jedes** Laufs; beide auch die eines Laufs, der in einem anderen Worktree noch offen
   ist. Also `--stale` nur, wenn kein anderer Lauf offen ist.

## Profile und Fokus

| Wunsch | Aufruf | Besonderheit |
| --- | --- | --- |
| Standard | `--profile standard --focus bugs` (beides Standard) | Normalfall |
| Prüfpunkt aus subagent-dev | `--profile checkpoint --soll-file <datei>` | `--soll-file` ist Pflicht, nur Fokus `bugs`; das Soll hängst du als Abschnitt „Soll" an den Auftrag |
| Wartbarkeit, Qualität | `--focus quality` | keine Gegenstellen; Auftrag „Fassung 2" in review-brief.md |
| Sicherheit | `--focus security` | ein Paket `s1` über alles. `/security-review` (`--tool security-review`) läuft nur, wenn sein Umfang dem Plan entspricht (Bedingungen in review-brief.md, „Fokus security"); sonst Review im Hauptkontext mit `--tool "Review ohne /security-review"` |
| Folgelauf nach einem Fix | neuer `plan` mit `--since <lauf>` | Funde unveränderter Dateien werden übernommen |
| Tests mitprüfen | `--with-tests` | Testdateien stehen sonst unter „Nicht geprüft" |

## Übergabe

Die Übergabe nennt die Lauf-ID, den Pfad des Berichts (`.skills/cache/deep-review/<lauf>/report.md`),
die Zahl der Funde und die Abdeckung `<covered>/<total>` aus `audit.json`. Lief ohne
`/code-review` oder `/security-review`, steht das Werkzeug wörtlich dabei. Bei einer Lücke
(`missing`, `stale`, `lost_findings`) steht „unvollständig" mit der Liste, nie „fertig".

`--max-findings all` bleibt nach dem Lauf als Wahl des Nutzers gesetzt. Zurück geht es mit
`/code-review --max-findings default`; auch das sagt die Übergabe.

deep-review behebt nichts. Im Profil `checkpoint` behebt subagent-dev die Funde über
`fix-task`. Sonst nennt die Übergabe debug-ledger für Funde mit unklarer Ursache und
test-first für den Regressionstest.

## Contract

- **Abdeckung gegen den Plan.** `audit` meldet jedes Paket ohne angenommenes Ergebnis
  (`missing`) und jede nicht angenommene Ergebnisdatei, etwa eines anderen Plans (`stale`).
  `coverage` zählt nur die angenommenen Ergebnisse gegen die Pakete des Plans.
- **Kein Fund verschwindet.** Jeder Fund eines angenommenen Ergebnisses und jeder übernommene
  Fund (`--since`) steht in `findings.json`; sonst meldet `audit` ihn unter `lost_findings`.
- **Bericht und Daten stimmen überein.** „vollständig" steht nur bei lückenlosem Audit.
- **Gegenstellen sind mechanisch.** `counterparts` wählt nicht nach Verdacht aus und nennt die
  Zahl der nicht aufgelösten Stellen.
- **Nichts wird ausgeführt, nichts behoben.** Das Skript startet keinen Zielcode, die Skill
  schreibt weder Fixes noch Commits; Hilfscommits liegen nur unter `refs/deep-review/`.
- **Anti-Zeremonie-Fall.** Bis `--split-at` (Standard 800) geänderte Zeilen ist der Plan ein
  Paket (`split: false`); ohne Wurzel-Commit läuft ein `/code-review` über den Originalbereich,
  ohne Hilfscommits. Für jeden Plan mit `split: false`, auch beim Wurzel-Commit, prüft `audit`
  die Einordnung auf höchstens 8 Textzeilen. Nach `--since` mit Übernahme steht
  `split: true`, auch bei einem Paket (etwa Fokus `security`); dort prüft `audit` die Länge nicht.

## Anti-Rationalisierung

| Gedanke | Realität |
| --- | --- |
| „Das Paket ist klein, den Block lasse ich weg" | Der Block ist der Grund, warum Pakete besser prüfen als ein Review über alles. Unverändert mitgeben. |
| „Das Audit meldet nur ein fehlendes Paket, ich nenne es trotzdem fertig" | Dann steht „unvollständig" mit dem Paket in der Übergabe. |
| „Ich fasse zwei Pakete in einem Review zusammen" | `record` nimmt je Paket genau ein Ergebnis an; der Zuschnitt war der Zweck. |
| „Ich nehme den Originalbereich, das ist einfacher" | Bei Hilfscommits zeigt er das ganze Branch-Diff, nicht das Paket. Nimm `<von>..<bis>` aus `counterparts`. |
| „Ein Paket ohne Funde braucht kein `record`" | Ohne Ergebnis ist das Paket nicht reviewt; es bekommt `"findings": []`. |
| „Ein kleiner Bereich braucht trotzdem sechs Schritte mit Hilfscommits" | Bis `--split-at` (Standard 800 Zeilen) ist es ein Paket und ein kurzer Bericht. |

## Abgrenzung

- **review-context** — sammelt Kontext und Soll für einen Diff und reviewt nichts. deep-review
  sammelt Gegenstellen je Paket und nimmt ein Soll nur über `--soll-file` entgegen.
- **subagent-dev** — legt die Prüfpunkte eines Plans fest und ruft deep-review mit
  `--profile checkpoint` auf. deep-review prüft, plant keine Prüfpunkte.
- **debug-ledger** — für einen bestätigten Fund mit unklarer Ursache. deep-review meldet,
  diagnostiziert nicht.
- **test-first** — für den Regressionstest zu einem Fund. deep-review schreibt keine Tests.
- `/code-review` — kleiner Diff, PR oder Pfad; hier wird es je Paket aufgerufen.
- `/security-review` — Sicherheitsaudit eines Systems; deep-review reicht Fokus `security`
  nur durch, wenn dessen Umfang dem Plan entspricht, und ist keine Sicherheits-Skill.
