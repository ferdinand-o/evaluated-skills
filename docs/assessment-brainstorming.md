<!-- skill: -- | schema: 1 | generated: von Hand, Prüfung am 2026-09-11 gegen obra/superpowers@b36e082 (v6.3.0), die synchronisierte eigene brainstorming-Skill (source: custom, Stand 2026-08-05) und den Repo-Stand 34af3ac -->
# Prüfung: Eine eigene Nachfolgerin für `superpowers:brainstorming`?

**Kurzantwort.** Nein — und die Frage ist anders gestellt, als der Befund sie
beantwortet. `superpowers:brainstorming` hat in diesem Repo genau eine Spec geschrieben
(`cad-parts`, 2026-07-10); die siebzehn Skill-Specs seit Zyklus 1 stammen aus der
**eigenen** `brainstorming`-Skill im Nutzerprofil (`source: custom`), deren Template
alle 18 Specs tragen. Die Nachfolgerin existiert also; sie heißt nur genauso wie das
Original, und die Routing-Matrix sagt nicht, welche von beiden gemeint ist. Was gemessen
fehlt, liegt nicht im Dialog, sondern danach: Die drei Specs, die vor dem Bau
unabhängig geprüft wurden (15, 16, 17), brauchten je eine Überarbeitung von 119 bis
217 Zeilen — sachliche Fehler über das eigene Repo, unfahrbare Evals, Zahlen ohne
Messung. Die Spec-Reviews sind der wirksamste Mechanismus der Pipeline, und sie stehen
nirgends: kein Prompt im Repo, kein Pflichtschritt, ihr Ergebnis nur in Commit-Bodies.
Dazu hat das Spec-Format keinen Eigentümer — `impl-plan` liest die Eval-Tabelle aus
3 von 17 Specs. Empfehlung: keine Spec 18, sondern drei Ergänzungen bei den
bestehenden Eigentümern — in `skill-forge` Spec-Template und Fragenliste als Eingabe
für `brainstorming` sowie der Spec-Review mit Nachmessen als Pflichtschritt, in
`subagent-dev` ein `lint_spec` neben dem Plan-Lint, das auch den Review-Vermerk der
Kopfzeile prüft und den Pflichtschritt damit von G1 auf G2 hebt.

Alles Weitere ist Beleg. Was ich gemessen habe, steht mit Zahl; was ich nur gelesen
oder vermutet habe, ist so markiert (§9).

## 1 · Was geprüft wurde

| Quelle | Stand | Umfang |
| --- | --- | --- |
| `obra/superpowers`, `skills/brainstorming` | b36e082, 2026-08-12 (v6.3.0) | SKILL.md 250 Zeilen (2.277 Wörter) mit Drei-Pfad-Router, `spec-document-reviewer-prompt.md` (49), `visual-companion.md` (299), fünf Dateien für den Browser-Begleiter (1.432 Zeilen: vier Skripte und ein HTML-Template, Node) |
| eigene `brainstorming`-Skill | Nutzerprofil, `~/.claude/skills/synced/…/brainstorming`, `source: custom`, 2026-08-05 | SKILL.md 157 Zeilen (1.648 Wörter), keine Skripte, kein Reviewer-Prompt |
| Dieses Repo | 34af3ac (`main`) plus Branch `claude/assessment-writing-skills-plans` | 18 Specs, 19 Pläne, 16 Reports, `docs/superpowers/specs/` und `validation/` (cad-parts), Git-Historie der Specs, `plan_to_tasks.py` (`spec_eval_table`) |
| Kontext | `feature-spec` (03) als Haus-Spec-Skill, `skill-forge` (17) Ablauf Schritt 1, `impl-plan` (16) Schritt 1 | — |

Methode: Zählung über alle Specs (Zeilen, Wörter, Abschnitte, Hausinhalte), Parser-Lauf
von `spec_eval_table` über alle Specs, Diff-Statistik der drei Review-Commits,
Zahlenvergleich vor/nach Review, Lektüre der Commit-Bodies und Report-Abschnitte.
Keine Evals gefahren; die beiden Skills wurden nicht gegeneinander gemessen (§9).

## 2 · Woher die Specs wirklich kommen

