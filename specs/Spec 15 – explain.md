# Spec 15: explain — Erklärungen mit Kurzantwort-Vertrag und Tiefenregler

Skill-Spezifikation · Zyklus 15 · Entscheidung: eine Skill, web-only, Tier 0, zustandslos · Abgeglichen mit Spec 00 · Überarbeitet nach unabhängigem Review

## Problem

„Erklär mir X" ist die häufigste Anfrage überhaupt und die einzige ohne Vertrag. Die Antwort schwankt zwischen einem Einzeiler, der den entscheidenden Vorbehalt weglässt, und einer Textwand, in der die eigentliche Antwort erst im vierten Absatz steht. Der Nutzer hat keinen Regler: Er bekommt die Standardlänge des Modells, unabhängig davon, ob er sich orientieren oder in die Tiefe will.

Schwerer wiegt die zweite Lücke. Wenn das Modell etwas nicht sicher weiß, klingt das im Text genauso wie sicheres Wissen — nur weicher. „Typischerweise", „in der Regel", „kann unter Umständen" tarnen eine Wissenslücke als Differenziertheit. Der Leser kann Gewissheit und Vermutung nicht auseinanderhalten, und genau das ist der Unterschied, der zählt.

## Constraints

Reine Web-Skill: claude.ai und Cowork sind das Zielsystem, nicht Claude Code. Daraus folgt **Tier 0** (Spec 00 §3): kein Skript, keine Shell, kein Dateizugriff. **Zustandslos:** keine eigene Memory-Datei, keine Historie, kein Update-Contract.

Code- und Repo-Erklärungen sind **ausdrücklich draußen** und gehören spezialisierten Skills. Das löst die Konkurrenz zu `architecture-map` allerdings **nicht** auf: Ausgewählt wird nach Descriptions, und `architecture-map` führt „erklär mir die Architektur" wörtlich als Trigger (`skills/architecture-map/SKILL.md:3`). Eine Skill namens `explain` konkurriert genau auf diesem Wort. Die Kollision bleibt, ist auf Description-Ebene nicht auflösbar und wird nur stichprobenartig gemessen (Eval 8) — ein einzelner grüner Lauf beweist dort nichts (`docs/known-limits.md`, „Ein Eval-Ergebnis ist eine Stichprobe").

Portables Frontmatter (`name`, `description`). SKILL.md ≤ 150 Zeilen, alles Weitere in `references/`. Pflicht-Anti-Zeremonie-Eval nach Spec 00 §2.

## Approach

**Die Kurzantwort ist der Vertrag; `effort` skaliert nur, was danach kommt.**

**Aufruf.** Primär natürlichsprachlich — „erklär mir X", „erklär mir X ausführlich", „erklär mir X in aller Tiefe". Die Stufe wird aus der Formulierung erkannt; ohne Hinweis gilt `medium`. Die Schreibweise `/explain <Thema> <effort>` ist eine Kurzform für Umgebungen, die Slash-Aufrufe kennen — im Zielsystem claude.ai/Cowork gibt es sie nicht, deshalb darf keine Regel der Skill sie voraussetzen. `references/effort-ladder.md` legt fest, welche Formulierungen welche Stufe auslösen und was bei Mehrdeutigkeit gilt (im Zweifel die niedrigere Stufe, und die gewählte Stufe wird genannt).

**Skill-Struktur:**

```
skills/explain/
├── SKILL.md               (Antwortform, Effort-Tabelle, Ehrlichkeitsregeln, Abgrenzung)
└── references/
    ├── honesty.md         (Marker-Geltungsbereich, Hedging, Quellen-Priorität, Routing)
    └── effort-ladder.md   (fünf Stufen, je beobachtbar definiert; Stufenerkennung)

evals/explain/evals.json
```

### Antwortform

1. **Kurzantwort** — höchstens **vier Sätze**, ohne Überschrift, auf jeder Effort-Stufe gleich knapp. Sie enthält kein Beispiel, keinen Randfall und keine Quellenangabe. Vollständig korrekt: Ein Vorbehalt, ohne den die Aussage falsch wäre, gehört hierher. „Es kommt darauf an" ist keine Kurzantwort, sondern deren Vermeidung — wenn es darauf ankommt, steht hier, worauf.
2. **Ausführung** — Umfang nach Effort, siehe Tabelle.
3. **Anschluss** — beginnt mit der wörtlichen Zeile `Next:` und nennt **höchstens zwei** benannte Themen, die sachlich als Nächstes kommen. **Entfällt bei `low` ersatzlos.** Nie eine Optionsliste, nie ein generisches „möchtest du mehr wissen?".

