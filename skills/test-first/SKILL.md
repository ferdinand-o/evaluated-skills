---
name: test-first
description: "Use when implementing a new behavior or fixing a diagnosed bug in code — each behavior gets a test that must fail first, then the minimal code to pass it, and every red and green is recorded with command and exit code in .skills/cache/test-first/log.md by tdd_log.py, so a test that passed on its first run shows up as such. Triggers include \"test first\", \"TDD\", \"rot-grün\", \"schreib erst den Test\", \"füge X hinzu\" for new code with tests, and code tasks of a work-plan plan. Not for deciding which tests a repo needs (use testing-strategy), not for diagnosing a bug (use debug-ledger first; the regression test afterwards belongs here), and not for docs, formatting, renames or config without a behavior change — then say literally \"Kein Test-Zyklus nötig\" with the reason. If the user explicitly declines tests, write none and say literally \"ungetestet auf Wunsch\"; time pressure alone is no waiver. If the superpowers plugin is installed, this replaces its test-driven-development skill."
---

# test-first — Rot vor Grün, belegt statt behauptet

**Ein Test, der nie rot war, belegt nichts.** Im Endstand sieht ein nachträglich
geschriebener Test aus wie TDD. Deshalb steht jeder Lauf mit Befehl und Exit-Code im Log —
und ein sofort grüner Test steht dort als `sofort-grün`, nie als `red`.

## Eiserne Regel

```
KEIN PRODUKTIONSCODE FÜR EIN NEUES VERHALTEN, BEVOR EIN TEST DAFÜR ROT GELAUFEN IST.
EIN TEST, DER NIE ROT WAR, BELEGT NICHTS.
```

Rot vor Grün verlangt diese Datei (G1). Dass ein Grün ein Rot desselben Tests hat und ein
sofort grüner Test als solcher dasteht, meldet `tdd_log.py` (G2). Es hält niemanden an.

## Ablauf

`T="${CLAUDE_SKILL_DIR}/scripts/tdd_log.py"` — Aufrufe mit `python "$T" …`.

1. **Verhalten benennen.** Eine beobachtbare Eigenschaft in einem Satz, eine ID ohne
   Leerzeichen und ohne `|` — meist der Testname (`references/cycle.md`).
2. **Test schreiben**, nur den Test. Kein Produktionscode in derselben Änderung.
3. **Rot:** `python "$T" red --test <id> -- <befehl>`. Der Befehl führt genau diesen
   Test aus (Form je Runner in `cycle.md`). Ausgabe lesen: der erwartete Fehlschlag, kein
   fehlendes Runner-Modul. Meldet das Skript `sofort grün`: Der Test prüft nichts Neues —
   schärfen —, oder das Verhalten gibt es schon; dann **nichts implementieren** und es
   in der Übergabe sagen.
4. **Minimal implementieren**, bis dieser Test grün wird — nicht mehr.
5. **Grün:** `python "$T" green --test <id> -- <befehl>`. Ohne Rot desselben Tests
   schreibt das Skript keine Zeile und endet mit 1.
6. **Aufräumen** ohne Verhaltensänderung, dann `python "$T" refactor --test <id> -- <befehl>`.
7. **Übergabe:** `python "$T" status`. Die Antwort nennt jeden Test mit Rot und Grün aus
   dem Log, jeden sofort grünen und jeden, dem ein Schritt fehlt — dazu einmal den
   Verifikationsbefehl des Repos.

Mehrere Verhalten: Schritt 1 bis 6 je Verhalten, nacheinander. Eine neue Aufgabe beginnt
mit `python "$T" start --note "<aufgabe>"`; `status` liest nur den letzten Abschnitt.

Das erste Log legt `.skills/cache/test-first/` an der Repo-Wurzel an. Steht `.skills/cache/`
nicht in der `.gitignore`, sagt das Skript es — und die Antwort auch: Dort ist ein
unversionierter Ordner entstanden.

## Ausnahmen und Verzicht

- **Kein Verhalten, kein Zyklus.** Reine Doku, Formatierung, Umbenennung, Konfiguration —
  jeweils ohne Verhaltensänderung: Die Antwort sagt „Kein Test-Zyklus nötig" mit dem
  Grund, und es entsteht kein Log.
- **Ausdrücklicher Verzicht.** Sagt der Nutzer, dass er keine Tests will („ohne Tests",
  „ich teste selbst"): kein Test, kein Log, und die Übergabe sagt „ungetestet auf Wunsch".
- **Druck ist kein Verzicht.** „Schnell", „keine Zeit", „nur kurz" ändern den Zyklus nicht.
  Ein Zyklus für ein kleines Verhalten kostet zwei Testläufe.

Ohne Python oder ohne das Skript: Zyklus trotzdem einhalten, Rot und Grün mit Befehl und
Exit-Code in der Antwort nennen, und die Übergabe sagt „ungeprüft — kein Log".

## Contract

- **Rot vor Grün, je Test.** Kein `green` ohne vorheriges `red` derselben ID.
- **Sofort grün ist eine eigene Phase** und wird in der Übergabe genannt.
- **Belegt oder ungeprüft.** Die Übergabe nennt Tests nur mit Zeilen aus `log.md`; ohne
  Log keine Aussage „testgetrieben".
- **Druck ist kein Verzicht;** nur ein ausdrücklicher Verzicht auf Tests ist einer.
- **Anti-Zeremonie:** Ein Tippfehler in der Doku läuft ohne Zyklus und ohne Log.
- **Frontmatter:** nur `name`/`description`. Tier 1, `tdd_log.py` nur Stdlib.

## Anti-Rationalisierung

| Gedanke | Realität |
| --- | --- |
| „Ich schreibe den Code schnell, der Test kommt gleich danach" | Dann bestätigt der Test den Code, statt ihn zu fordern. Er war nie rot. |
| „Der Test ist sofort grün — umso besser" | Er prüft nichts Neues, oder das Verhalten gab es schon. Beides gehört in die Übergabe, keines ist ein Erfolg. |
| „Die ganze Suite als Befehl ist einfacher" | Dann färbt ein fremder roter Test dein Rot. Ein Test je Lauf. |
| „Der Nutzer hat es eilig, ich lasse den Zyklus weg" | Eile ist kein Verzicht. Zwei Testläufe sind schneller als ein Bug ohne Test. |
| „Das Log kann ich am Ende von Hand ergänzen" | Eine Zeile ohne Lauf ist eine Behauptung. Das Log schreibt nur `tdd_log.py`. |
| „Für eine Doku-Korrektur mache ich der Ordnung halber einen Zyklus" | Kein Verhalten, kein Test. „Kein Test-Zyklus nötig" ist die vollständige Antwort. |

## Abgrenzung

- **testing-strategy** — welche Tests ein Repo braucht, Schichten, Repo-Typ. test-first
  plant nicht; es führt einen Test durch den Zyklus.
- **debug-ledger** — Bug und Diagnose. test-first übernimmt erst den Regressionstest
  danach: rot vor dem Fix, grün danach.
- **work-plan** — Plan mit Code-Tasks; deren Steps (Test schreiben, Rot sehen,
  Implementieren, Grün sehen) laufen über test-first.
- feature-spec erzeugt Test-Stubs aus Given/When/Then; setup-repo hält das Turn-Ende an,
  solange der ganze Verifikationsbefehl rot ist — test-first prüft einzelne Tests.
