---
name: visual-summary
description: Use for ad-hoc "fass das zusammen"/"mach mir eine Zusammenfassung" requests over documents, articles, chat/work history, research results, or code/project state — picks one of four structured formats (one-pager, decision-memo, timeline-brief, learn-card) and renders styled HTML and/or plain Markdown from a single, source-bound content model. Also use for a bare "fass das zusammen" with no material attached and nothing obvious in the working directory to summarize — do not fall back to generic directory exploration or a generic clarifying question first; this skill's own first step is asking what to summarize and for whom/why. Not for periodic project/status reports (use dev-report) and not for end-of-session handover (use handoff).
---

# visual-summary — Format-Familie für Zusammenfassungen

**Inhalt vor Medium.** Erst entsteht ein medienneutrales Inhaltsmodell (Kernthese,
Belege mit Referenz, Datenpunkte mit Referenz, offene Punkte), dann rendert einer
von zwei Renderern daraus HTML oder Markdown. Beide Ausgaben sind inhaltsgleich,
weil die Quellenbindung im Modell sitzt, nicht im Layout.

## Der Contract

```
KEINE ZAHL UND KEIN CHART OHNE QUELLENREFERENZ IM MODELL.
```

- Jede Zahl und jeder Chart-Datenpunkt im gerenderten Output trägt unmittelbar im
  Anschluss eine Referenzmarke: Markdown native Fußnote (`[^1]`), HTML ein
  verlinkter Anker (`[<a href="#ref-1">1</a>]`). Jede Marke hat einen Eintrag in
  der Quellenliste am Dokumentende — Locator-Regeln je Input-Art stehen in
  `references/evidence.md`.
- **Referenzmarken sind dokumentweit fortlaufend nummeriert (1, 2, 3, …) — nicht
  pro REPEAT-Block neu bei 1.** Belege, Chart-Zeilen und die Quellenliste teilen
  sich einen einzigen Zähler. Ein Beleg behält seine Nummer bei jeder erneuten
  Erwähnung im selben Dokument. Die Quellenliste enthält jede vergebene Nummer
  genau einmal; jede im Text vergebene Marke hat dort ihren Eintrag — sonst
  zeigt die Marke ins Leere und der Contract bricht strukturell, auch wenn
  jede einzelne Zahl für sich genommen eine Marke trägt.
- Eine Zahl ohne Fundstelle im Modell gehört nicht in den Output — auch nicht als
  eigener „unbelegt"-Absatz. Ohne Beleg fliegt sie raus, Punkt.
- Das Längenbudget des Formats ist hart (`references/formats.md` nennt die
  Zeilenzahl je Format für Markdown). Kürzen ist die Leistung dieser Skill, nicht
  die Zumutung an den Leser. Ein Budget-Überlauf wird nie durch kleinere Schrift
  oder engere Zeilen gelöst, sondern durch Weglassen von Nebensächlichem.
- Ein Format pro Output. Wer mischen möchte, hat das falsche Format gewählt —
  zurück zur Triage, nicht zum Frankenstein-Layout.
- Trägt das Material weniger als drei Belege für einen One-Pager her, bleiben es
  weniger. Ein erfundener dritter Beleg ist schlimmer als ein kürzerer One-Pager.
- Keine offenen Punkte? Dann steht „Keine." da — keine erfundene Unsicherheit,
  nur damit die Sektion nicht leer wirkt.

## Triage — zwei Fragen, dann Entscheidung

1. **Wer liest es?**
2. **Welche Entscheidung oder Handlung soll folgen?**

| Antwort auf Frage 2 | Format |
| --- | --- |
| Eine Entscheidung steht an | `decision-memo` |
| Überblick für Dritte, keine Entscheidung | `one-pager` |
| Verlauf/Entwicklung nachvollziehen | `timeline-brief` |
| Eigenes Lernen, Konzept verinnerlichen | `learn-card` |

Medium: Bildschirm/Teilen → HTML, Repo/Notizen → Markdown, auf Wunsch beides aus
demselben Modell. Nennt der Nutzer weder Publikum noch Zweck, und lässt sich
beides auch nicht aus der Anfrage ableiten, werden genau diese zwei Fragen
gestellt — nie ein Format geraten. Fehlt zusätzlich auch jedes Material (der
bare „Fass das zusammen." ohne Anhang, ohne Pfad, ohne eingefügten Text — der
Musterfall dieser Skill), werden Material- und Triage-Fragen **zusammen in
einer** Rückfrage gestellt, nicht nacheinander (siehe Ablauf, Schritt 1). Details
je Format (Aufbau, Budget, Leerfälle) stehen in `references/formats.md`,
Chart-Entscheidungen in `references/charts.md`.

**Die Format-Wahl wird begründet ausgegeben** — eine Zeile wie „Format:
decision-memo (Entscheidung steht an), Medium: HTML (zum Teilen)." ist Teil der
Übergabe, kein stilles Vorgehen.

## Ablauf