`Next:` ist wörtlich mandatiert und wie die Marker ein fester englischer Token. Das ist kein Layout-Detail, sondern der einzige Anker, an dem sich Anwesenheit und Abwesenheit des Anschluss-Teils mechanisch prüfen lassen — und damit das einzige Merkmal, an dem ein Eval `explain` von einer beliebigen guten Antwort unterscheiden kann (`docs/known-limits.md`, „Assertions müssen an Artefakten hängen, die *nur* die getestete Skill erzeugt").

### Effort-Leiter

Kumulativ: Jede Stufe enthält alles Vorherige und fügt eine Schicht hinzu.

| Stufe | Teil 2 enthält zusätzlich | Teil 3 | Recherche |
| --- | --- | --- | --- |
| `low` | ein Absatz: der Mechanismus, sonst nichts | entfällt | nein — nur markieren |
| `medium` (Default) | warum es so gebaut ist; ein durchgerechnetes Beispiel | ja | nein — nur markieren |
| `high` | Randfälle, verbreitete Missverständnisse, Geltungsgrenzen | ja | ja |
| `xhigh` | konkurrierende Modelle/Ansätze und die Abwägung zwischen ihnen | ja | ja |
| `max` | Herkunft, Entwicklung, offene Streitfragen, Primärquellen | ja | ja |

Der Regler steuert Untersuchungsaufwand **und** Ausgabetiefe — aber nie die Kurzantwort. Ein `max`-Aufruf beginnt so knapp wie ein `low`-Aufruf; identisch im Wortlaut sind sie nicht (Sampling), gleich knapp schon.

`xhigh` ist bewusst beibehalten, obwohl sonst keine Skill dieser Sammlung fünf Stufen führt: Es ist eine reale Claude-Effort-Stufe und war ausdrücklich angefragt. Die Trennung zu `max` muss `effort-ladder.md` scharf genug ziehen, dass ein Judge zwei Antworten allein anhand der Definition zuordnen könnte — `xhigh` diskutiert konkurrierende **Erklärungen desselben Gegenstands**, `max` dessen **Geschichte und Quellenlage**. Trägt die Trennung das nicht, fällt `xhigh` beim Bau weg.

### Ehrlichkeitsregeln

**Geltungsbereich der Marker — die Grundregel:** Eine unmarkierte Aussage behauptet Gewissheit. Das ist der Normalfall und wird nicht eigens ausgewiesen. Ein Marker steht genau vor den Aussagen, für die das nicht gilt:

- `Unverified:` — aus dem Gedächtnis, nicht belegt, nicht sicher.
- `Source:` — nachgeschlagen, Quelle in derselben Zeile.

Daraus folgt für Teil 1: **Die Kurzantwort trägt nie einen Marker.** Sie enthält nur, was die Skill als gesichert vertreten kann. Ist zur gestellten Frage nichts Gesichertes verfügbar, sagt Teil 1 genau das in einem Satz — das ist die Antwort, keine Ausrede.

Das **Hedging-Verbot**: eine Formulierung weichzuspülen — „typischerweise", „in der Regel", „kann unter Umständen", „generally", „tends to", „in most cases" —, statt die Unsicherheit zu benennen. Statistische Aussagen dürfen diese Wörter benutzen; verboten ist der Gebrauch **als Ersatz für einen Marker**. Diese Regel ist der eigentliche Zweck der Skill — und sie ist **G1 (Selbstauskunft, Spec 00 §4)**: Die SKILL.md verlangt sie, nichts erzwingt sie.

**Warum nicht `Verified:`** als Gegenstück zu `Unverified:`: `verified-research` bezeichnet damit Tier-1/2-Provenienz mit Stichprobenprüfung, `exercise-forge` einen bestandenen Blind-Gate-Lauf. `Source:` behauptet nur, was es einlöst — jemand hat nachgeschlagen.

Bei Recherche gilt eine feste **Quellen-Priorität**: Primärquelle (Spezifikation, offizielle Dokumentation, Originalarbeit, Gesetzestext) → belastbare Sekundärquelle → alles andere. Nie zitieren, was nicht tatsächlich geöffnet wurde.

**Routing statt schwacher Kopie:** Braucht eine Frage Provenienz, die einer Prüfung standhält — regulatorisch, medizinisch, juristisch, finanziell —, sagt `explain` das und verweist auf `verified-research`.

**Was die Marker mechanisch leisten — und was nicht.** `output_matches` prüft **Anwesenheit** eines Tokens. Es kann nie feststellen, dass eine unsichere Aussage *ohne* Marker durchgegangen ist — und genau das ist der Fehlerfall, gegen den die Skill existiert. Prüfbar ist also, dass ein Marker auftaucht, wo einer hingehört; ungeprüft bleibt, ob überall einer steht, wo einer hingehörte.

### Anti-Rationalisierung (Auszug)

| Gedanke | Realität |
| --- | --- |
| „Bei `max` darf die Kurzantwort ausführlicher sein" | Nein. Höchstens vier Sätze auf jeder Stufe — das ist der Vertrag, keine Voreinstellung. |
| „Ich bin mir nicht ganz sicher, ich formuliere es vorsichtiger" | Genau das ist verboten. Vorsichtige Formulierung ist kein Marker; `Unverified:` ist einer. |
| „Ich bin sicher genug, das braucht keinen Marker" | Dann ohne Marker — und du stehst für die Aussage gerade. Der unmarkierte Zustand ist eine Behauptung, kein Ausweichen. |
| „Die Antwort ist deutsch, ich übersetze Marker und `Next:` mit" | Nein — feste Tokens in jeder Sprache. Übersetzt sind sie nicht mehr prüfbar. |
| „Die Frage ist simpel, ich lasse die Form trotzdem stehen" | Bei `low` entfällt Teil 3 ersatzlos und Teil 2 ist ein Absatz. Vollständige Form ab `medium`. |
| „Ich liste alle möglichen Anschlussthemen auf" | Höchstens zwei, benannt. Eine Auswahlliste ist Zeremonie, keine Hilfe. |
| „`low` heißt, ich darf ungenau sein" | `low` steuert den Umfang, nie die Korrektheit. Eine kurze Antwort ist keine ungefähre. |

### Abgrenzung

| Anlass | zuständig | nicht |
| --- | --- | --- |
| Konzept/Thema erklären (Allgemeinwissen, Theorie) | **explain (15)** | learning-coach (Session), visual-summary (Verdichtung) |
| Codebase, Architektur, Abhängigkeiten | architecture-map (10), `/code-review` | explain |
| Strukturierte Lernsession mit Abruf und Spacing | learning-coach (14) | explain |
| Vorliegendes Dokument verdichten | visual-summary (11) | explain |
| Recherche mit Provenienzanspruch | verified-research (12) | explain |

`learning-coach`s Description endet heute mit dem Satz „Not a tutor that explains on demand without structure — if you just want an explanation, that's a normal conversation." (`skills/learning-coach/SKILL.md:3`, englisch wie die ganze Description). Er muss beim Bau auf `explain` zeigen, ebenfalls auf Englisch. Die Routing-Matrix steht an **zwei** Orten: `specs/Spec 00 – skill-foundation.md` §5 und `README.md` — beide brauchen eine Zeile.

Am Ende einer Erklärung steht **ein** optionaler Übergabesatz Richtung `learning-coach`. `explain` schreibt dabei nichts und darf keinen Beherrschungsgrad zusagen: Grad 0 heißt dort „nie gesehen" (`skills/learning-coach/references/learner-schema.md`), was auf ein gerade erklärtes Thema nicht zutrifft. Der Satz nennt deshalb nur den Themennamen und überlässt Einstufung und Anlage `learning-coach`.

### Evals

Alle Evals fahren ohne Fixture-Dateien der Skill selbst (`empty-dir`, `{"git": false}`), außer wo anders vermerkt. Jeder Eval beantwortet in `notes` die Diskriminator-Frage: **Könnte das Basismodell ohne diese Skill dieselbe Ausgabe erzeugen?** Wo die Antwort „ja" lautet, ist der Eval wertlos und wird umgebaut.

| # | id | Klasse | Prüft | Mechanismus |
| --- | --- | --- | --- | --- |
| 1 | `anti-ceremony-trivial-low-stays-bare` | behavior | Pflicht-Anti-Zeremonie: triviale Frage, `low` | `must_not: output_matches "Next:"` plus **ein** Judge-Claim mit Zahl („höchstens sechs Sätze insgesamt, keine Zwischenüberschriften") |
| 2 | `medium-answer-carries-next-block` | contract | dieselbe Frage, `medium` | `output_matches "Next:"` |
| 3 | `short-answer-stays-bare-at-max` | behavior | Kurzantwort-Invarianz | Judge: „Vor dem ersten Absatzumbruch stehen höchstens vier Sätze, ohne Beispiel, Randfall oder Quellenangabe" |
| 4 | `uncertainty-is-marked` | contract | Marker statt Schweigen, `low` | `output_matches "Unverified:"` |
| 5 | `hedging-is-not-a-substitute` | behavior | derselbe Prompt | Judge: „Die Unsicherheit ist mit dem Marker benannt, nicht in abschwächende Formulierungen verlegt" |
| 6 | `high-effort-cites-a-source` | contract | Recherche-Kopplung, `high` | `output_matches "Source:"`, Fixture mit lokalen Quellen |
| 7 | `marker-token-is-language-independent` | contract | englischer Prompt | `output_matches "Unverified:"` |
| 8 | `codebase-question-is-routed-away` | behavior | Abgrenzung | Fixture `layered-service`; Judge, ein Claim |

Vier Konstruktionsregeln, die aus dem Harness folgen und nicht verhandelbar sind:

- **Ein Eval, ein Prompt** (`evalkit/schema.py`). Jeder Vergleich zweier Stufen zerfällt in zwei Evals mit je einer Assertion; ein Vergleich innerhalb eines Prompts wäre wertlos, weil das Modell seine eigene erste Antwort im Kontext sieht und kopiert.
- **Ein Judge-Claim pro Eval.** Zusammengesetzte Claims sind im Repo nachweislich unzuverlässig (`docs/known-limits.md`, Abschnitt „Judge").
- **Kürze ist nicht mechanisch messbar.** Es gibt kein `output_max_lines`; `file_max_lines` greift nur auf Dateien, und diese Skill erzeugt keine. Eval 1 stützt sich deshalb auf die *Abwesenheit* von `Next:` — das ist der harte Teil — plus einen Judge-Claim mit Zahl für den Rest.
- **Eval 6 misst keine echte Recherche.** Kein Eval dieses Repos geht ins Netz; `verified-research` verbietet Websuche in allen seinen Prompts und arbeitet mit lokalen Quellen-Fixtures. Eval 6 folgt diesem Muster. Gemessen wird die Marker-Disziplin bei verfügbarer Quelle, nicht die Recherchefähigkeit — Sichtbarkeitsregel Spec 00 §3.

## Alternatives considered

**Zwei Skills (`explain-code`, `explain-topic`).** Hinfällig, sobald Code aus dem Scope fällt — und schon vorher schwach: zwei fast identische Descriptions hätten auf dieselben Wörter getriggert.

**Eine Skill mit Codebase-Modus und mechanischem Zitat-Gate** (`check_citations.py` prüft, dass jede `datei:zeile`-Angabe existiert). Inhaltlich der stärkste Entwurf, weil er der Skill ein echtes Gate gegeben hätte. Verworfen mit der Web-only-Entscheidung: Im Zielsystem gibt es keine Shell.

**Nur ein Slash-Command statt einer Skill.** Scheitert am Zielsystem — Commands gibt es in claude.ai/Cowork nicht. Dieselbe Begründung streicht die Slash-Form als *primäre* Aufrufsyntax.

**Eigene Memory-Datei für `explain`.** Verworfen: Sie erzwingt einen Tier-0-Sonderpfad im Web, macht den trivialen Fall zeremoniell, und „was weiß diese Person schon" gehört bereits `learner.md` — eine zweite Datei mit derselben Bedeutung bräuchte eine geprüfte Verdrahtung zwischen beiden Eigentümern, und genau daran ist die Schnittstelle learning-coach ↔ exercise-forge zweimal gescheitert.

**Effort steuert nur die Ausgabelänge.** Verworfen: Dann kostet `max` genauso wenig Arbeit wie `low`, und der Name lügt.

**Vier Stufen wie `/code-review`.** Erwogen nach dem Review-Hinweis, dass `xhigh` sonst nirgends im Repo vorkommt. Beibehalten, weil `xhigh` eine reale Claude-Effort-Stufe und ausdrücklich angefragt ist — unter der Auflage, dass `effort-ladder.md` die Trennung zu `max` trägt.

## Out of scope

Code-, Repo- und Architekturerklärungen jeder Art. Eigene Persistenz. Gerendertes HTML oder Artifacts (`visual-summary`). Übungsaufgaben und Abfragen (`exercise-forge`, `learning-coach`). Vollwertige Recherche mit Quellenregister und Stichprobenprüfung (`verified-research`). Ein Skript — die Skill ist bewusst Tier 0.

## Open questions

**Die Selbsteinschätzung der Unsicherheit ist die schwächste Stelle, und sie ist nicht gelöst.** Die Ehrlichkeitsregel steht und fällt damit, dass das Modell erkennt, wann es unsicher ist — und das ist bekanntlich das, was Sprachmodelle am schlechtesten können. Die Durchsetzung ist reine G1-Selbstauskunft; bei einer Tier-0-Skill gibt es kein Gate, das die Lücke schließen könnte. Eval 4 und 5 messen stichprobenartig, beweisen nichts. Wer diese Skill baut, sollte das nicht wegformulieren: Sie ist ein Ausgabevertrag mit einer ehrlichen Grenze, kein Wahrheitsmechanismus.

**Das Zielsystem wird nie gemessen.** Die Skill ist für claude.ai/Cowork gedacht, der Eval-Harness fährt sie in Claude Code — mit Shell, Dateizugriff und fremden Skills im Kontext. Alle acht Evals belegen Verhalten *mit* verfügbaren Werkzeugen, nicht ohne. Dieselbe Grenze hat `learning-coach`s Tier-0-Pfad (`docs/known-limits.md`), dort für einen Teilpfad; hier für die ganze Skill. Nicht auflösbar mit dem heutigen Harness, deshalb benannt statt behauptet.

**`Next:` als Anker ist ein Kompromiss.** Der Token macht Anwesenheit und Abwesenheit des Anschluss-Teils prüfbar und ist das einzige Merkmal, das `explain` von einer guten Antwort ohne Skill unterscheidet. Er ist zugleich ein sichtbarer Fremdkörper in einer sonst fließenden Antwort. Wenn er sich im Gebrauch als störend erweist, entfällt mit ihm die mechanische Prüfbarkeit von Eval 1 und 2 — dann bleibt nur der Judge, und das ist ein echter Verlust, kein kosmetischer.

**Marker im deutschen Fließtext.** Feste englische Tokens, damit eine Assertion in jeder Sprache greift. Ob sie in einer durchgehend deutschen Antwort stören, entscheidet der erste echte Gebrauch. Die Alternative ist kein übersetzter Marker (dann ist die Prüfbarkeit weg), sondern ein sprachneutrales Zeichen — schlechter lesbar als beides.

**Default-Effort `medium`: bestätigt.** `/code-review` merkt sich stattdessen die zuletzt genannte Stufe, was hier mangels Persistenz nicht geht.

## Next steps

`references/honesty.md` zuerst — der Marker-Geltungsbereich legt die `output_matches`-Muster von Eval 4, 6 und 7 fest. Dann `effort-ladder.md`, wo sich entscheidet, ob `xhigh` trägt. SKILL.md zuletzt, damit sie auf fertige Referenzen zeigt. Evals parallel zu honesty.md, nicht danach: Sie sind bei einer Skill ohne Code das einzige Messinstrument. Beim Bau mitziehen: `learning-coach`s Abgrenzungssatz (englisch), die Routing-Matrix in Spec 00 §5 **und** in `README.md`.