| Herkunft | Specs | Beleg |
| --- | --- | --- |
| claude.ai, eigene `brainstorming` | 01–14 | alle 14 tragen escaptes Markdown (`Skill\-Spezifikation`, `\+`), wie es beim Kopieren aus der Web-Oberfläche entsteht; ein einziger Import-Commit f204347 am 2026-08-14. Spec 00 („nachgezogen") ist ohne Escapes, ihre Herkunft nicht belegt |
| Claude Code, eigene `brainstorming` | 15, 16, 17 | Sessions in diesem Repo; die superpowers-Skill ist im Container nicht installiert, die eigene ist es |
| Claude Code, `superpowers:brainstorming` | `cad-parts` (2026-07-10) | `docs/superpowers/specs/2026-07-10-cad-parts-skill-design.md`, 321 Zeilen, zehn nummerierte Abschnitte, „Autor: ferdinand-o + Claude (brainstorming)", RED-Baseline unter `validation/` |

Das Template Problem / Constraints / Approach / Alternatives considered / Out of scope /
Open questions / Next steps steht wörtlich in der eigenen Skill (Abschnitt 5) und in
keiner superpowers-Datei — superpowers schreibt nach `docs/superpowers/specs/` ohne
Vorlage. Alle 18 Specs unter `specs/` tragen die sieben Abschnitte in dieser
Reihenfolge; Spec 04 hat zusätzlich `## Status`, Spec 00 Unterabschnitte.

Damit ist die Ausgangsfrage schon halb beantwortet: Die Sammlung hat
`superpowers:brainstorming` seit Zyklus 1 nicht benutzt. Für 01–14 ist der tragende
Grund nicht das Template, sondern der Ort: In claude.ai kann ein Claude-Code-Plugin
gar nicht laden, dort gibt es nur die Profil-Skills. Das Template ist Zusatzindiz; das
Datum der Profil-Skill (2026-08-05) ist ein Änderungsdatum und beweist nicht, dass sie
vor den Specs existierte (§10). Was bleibt, ist ein
**Namensproblem**: Auf dem Rechner des Nutzers sind beide installiert, die Description
von superpowers ist die pushigere („You MUST use this before any creative work"), und
`skill-forge` Schritt 1, `impl-plan` Abgrenzung und die Routing-Matrix sagen nur
„brainstorming". Welche der beiden bei „Brainstorming für Spec 18 starten" lädt,
entscheidet der Harness — gemessen ist es nicht (§9).

## 3 · Drei Fassungen nebeneinander

| Dimension | `superpowers:brainstorming` v6.3.0 | eigene `brainstorming` | was die Specs hier brauchen (Spec 00, `impl-plan`, `skill-forge`) |
| --- | --- | --- | --- |
| Einstieg | Drei-Pfad-Router (Spike / Bounded / Architectural), laut ausgesprochen; „im Zweifel der schwerere Pfad" | Orientieren, dann **eine** Fragerunde mit höchstens drei Fragen und Notausgang („just go") | Orientieren heißt hier *messen*: Nachbar-Descriptions, Routing-Matrix, `known-limits.md`, was der Harness prüfen kann |
| Fragen | eine pro Nachricht, so viele wie nötig — das Interview, das Spec 03 als „für Solo-Arbeit zu langsam" verwirft | gebündelt, mit Annahmen statt Fragen („I'm assuming … say if not") | die vier Hausentscheidungen: Tier, Gate-Grad, Anti-Zeremonie-Fall, die zwei stärksten Konkurrenten |
| Optionen | 2–3 Ansätze mit Trade-offs | vier nach Art verschieden (die langweilige, die umgeformte, die ambitionierte, der Hack), plus die verworfene | — |
| Gate | `<HARD-GATE>`: keine Implementierung ohne Zustimmung, auf jedem Pfad | keins; „Spec is written — have a look" | G1 durchgehend; `skill-forge` verlangt den Review, nichts prüft die Spec |
| Ablage | `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`, committet | „a markdown file", Ort frei | `specs/Spec NN – <skill>.md` mit Kopfzeile „Skill-Spezifikation · Zyklus N · Entscheidung: …" — ungeschriebene Konvention, 17 von 18 halten sie (Spec 17 nicht) |
| Spec-Inhalt | frei; Sektionen skaliert; Selbst-Review in vier Fragen | Sieben-Abschnitte-Template; Selbst-Review in fünf Fragen, darunter „unearned specificity" | dazu: Eval-Tabelle mit `id`, Klasse, Fixture, Mechanismus; Skill-Struktur-Block; Abgrenzung mit Rückverweis; Tier je Skript; Gate-Sprache |
| Review | `spec-document-reviewer-prompt.md`: Subagent, „Only flag issues that would cause real problems during implementation planning", nichts über Faktenprüfung — und die SKILL.md ruft die Datei an keiner Stelle auf (null Verweise) | keiner außer dem Selbst-Review | der Review, der 15/16/17 gerettet hat: ein Subagent, der **Behauptungen nachmisst** — Prompt nicht im Repo |
| Übergabe | `writing-plans`, ausschließlich („Do NOT invoke any other skill") | keine | `impl-plan` (16), dann `skill-forge` (17) |
| Visuelles | Browser-Begleiter mit eigenem Node-Server, 1.432 Zeilen | „Show it when showing beats telling", ohne Werkzeug | nicht gebraucht: Specs hier sind Text und Tabellen |
| Sprache | Englisch | Englisch | Deutsch, englische Bezeichner |

Fair gelesen ist die superpowers-Fassung für **Code in fremden Repos** die
vollständigere: Der Router verhindert, dass ein Ein-Datei-Fix eine Spec bekommt, und
der HARD-GATE ist die Zustimmungsregel, die claude.ai-Sessions nicht haben. Für
Skill-Specs dieser Sammlung passt sie schlechter als die eigene: Jede Skill-Spec ist
„architectural" (neues Subsystem), also immer der volle Pfad mit Ein-Frage-Interview;
der Terminalzustand ruft `writing-plans` statt `impl-plan`; die Ablage widerspricht
`specs/`; und die eigene Fassung hat die zwei Stücke, die die 18 Specs geprägt haben —
das Template und den Vier-Optionen-Zwang. Was sich aus superpowers lohnt, ist genau
eines: der **Reviewer-Prompt als eigene Datei** — und zugleich die Warnung, die daran
hängt: Die Datei liegt im Repo, der eigene Ablauf ruft sie nie auf, also passiert der
Review dort nur, wenn jemand daran denkt. Ein Prompt allein ist G0; er wird erst mit
einem Pflichtschritt und einem prüfbaren Vermerk zu etwas.

## 4 · Gemessen: Wo die Specs brechen

### 4.1 Behauptungen ohne Messung — das Review korrigiert sie jedes Mal

Drei Specs wurden vor dem Bau von einem Subagenten mit frischem Kontext geprüft (die
cad-parts-Spec hatte ebenfalls einen Review-Commit, 7a12e7f, vor dem Harness und ohne
Fundliste im Body — sie bleibt hier außen vor). Die Commit-Bodies der Überarbeitungen
sind die genaueste Quelle für das, was Brainstorming allein nicht liefert:

| Spec | Review | geänderte Zeilen (Diff-Stat) | Umfang danach | Zahlen neu / weg |
| --- | --- | --- | --- | --- |
| 15 explain (f1b2b6d) | 5 blockierende Funde, 3 sachliche Fehler über Nachbarskills, 1 abgelehnt | 123 von 133 → 160 | +20 % | +3 / 0 |
| 16 impl-plan (d6d456e) | 23 Funde, 3 blockierend | 119 von 156 → 165 | +6 % | +9 / 2 |
| 17 skill-forge (0ecccfa) | Zahl nicht protokolliert („alle Zahlen nachgemessen") | 217 von 265 → 324 | +22 % | +6 / 1 |

Was die Reviews fanden, zerfällt in zwei Klassen:

- **Konsistenzfehler, die der Selbst-Review der Skill nennt und trotzdem nicht fing:**
  Widerspruch Anti-Rationalisierungs-Tabelle gegen offene Frage (15); Aufrufsyntax
  gegen das eigene Zielsystem (15); „Tier 0" bei einer Eisernen Regel, die an einem
  Skriptaufruf hängt (16); ein pytest-Test als „G3" gegen Spec 00 §4 (16); ein Eval,
  dessen Prompt verlangt, was die Eiserne Regel verbietet (16). Der Selbst-Review ist
  G1 in Reinform — dieselbe Doktrin, die die fünf Fragen stellt, hat die Spec
  geschrieben und liest sie wohlwollend.
- **Fakten über das Repo, die nur Nachmessen findet:** zwei Evals, die zwei Läufe
  vergleichen, obwohl `evals.json` einem Eval einen Prompt gibt (15); ein Lint, der im
  Eval-Workspace nicht existiert, weil `prepare()` nur den Skill-Ordner kopiert (16);
  `token:` in `Produces`, das `check_produces` als fehlend gemeldet hätte (16); „2–78
  Befunde" statt gemessen 14–78, „id-Spalte ab Spec 11" statt 15, ein Zitat, das im
  Body stand und nicht in der Description (16); ein als Zitat ausgegebener selbst
  übersetzter Satz, ein falsch zugeschriebener Präzedenzfall, eine Zusage „Grad 0", die
  beim Nachbarn „nie gesehen" heißt (15). Keine dieser Stellen ist ein
  Formulierungsproblem; jede ist eine Aussage über eine Datei, die niemand geöffnet
  hatte.

Die Skill sagt „Unearned specificity — numbers you invented rather than got from them
or verified": Die Regel ist bekannt, sie wirkt nicht, solange derselbe Kontext prüft,
der die Zahl erfunden hat. Nach dem Review stiegen die Zahlen in jeder Spec (16: von
17 auf 24 verschiedene) — die Reviews haben nicht Zahlen gestrichen, sondern die
erfundenen durch gemessene ersetzt und ergänzt.

Spec 00 selbst ist ein Beleg gegen sich: Sie behauptet, die Specs 06–09 nennten ihre
Gates „Blocker" und „jede Spec" delegiere das Trigger-Problem an „Description
schärfen". Im heutigen Text steht „block" in einer der vier (08, dort bereits im
korrigierten Sinn) und „Description schärfen" in 3 von 14. Ob die Specs vor dem
Import bereinigt wurden, zeigt die Historie nicht (ein Commit) — die Zahl in Spec 00
war jedenfalls nie nachgezogen.

### 4.2 Evals als Prosa

Spec 00 nennt es in ihrem Problem-Abschnitt selbst: „rund sechzig adversariale
Szenarien als unbepreister Posten". Gemessen an den Specs 01–14: alle 14 zählen ihre
Evals als „(1) … (4)" in einem Absatz auf, ohne ID, Klasse, Fixture oder Assertion;
keine trägt eine Tabelle. `plan_to_tasks.py`s `spec_eval_table` — der Leser, den `impl-plan` für die
Coverage-Prüfung braucht — findet Eval-IDs in **3 von 17** Specs (15, 16, 17: 8, 5, 5
IDs). In 8 von 14 Fällen hat die spätere `evals.json` mehr Evals als die Spec nennt
(learning-coach: 5 genannt, 11 gebaut); die Spec war für die Evals nie die Vorlage,
sondern ein Anlass.

Auch die drei Specs mit Tabelle hatten Eval-Defekte, die erst das Review fand (§4.1:
unfahrbare Zwei-Lauf-Evals, ein unbestehbarer Platzhalter-Eval, ein Eval, den „jedes
Modell besteht, weil es IDs abschreibt"). Das ist die Diskriminator-Frage aus
`skill-forge`, gestellt zu spät: Sie gehört in die Spec, nicht in die `evals.json`.

### 4.3 Offene Fragen und die Entscheidungen dazwischen

Die Specs 01–14 hinterlassen je ein bis vier offene Fragen als Prosa; drei Specs
verweisen dabei auf eine andere (01 auf 03, 07 und 10 aufeinander: „Spec 10 stellt
dieselbe Monorepo-Frage"), und keine der Fragen wurde gemeinsam entschieden. Die Reports zeigen, wo sie landeten: learning-coach entschied
seine drei beim Bau („Offene Fragen aus Spec 14, hier entschieden"), subagent-dev ließ
beide offen („nicht Teil dieses Auftrags"). Dazu führt jeder Report einen Abschnitt
„Zusätzliche Entscheidungen" oder „Abweichungen von der Spec" — grob gezählt 3 bis
10 Einträge pro Report, 87 über 16 Reports. Sechs Pläne und fünf Reports berufen sich
außerdem auf `brief-common.md` und `rulings-final-four.md`: eine Entscheidungsschicht
*zwischen* Spec und Bau, die im Repo nicht existiert (vier Reports melden die Datei
als fehlend). Die Specs waren also durchgängig unterbestimmt — was in Ordnung ist,
solange es markiert ist. Die Markierung dafür hat das Repo (`Annahme:`-Zeilen aus
Spec 03); in den Specs steht sie in 00 und 03, sonst nirgends.

### 4.4 Ein Format ohne Eigentümer

Die Hausinhalte einer Skill-Spec stehen in keinem Template — nur in den letzten drei
Specs und in dem, was `impl-plan` liest:

| Inhalt | verlangt von | vorhanden in |
| --- | --- | --- |
| Kopfzeile „Skill-Spezifikation · Zyklus N · Entscheidung: …" | Konvention | 17 von 18 (Spec 17 beginnt mit `## Problem`) |
| Skill-Struktur-Block | `impl-plan` Schritt 1 | 17 von 17 |
| Eval-Tabelle mit `id` unter einer Eval-Überschrift | `impl-plan` Schritt 1, `spec_eval_table` | 3 von 17 |
| Abgrenzung als eigener Abschnitt | `impl-plan` (Nachbarn-Task), `skill-forge` (`neighbors`) | 2 von 17 (15, 16); Spec 17 verteilt sie auf Prosa unter Approach, Spec 11 nennt das Wort nur in einer Formatbeschreibung; bei den übrigen ein „Description schärfen"-Satz in Next steps (3) oder nichts |
| Tier je Skript | Spec 00 §3 | 15 von 17 |
| G1/G2/G3-Sprache | Spec 00 §4 | 12 von 17 (gezählt als Token `G1`, `G2`, `G3`; wer „Grad N" mitzählt, kommt auf 11) |

Das ist dieselbe Lage wie bei den Plänen vor `impl-plan`: Der Konsument setzt ein
Format voraus, der Erzeuger kennt es nicht, und der Lint des Konsumenten meldet das
Fehlen „als Hinweis und prüft Coverage nicht" (`impl-plan` SKILL.md, Schritt 5). Die
Specs 01–14 haben keinen Konsumenten mehr; jede neue Spec hat zwei.

## 5 · Was `superpowers:brainstorming` hier ändern würde

Angenommen, die nächste Spec entstünde mit der superpowers-Fassung statt der eigenen:

- **Router:** Eine Skill-Spec ist immer „architectural" → voller Pfad. Der Router
  bringt hier nichts, weil es den Bounded-Fall (eine Satzänderung in einer SKILL.md)
  schon gibt und er bei `skill-forge` liegt, nicht bei einer Spec.
- **Ein-Frage-Interview:** genau das Muster, das Spec 03 für Solo-Arbeit als zu
  langsam verworfen und die eigene Skill durch eine gebündelte Runde ersetzt hat. Die
  drei Brainstormings zu 15–17 kamen mit je einer Runde aus (17: drei Entscheidungen
  per Auswahlfrage) — Beobachtung aus den Sessions, im Repo nicht messbar (§10).
- **HARD-GATE:** in Claude Code sinnvoll; hier stellt ihn die Übergabe an `impl-plan`
  ohnehin her, weil niemand baut, bevor der Plan steht.
- **Ablage und Übergabe:** `docs/superpowers/specs/` und `writing-plans` — beides
  falsch für dieses Repo, beides müsste jedes Mal übersteuert werden (die eine Spec,
  die so entstand, liegt bis heute an dem anderen Ort).
- **Reviewer-Prompt:** vorhanden, aber auf Implementierungslücken kalibriert und vom
  eigenen Ablauf nie aufgerufen; von den in §4.1 gezählten Funden hätte er die
  Konsistenzklasse erfasst, die Faktenklasse nicht — er sagt nichts über Nachmessen.
  Der eine superpowers-Fall hier hatte trotzdem einen Review-Commit (cad-parts,
  7a12e7f) — auf Zuruf, wie die drei Reviews danach.
- **Browser-Begleiter:** 1.432 Zeilen Node für Mockups. Keine Spec dieser Sammlung
  hatte eine visuelle Frage.

Urteil zu dieser Teilfrage: Die eigene Skill *ist* für diese Sammlung die bessere
Fassung; ein Nachbau von superpowers wäre ein Rückschritt. Als Konkurrentin im Routing
bleibt superpowers trotzdem — und das ist das einzige, was an ihr zu lösen ist.

## 6 · Urteil

**Keine Spec 18.** Der Dialog ist nicht das Problem; die drei gemessenen Lücken liegen
davor (Orientieren als Messen), danach (Review mit Nachmessen) und im Format
(Template, Lint). Alle drei haben schon einen Eigentümer:

1. **`skill-forge` besitzt die Hausmethode** — und Schritt 1 ihres Ablaufs sagt nur
   „`brainstorming` für Neues". Dort gehören hin: `assets/spec-template.md` (die sieben
   Abschnitte plus Kopfzeile, Skill-Struktur, Eval-Tabelle mit `id`/Klasse/Fixture/
   Mechanismus/Diskriminator-Spalte, Abgrenzung gegen zwei genannte Konkurrenten, Tier
   je Skript, Gate-Grad je Gate) und `references/spec-brief.md` — die Fragen, die das
   Brainstorming beantworten muss, bevor die Spec steht, und die Stellen, die es vorher
   *lesen* muss (Nachbar-Descriptions, Routing-Matrix, `known-limits.md` des
   Nachbarn, die neun Assertion-Typen von `evalkit`). Beides sind **Eingaben für
   `brainstorming`**, so wie die Skizzen in §7 der Vorgänger-Prüfung Eingaben für die
   Specs 16 und 17 waren — und Spec 17 ist die einzige, deren Plan mit `impl-plan`
   ohne Format-Nacharbeit entstand.
2. **Der Spec-Review wird Schritt 1b von `skill-forge`**, mit
   `references/spec-reviewer-prompt.md` neben dem vorhandenen `reviewer-prompt.md`:
   frischer Kontext, jede Behauptung über das Repo nachmessen (Dateien öffnen, Zahlen
   zählen, Parser laufen lassen), jede Eval-Zeile gegen `evalkit` prüfen (ein Prompt,
   ein prüfbares Muster, Diskriminator beantwortet), Widersprüche gegen Spec 00 §3/§4.
   Ergebnis als Liste „blockierend / wichtig / abgelehnt mit Grund" — das Format, das
   die Commit-Bodies d6d456e und f1b2b6d bereits haben.
3. **`lint_spec` in `plan_to_tasks.py`** — bei `subagent-dev`, nicht bei `impl-plan`:
   dessen Contract sagt ausdrücklich, dass der Lint dem Konsumenten gehört und jede
   Format-Erweiterung dort gebaut wird; `spec_eval_table` liegt schon da. Geprüft:
   Kopfzeile, sieben Abschnitte, Eval-Tabelle mit Pflichtspalten und
   `anti-ceremony-`-Präfix, Skill-Struktur-Block, Abgrenzung mit mindestens zwei
   Backtick-Namen, die als Skill existieren, `Annahme:`-Zeilen statt unmarkierter
   Festlegungen in Open questions, Tier je `scripts/`-Eintrag, Gate-Wörter — **und der
   Review-Vermerk**: Spec 15 und 16 tragen in der Kopfzeile „Überarbeitet nach
   unabhängigem Review". Der Lint verlangt den Vermerk ab Spec 18 und meldet sein
   Fehlen; erst damit ist Punkt 2 mehr als ein Satz im Ablauf. Exit ≠ 0 für Specs ab
   18; Specs ≤ 17 sind Historie ohne Konsumenten und stehen nicht im Register — ein
   Nummern-Cutoff ist ehrlicher als 14 Register-Einträge für Dateien, die niemand
   mehr ändert.

Das Verhältnis der drei: Punkt 1 senkt, was der Review findet; Punkt 2 fängt, was
Punkt 1 nicht senkt (Fakten); Punkt 3 macht das Format zur Regel statt zur Erinnerung.
Punkt 2 ist der mit dem gemessenen Hebel — 119 bis 217 Diff-Zeilen an Specs von 133
bis 265 Zeilen — und kostet am wenigsten: ein Prompt, ein Satz im Ablauf.

**Gate-Grade nach Spec 00 §4, ausgesprochen:** Punkt 1 ist für sich G1 — die Dateien
müssen dem Brainstorming mitgegeben werden, und das ist dieselbe Schwäche wie der
Review auf Zuruf. Prüfbar wird er über Punkt 3: Eine Spec, die Kopfzeile, Tabelle und
Abgrenzung trägt, hat das Template benutzt, sonst meldet der Lint. Punkt 2 ist für
sich G1 („verlangt"); mit dem Review-Vermerk als Lint-Regel wird er G2 („meldet"). Ein
Vermerk ist fälschbar — aber er ist ein Token in einer Datei, den ein Diff zeigt, statt
einer Erinnerung. Punkt 3 ist G2. G3 gibt es nicht: Eine ungeprüfte Spec richtet
keinen irreversiblen Schaden an, sie kostet eine Fix-Runde.

**Anti-Zeremonie:** Eine Spec-Änderung um eine Entscheidung (ein Satz in Open
questions wird zur Festlegung) löst `lint_spec` und den Commit aus, keinen zweiten
Review. Der Review gilt der ersten Fassung und jeder Änderung an der Eval-Tabelle —
dieselbe Regel, die `skill-forge` für `evals_due` schon hat.

**Routing:** Die Kollision der zwei `brainstorming`-Skills ist nicht im Repo lösbar
(Plugin gegen Profil-Skill). Was das Repo tun kann: an allen Stellen, die
„brainstorming" nennen (Spec 00 §5 und README je zweimal in der Matrix, `skill-forge`
Schritt 1, `impl-plan` Description und Abgrenzung), die eigene Fassung als gemeint
kennzeichnen und superpowers als
„nicht" eintragen — mit dem Grund aus §5 (Ablage, Übergabe). Ob das den Trigger
verschiebt, ist eine Stichprobe wie jeder Routing-Eval.

## 7 · Verworfene Alternativen

- **Spec 18 `skill-spec` als eigene Skill** (Ablauf: messen → eine Fragerunde → Spec
  nach Template → Review → `impl-plan`). Hätte den Vorteil, dass die Fragen zur
  richtigen Zeit im Kontext sind, ohne dass jemand eine Datei mitgibt. Verworfen, weil
  sie den Dialogteil der eigenen `brainstorming` nachbauen müsste (Optionen nach Art,
  Notausgang, Selbst-Review), um ihn dann zu spezialisieren — dreißig Zeilen
  Hausfragen in einer 150-Zeilen-Kopie. Und sie wäre die **dritte** Skill mit
  Brainstorming-Trigger auf demselben Rechner. Wenn sich nach zwei Zyklen zeigt, dass
  die Eingabedateien nicht mitgegeben werden, ist das der Zeitpunkt, sie zu bauen; die
  Skizze steht in §8.
- **`feature-spec` um einen Skill-Modus erweitern.** Die Nähe ist echt: Draft-first,
  `Annahme:`-Zeilen, ein G2-Gate (`export_stubs.py`), das die Form der
  Akzeptanzkriterien erzwingt — das Analogon für Skill-Specs wäre ein
  `export_evals.py`, der aus der Eval-Tabelle das `evals.json`-Gerüst erzeugt und bei
  fehlender Spalte verweigert. Verworfen als Modus: `feature-spec`s Spec ist
  wegwerfbar (`docs/specs/wip/`), ihre Kriterien sind Given/When/Then für pytest, ihre
  Ernte geht nach `docs/decisions.md`; eine Skill-Spec lebt dauerhaft unter `specs/`,
  ihre Kriterien sind Evals. Der Export-Gedanke ist aber der stärkste mechanische
  Kandidat in dieser Prüfung und gehört als Option zu `lint_spec` (Punkt 3): erst
  prüfen, später erzeugen.
- **Nur die Routing-Zeile ändern und sonst nichts.** Beseitigt das Namensproblem,
  nicht die drei gemessenen Lücken. Die nächste Spec bekäme wieder ihr Review ad hoc
  — oder gar nicht.

## 8 · Gegenargumente

- **„Der Review passiert doch schon."** Viermal — cad-parts (7a12e7f) und 15, 16, 17
  —, jedes Mal auf Zuruf („Von einem Fable Subagent reviewen lassen"), mit einem
  Prompt, der jedes Mal neu geschrieben wurde und nirgends liegt. Vierzehn Specs
  hatten keinen; was sie offen ließen, tauchte beim Bau auf: der fehlende
  Anti-Zeremonie-Eval von feature-spec steht im Report als „Spec-Lücke", den Eval-Pfad
  aus Spec 09 überstimmte Spec 00 erst beim Bau. Ein Schritt, der nur stattfindet,
  wenn der Nutzer daran denkt, ist G0.
- **„Ein Template macht die Specs länger."** Die drei Specs mit Tabelle sind 160–324
  Zeilen gegen 53–65 bei den vierzehn davor. Der Zuwachs ist aber nicht das Template,
  sondern der Inhalt, den die kurzen Specs nicht hatten und der Bau dann erfand (§4.3:
  3–10 Zusatzentscheidungen je Report). Das Template verschiebt Entscheidungen von der
  Bauzeit in die Spec — und es verlangt `Annahme:` für alles, was es nicht weiß, statt
  Zeilen zu füllen.
- **„`lint_spec` ist Zeremonie für ein Dokument, das ein Mensch liest."** Zwei
  Skripte lesen es auch (`spec_eval_table`, künftig `lint_skill.py`s Nachbarn-Regel
  über die Abgrenzung). Und der Lint prüft nur Form, die in einer Sekunde sichtbar
  ist; er ersetzt den Review nicht, er spart ihm die Formfunde.
- **„Das ist wieder Konventions-Dokument statt Skill"** — ja, mit Absicht: Spec 00
  hat das Muster für Konventionen, die driften würden, genau so entschieden, und
  `impl-plan` hat gezeigt, dass Template plus Lint beim Konsumenten zwei Drittel des
  Werts bringt. Der Rest wäre der Dialog, und den gibt es.
- **Selbstbezug:** Die Ergänzungen an `skill-forge` sind eine Skill-Änderung und
  laufen durch `lint_skill.py`; `spec-brief.md` und das Spec-Template tragen die
  Kopfzeile (das Spec-Template darf sie tragen, es beginnt nicht mit Frontmatter — die
  Ausnahme für das SKILL.md-Gerüst lebt in der Regel `asset-headers` des Lints, nicht in
  `artifact-header.md`, dessen drei Ausnahmen `handoff.md`, die Stubs und die Anki-CSV
  sind).

## 9 · Empfehlung und Reihenfolge

1. **Sofort, ohne Spec:** `references/spec-reviewer-prompt.md` in `skill-forge` aus
   den drei Commit-Bodies destillieren; Schritt 1 des Ablaufs um „1b Review der Spec
   durch einen Subagenten mit frischem Kontext, Behauptungen nachgemessen" erweitern;
   die sieben „brainstorming"-Nennungen um „(die eigene, nicht superpowers)" ergänzen.
   Ein Nachmittag, eine Skill-Änderung; `evals_due` bleibt dabei `false`, weil ein
   Ablaufschritt weder Frontmatter noch Contract berührt — Evals werden erst fällig,
   wenn der Contract den Satz „kein Fertig ohne Spec-Review" bekommt, und dann gehört
   ein sechster Eval dazu (Spec ohne Vermerk → Übergabe sagt „ungeprüft").
2. **Danach:** `assets/spec-template.md` und `references/spec-brief.md` in
   `skill-forge`; `lint_spec` in `plan_to_tasks.py` bei `subagent-dev` mit
   Nummern-Cutoff und Review-Vermerk. Ein Vormittag Tier-1-Code plus ein Repo-Test, der
   alle Specs ≥ 18 lintet. Zwei Folgerunden (`skill-forge`, `subagent-dev`), keine
   Spec — der Contract-Satz aus Punkt 1 ist die einzige Contract-Änderung, und die
   trägt ihren Eval selbst.
3. **Beobachten:** Die nächste Spec (18 oder was kommt) mit den Eingabedateien
   brainstormen und messen, wie viele Review-Funde der Faktenklasse bleiben. Bleibt
   die Zahl in der Größenordnung der 23 von Spec 16, ist der Review das eigentliche
   Instrument und die Eingaben sind Zeremonie; fällt sie unter fünf, hat das Template
   gewirkt.
4. **Nicht tun:** die vierzehn alten Specs auf das Template heben (keine Konsumenten);
   superpowers' Router oder Browser-Begleiter nachbauen; eine dritte
   Brainstorming-Skill installieren.

### Skizze `skill-spec`, falls Punkt 3 dafür spricht

Absichtlich kurz — Eingabe für `brainstorming`, keine Spec.

**Problem.** Skill-Specs entstehen im Dialog mit einer Skill, die die Hausmethode nicht
kennt; drei von drei geprüften Specs brauchten eine Überarbeitung von einem Fünftel
ihrer Zeilen, jede aus Behauptungen über das Repo, die niemand gemessen hatte.

**Constraints.** Kein Nachbau des Dialogs: Optionen, Notausgang und Selbst-Review
bleiben Zitat aus der eigenen `brainstorming`. Tier 1 (`lint_spec`). Ablage `specs/`
bleibt. Anti-Zeremonie: eine Entscheidung nachtragen heißt Lint und Commit.

**Approach.** Ablauf: messen (Nachbarn, Matrix, known-limits, Assertion-Typen) → eine
Fragerunde (Tier, Gate, Anti-Zeremonie-Fall, zwei Konkurrenten) → Spec nach Template →
`lint_spec` → Review mit Nachmessen → Übergabe an `impl-plan`. Evals: (1)
Anti-Zeremonie: Entscheidung nachtragen → nur Lint, kein Review-Artefakt. (2) Spec ohne
Abgrenzung → Lint meldet, Übergabe sagt „ungeprüft". (3) Eval-Zeile mit
Zwei-Lauf-Vergleich → Review-Liste nennt sie blockierend. (4) Routing: „Spec für eine
neue Skill" → Datei unter `specs/` mit Kopfzeile und Eval-Tabelle, nicht unter
`docs/superpowers/specs/`.

**Abgrenzung.** `brainstorming` (eigene) für alles außerhalb dieser Sammlung;
`feature-spec` für Features mit Given/When/Then; `impl-plan` konsumiert.

## 10 · Was nicht geprüft wurde

- Keine Evals gefahren; welche der beiden `brainstorming`-Skills auf dem Rechner des
  Nutzers bei welchem Wortlaut lädt, ist nicht gemessen — die Kollision ist aus den
  Descriptions geschlossen.
- Die Review-Fundzahl zu Spec 17 ist nicht protokolliert; die Zeilenzahlen des Diffs
  sind gemessen, die Verteilung auf Fakten- und Konsistenzklasse ist es nur für 15
  und 16.
- Die Zählung „3–10 Zusatzentscheidungen je Report" ist eine Heuristik über
  Überschriften mit „Entscheidung" oder „Abweichung" und fette Einträge darunter; die
  Größenordnung stimmt nach Lektüre von vier Reports, die Einzelzahlen nicht sicher.
- Ob die Specs 01–14 vor dem Import bereinigt wurden (Spec 00s „Blocker"-Befund),
  zeigt die Historie nicht; die Zählung gilt dem heutigen Text.
- Dass die Specs 01–14 in claude.ai entstanden, ist aus dem escapten Markdown
  geschlossen, nicht beobachtet. Dass dort die eigene `brainstorming`-Skill das
  Template lieferte, ist die naheliegende, nicht die einzige Erklärung: Eine
  Projektanweisung oder eine frühere Fassung der Skill könnte dieselben sieben
  Abschnitte vorgegeben haben; das Repo zeigt nur das Änderungsdatum der Skill. Dass
  15–17 mit der eigenen Skill entstanden, folgt daraus, dass im Container nur sie
  installiert ist; für die Session zu Spec 15 ist das nicht geprüft. Dass die drei
  Brainstormings mit einer Fragerunde auskamen, ist Erinnerung an die Sessions, kein
  Repo-Befund.
- Die Zahlenvergleiche vor/nach Review (§4.1, letzte Spalte) hängen an der Zählregel
  für „Zahl im Text"; eine andere Regex liefert für Spec 16 statt 17→24 etwa 18→24.
  Die Richtung ist stabil, die Einzelwerte nicht.
- Die Aufwandsschätzungen sind Erfahrungswerte aus den Folgerunden dieses Repos, keine
  Telemetrie.
- Die Vorgänger-Prüfung, auf die §6 verweist, liegt weiter nur auf ihrem Branch
  (`claude/assessment-writing-skills-plans`); Spec 16, Spec 17 und
  `skill-forge/references/checklist.md` zitieren sie.