1. **Material und Kontext klären — in einer Rückfrage, nicht nacheinander.**
   Zwei Dinge können fehlen: das Material selbst, und der Kontext (Publikum,
   Zweck) aus der Triage. Fehlt nur eines der beiden, wird nur danach gefragt.
   **Fehlen beide — der bare „Fass das zusammen." ohne Anhang, ohne Pfad, ohne
   eingefügten Text und ohne erkennbares Publikum oder Ziel —, werden Material
   *und* die zwei Triage-Fragen in derselben Antwort gestellt, wortwörtlich
   beide, nicht nur sinngemäß angedeutet.** Das gilt auch dann, wenn „wer liest
   es" noch keinen Sinn zu ergeben scheint, solange unklar ist, worum es
   überhaupt geht — genau dieser Reflex („erst das Material, die Triage kommt
   später") ist der Fehler: Sobald der Nutzer irgendein Material nachliefert,
   wird direkt gerendert, und die Triage bleibt für immer ungestellt. Beispiel
   für eine korrekte, kombinierte Rückfrage:
   > „Ich brauche noch zwei Dinge: (1) Was soll ich zusammenfassen — Datei,
   > Text, Chat-Verlauf oder Code-Stand? (2) Wer liest das Ergebnis, und welche
   > Entscheidung oder Handlung soll daraus folgen?"
   Diese Fragen dürfen anders formuliert sein, aber beide Themen — Material
   UND Publikum/Zweck — müssen in derselben Antwort auftauchen.
   - Dokument/Artikel: Pfad oder Text.
   - Chat-/Arbeitsverlauf: **wird übergeben, nie erraten** — fehlt er, sag das
     und frag nach Pfad oder Einfügung, statt aus der laufenden Session zu
     rekonstruieren (die könnte die falsche sein, ohne dass es auffällt).
   - Code-/Projektstand: Repo-Pfad oder Diff.
   - Triage (siehe oben): wer liest es, welche Entscheidung/Handlung folgt.
2. **Modell bauen**: Kernthese (ein Satz), Belege (Aussage + Locator + Konfidenz),
   Datenpunkte (für Charts, mit Locator), offene Punkte. Erst danach rendern.
3. **Slug festlegen.** Nennt der Nutzer einen Slug, gilt er. Sonst ein
   kebab-case-Slug aus der Kernthese ableiten (≤ 4 Wörter).
4. **Rendern**: Template aus `assets/<format>.html` bzw. `assets/md/<format>.md`.
   Slots (`{{PLATZHALTER}}`) füllen, Wiederholblöcke (`<!-- REPEAT: x -->` …
   `<!-- /REPEAT -->`) je Beleg/Datenpunkt/Zeitstrahl-Eintrag duplizieren. Kein
   eigenes Layout erfinden — die Templates sind fertig.
5. **Ablegen**: Repo (`.git` im cwd oder einem Elternverzeichnis vorhanden) →
   `docs/summaries/<format>-<slug>.md|html`; sonst
   `~/.skills/visual-summary/summaries/<format>-<slug>.*`. Bootstrap-Regel: Der
   erste Lauf kündigt die Anlage von `docs/summaries/` an und nennt den Pfad.
   Jede Datei trägt die Artefakt-Kopfzeile aus `docs/artifact-header.md` als
   erste Zeile.
6. **Selbst-Audit vor Lieferung:**
   - Überlebt die Kernaussage, wenn der Leser nur Headline und Chart sieht?
   - Ist jeder Beleg klickbar/auffindbar (Referenzmarke → Quellenlisten-Eintrag)?
   - Ist das Budget eingehalten?
   - **Gegenprobe Referenzmarken:** Hat jede im Text vergebene Marke einen
     Eintrag in der Quellenliste, und wird jeder Eintrag der Quellenliste
     mindestens einmal referenziert? Eine Marke ohne Eintrag oder ein Eintrag
     ohne Marke ist derselbe Fehler wie eine Zahl ohne Beleg — beide durchbrechen
     den Contract, auch wenn jede einzelne Zahl für sich genommen eine Marke trägt.
   - Bei HTML zusätzlich: Layout-Sichtprüfung (Datei im Kopf durchgehen oder
     Screenshot ansehen) — das Zeilenbudget ist für HTML nicht mechanisch
     prüfbar, nur die Markdown-Fassung hat eine harte Zeilenzahl.

## Anti-Rationalisierung

| Gedanke | Realität |
| --- | --- |
| „Mehr Details machen es wertvoller" | Das Budget ist die Wertgrenze. Kürzen ist die Leistung, nicht der Verlust. |
| „Die Zahl stand irgendwo im Dokument" | Ohne Fundstelle im Modell keine Zahl im Output — „irgendwo" ist kein Locator. |
| „Ein schickes Diagramm wertet es auf" | Ein Chart ohne Frage, die er beantwortet, fliegt (`references/charts.md`). |
| „Format mische ich passend" | Ein Format pro Output. Mischbedarf heißt: falsches Format gewählt. |
| „Ich weiß es noch aus dem Gespräch" | Der Chat-Verlauf wird übergeben, nie erraten — Erinnerung ist der falsche Verlauf, ohne dass es auffällt. |
| „Drei Belege muss ich voll machen" | Trägt das Material nur zwei, bleiben es zwei. Ein erfundener dritter ist schlimmer. |
| „Ohne Material ergibt die Publikums-Frage noch keinen Sinn, erst mal nachfragen was" | Genau der Reflex, der die Triage nie stellt. Beide Fragen gehören in dieselbe Rückfrage — auch wenn „wer liest es" noch abstrakt wirkt. |

## Abgrenzung

- **dev-report** — periodische Projekt-/Statusreports aus Git-Fakten. Diese
  Skill ist für Ad-hoc-Material jeder Art, nicht für wiederkehrende Reports.
- **handoff** — Sitzungszustand für die nächste Claude-Session, kein Bericht an
  Menschen.
- **human-prose** — „mach das menschlicher", auch über eine Zusammenfassung von hier;
  diese Skill wählt das Format, human-prose den Stil.
- Nicht diese Skill: Slides/Präsentationen, Langform-Dokumente, automatische
  Verteilung (Mail/Slack), Übersetzung.
