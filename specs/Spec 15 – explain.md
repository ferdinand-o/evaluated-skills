# Spec 15: explain — Erklärungen mit Kurzantwort-Vertrag und Tiefenregler

Skill-Spezifikation · Zyklus 15 · Entscheidung: eine Skill, web-only, Tier 0, zustandslos · Abgeglichen mit Spec 00

## Problem

„Erklär mir X" ist die häufigste Anfrage überhaupt und die einzige ohne Vertrag. Die Antwort schwankt zwischen einem Einzeiler, der den entscheidenden Vorbehalt weglässt, und einer Textwand, in der die eigentliche Antwort erst im vierten Absatz steht. Der Nutzer hat keinen Regler: Er bekommt die Standardlänge des Modells, unabhängig davon, ob er sich orientieren oder in die Tiefe will.

Schwerer wiegt die zweite Lücke. Wenn das Modell etwas nicht sicher weiß, klingt das im Text genauso wie sicheres Wissen — nur weicher. „Typischerweise", „in der Regel", „kann unter Umständen" tarnen eine Wissenslücke als Differenziertheit. Der Leser kann Gewissheit und Vermutung nicht auseinanderhalten, und genau das ist der Unterschied, der zählt.

## Constraints

Reine Web-Skill: claude.ai und Cowork sind das Zielsystem, nicht Claude Code. Daraus folgt **Tier 0** (Spec 00 §3): kein Skript, keine Shell, kein Dateizugriff — die Skill läuft überall identisch, und es gibt keinen Degradationspfad, weil es nichts zu degradieren gibt. **Zustandslos:** keine eigene Memory-Datei, keine Historie, kein Update-Contract.

Code- und Repo-Erklärungen sind **ausdrücklich draußen** und gehören spezialisierten Skills. Damit entfällt die Kollision mit `architecture-map`, das wörtlich auf „erklär mir die Architektur" triggert.

Portables Frontmatter (`name`, `description`). SKILL.md ≤ 150 Zeilen, alles Weitere in `references/`. Pflicht-Anti-Zeremonie-Eval nach Spec 00 §2.

## Approach

**Die Kurzantwort ist der Vertrag; `effort` skaliert nur, was danach kommt.**

Der Aufruf: `/explain <Thema> [effort] [Kontext]`. Ohne Angabe gilt `medium`. Der dritte Parameter bindet die Erklärung an vorliegendes Material — ein angehängtes Dokument, einen zitierten Absatz, den bisherigen Gesprächsverlauf.

**Skill-Struktur:**

```
explain/
├── SKILL.md               (Antwortform, Effort-Tabelle, Ehrlichkeitsregeln, Abgrenzung)
└── references/
    ├── effort-ladder.md   (die fünf Stufen mit beobachtbaren Definitionen)
    └── honesty.md         (Marker-Wortlaut, Quellen-Priorität, Routing an verified-research)
```

### Antwortform (fest, drei Teile)

1. **Kurzantwort** — zwei bis vier Sätze. **Auf jeder Effort-Stufe identisch kurz.** Vollständig korrekt: Ein Vorbehalt, ohne den die Aussage falsch wäre, gehört hierher, nicht in Teil 2. „Es kommt darauf an" ist keine Kurzantwort, sondern deren Vermeidung — wenn es wirklich darauf ankommt, steht hier, worauf.
2. **Ausführung** — Umfang nach Effort, siehe Tabelle. Entfällt bei `low` nicht, ist dort aber ein Absatz.
3. **Anschluss** — höchstens **zwei benannte** Themen, die sachlich als Nächstes kommen, plus das Angebot, in einen Punkt der Antwort tiefer zu gehen. Nie eine Optionsliste, nie ein generisches „möchtest du mehr wissen?".

### Effort-Leiter

Die Stufen sind kumulativ: Jede enthält alles Vorherige und fügt eine Schicht hinzu.

| Stufe | Teil 2 enthält zusätzlich | Recherche bei Unsicherheit |
| --- | --- | --- |
| `low` | ein Absatz: der Mechanismus, sonst nichts | nein — nur markieren |
| `medium` (Default) | warum es so gebaut ist; ein durchgerechnetes Beispiel | nein — nur markieren |
| `high` | Randfälle, verbreitete Missverständnisse, Geltungsgrenzen | ja |
| `xhigh` | konkurrierende Modelle/Ansätze und ihre Abwägung | ja |
| `max` | Herkunft und Entwicklung, offene Streitfragen, Primärquellen | ja |

Der Regler steuert damit zwei Dinge zugleich — Untersuchungsaufwand und Ausgabetiefe — aber **nie die Kurzantwort**. Ein `max`-Aufruf beginnt mit denselben drei Sätzen wie ein `low`-Aufruf.

### Ehrlichkeitsregeln

Zwei **wörtlich mandatierte Marker**, damit die Regel prüfbar ist und nicht nur appelliert (dasselbe Muster wie learning-coachs „Keine verifizierten Aufgaben gefunden"):

- `Unverified:` — Aussage aus dem Gedächtnis, nicht belegt.
- `Source:` — nachgeschlagen, Quelle in derselben Zeile.

Die Marker sind **feste englische Tokens, unabhängig von der Antwortsprache** — eine deutsche Erklärung trägt dieselben Marker wie eine englische. Das ist bewusst inkonsequent gegenüber dem Fließtext und der Preis dafür, dass eine einzige `output_matches`-Assertion in jeder Sprache greift; eine übersetzte Pflichtphrase wäre in genau dem Moment nicht mehr prüfbar, in dem die Skill die Sprache wechselt.

**Warum nicht `Verified:`** als Gegenstück: Das Wort ist in dieser Sammlung bereits zweifach belegt — `verified-research` meint damit Tier-1/2-Provenienz mit Stichprobenprüfung, `exercise-forge` einen bestandenen Blind-Gate-Lauf. Ein drittes, deutlich schwächeres „verified" (jemand hat einmal nachgeschlagen) würde dieselbe Bedeutungs-Drift erzeugen, die zwischen learning-coach und exercise-forge bereits zwei Fix-Runden gekostet hat. `Source:` behauptet nur, was es einlöst.

Verboten ist **Hedging als Ersatz für einen Marker**: eine Formulierung weichzuspülen — „typischerweise", „in der Regel", „kann unter Umständen", „generally", „tends to", „in most cases" —, statt die Unsicherheit zu benennen. Weichgespülte Sprache ist der Normalzustand, den diese Regel ersetzt; sie ist der eigentliche Zweck der Skill, nicht ein Zusatz.

Bei Recherche gilt eine feste **Quellen-Priorität**: Primärquelle (Spezifikation, offizielle Dokumentation, Originalarbeit, Gesetzestext) → belastbare Sekundärquelle → alles andere. Nie zitieren, was nicht tatsächlich geöffnet wurde. Das Tier-Vokabular ist von `verified-research` geborgt, damit beide Skills dieselbe Sprache sprechen — **ohne** deren Quellenregister, Stichprobenprüfung und Wissensdatei.

**Routing statt schwacher Kopie:** Braucht eine Frage Provenienz, die einer Prüfung standhält — regulatorisch, medizinisch, juristisch, finanziell —, sagt `explain` das und verweist auf `verified-research`, statt eine leichtgewichtige Version davon zu liefern.

### Anti-Rationalisierung (Auszug)

| Gedanke | Realität |
| --- | --- |
| „Bei `max` darf die Kurzantwort ausführlicher sein" | Nein. Teil 1 ist über alle Stufen identisch kurz — das ist der Vertrag, nicht eine Voreinstellung. |
| „Ich bin mir nicht ganz sicher, ich formuliere es vorsichtiger" | Genau das ist verboten. Vorsichtige Formulierung ist kein Marker; `Unverified:` ist einer. |
| „Die Antwort ist deutsch, ich übersetze den Marker mit" | Nein — die Marker sind feste Tokens in jeder Sprache. Übersetzt sind sie nicht mehr prüfbar. |
| „Die Frage ist zu simpel für drei Teile" | Dann ist Teil 2 ein Absatz und Teil 3 eine Zeile. Die Form bleibt, der Umfang schrumpft. |
| „Ich liste mal alle möglichen Anschlussthemen auf" | Höchstens zwei, benannt. Eine Auswahlliste ist Zeremonie, keine Hilfe. |
| „`low` heißt, ich darf ungenau sein" | `low` steuert den Umfang, nie die Korrektheit. Eine kurze Antwort ist keine ungefähre. |

### Abgrenzung

| Anlass | zuständig | nicht |
| --- | --- | --- |
| Konzept/Thema erklären (Allgemeinwissen, Theorie) | **explain (15)** | learning-coach (Session), visual-summary (Verdichtung) |
| Codebase, Architektur, Abhängigkeiten | architecture-map (10), `/code-review` | explain |
| Strukturierte Lernsession mit Abruf und Spacing | learning-coach (14) | explain |
| Vorliegendes Dokument verdichten | visual-summary (11) | explain |
| Recherche mit Provenienzanspruch | verified-research (12) | explain |

`learning-coach`s Description endet heute mit „Reines ‚erklär mir X' ohne Session-Struktur ist ein normales Gespräch, keine learning-coach-Session". Dieser Satz muss beim Bau auf `explain` zeigen — sonst bleibt die Lücke unbesetzt beschrieben, obwohl sie besetzt ist. Ebenso bekommt Spec 00 §5 eine Zeile in der zentralen Routing-Matrix.

Am Ende einer Erklärung steht **ein** optionaler Übergabesatz: „Soll ich das als Thema in deinen Lernstand aufnehmen?" → `learning-coach` legt es mit Grad 0 an. Erklärt bekommen ist dort ausdrücklich noch nicht gelernt. Das ist ein Angebot, kein Dateibesitz — `explain` schreibt nichts.

### Evals

1. **Anti-Zeremonie (Pflicht):** eine triviale Frage mit `low` — bleibt die Antwort kurz, ohne ausgewalzte Struktur und ohne Marker-Overhead?
2. **Kurzteil-Invarianz:** dieselbe Frage einmal mit `low`, einmal mit `max` — ist Teil 1 in beiden Läufen gleich knapp, während Teil 2 wächst? (Judge)
3. **Marker statt Hedging:** eine Frage nach einem zeitkritischen Detail hinter dem Wissensstand, mit `low` (also ohne Recherche) — erscheint `Unverified:` wörtlich, statt dass die Aussage weichgespült wird? (mechanisch, `output_matches`)
4. **Effort-Recherche-Kopplung:** dieselbe Frage mit `high` — wird recherchiert und mit `Source:` samt Quelle belegt? Ein zweiter Lauf mit derselben Frage auf Englisch prüft, dass der Marker-Wortlaut sprachunabhängig gleich bleibt.
5. **Abgrenzung:** „erklär mir die Architektur von diesem Projekt" — übernimmt `explain` **nicht**, sondern verweist auf die zuständige Skill? (Judge)

## Alternatives considered

**Zwei Skills (`explain-code`, `explain-topic`).** Der ursprüngliche Gedanke. Hinfällig, sobald Code aus dem Scope fällt — und schon vorher schwach: zwei fast identische Descriptions hätten auf dieselben Wörter getriggert, und der Nutzer hätte eine Unterscheidung treffen müssen, die das System zuverlässiger trifft.

**Eine Skill mit Codebase-Modus und mechanischem Zitat-Gate** (`check_citations.py` prüft, dass jede `datei:zeile`-Angabe existiert). Inhaltlich der stärkste Entwurf, weil er der Skill ein echtes Gate gegeben hätte statt nur Doktrin. Verworfen mit der Web-only-Entscheidung: Im Zielsystem gibt es keine Shell, das Gate wäre tot geboren.

**Nur ein Slash-Command statt einer Skill.** Passt zur Natur der Sache (ein Ausgabevertrag ist genau das, was ein Command gut kann), scheitert aber am Zielsystem — Commands gibt es in claude.ai/Cowork nicht.

**Eigene Memory-Datei für `explain`.** Verworfen aus drei Gründen: Sie erzwingt wieder einen Tier-0-Sonderpfad im Web; sie macht den trivialen Fall (`/explain X low`) zeremoniell; und „was weiß diese Person schon" gehört bereits `learner.md`. Ein zweiter Speicher mit überlappender Bedeutung ist der Fehler, der zwischen learning-coach und exercise-forge zweimal aufgetreten ist.

**Effort steuert nur die Ausgabelänge.** Verworfen: Dann kostet `max` genauso wenig Arbeit wie `low`, und der Name lügt.

## Out of scope

Code-, Repo- und Architekturerklärungen jeder Art. Eigene Persistenz. Gerendertes HTML oder Artifacts (das ist `visual-summary`). Übungsaufgaben und Abfragen (`exercise-forge`, `learning-coach`). Vollwertige Recherche mit Quellenregister und Stichprobenprüfung (`verified-research`). Ein Skript — die Skill ist bewusst Tier 0.

## Open questions

**Die Selbsteinschätzung der Unsicherheit ist die schwächste Stelle, und sie ist nicht gelöst.** Die ganze Ehrlichkeitsregel steht und fällt damit, dass das Modell erkennt, wann es unsicher ist — und genau das ist bekanntlich das, was Sprachmodelle am schlechtesten können. Die Durchsetzung ist reine **G1-Selbstauskunft** (Spec 00 §4): Die SKILL.md verlangt den Marker, nichts erzwingt ihn. Bei einer Tier-0-Skill gibt es kein Gate, das die Lücke schließen könnte. Eval 3 misst das Verhalten stichprobenartig, beweist es aber nicht. Wer diese Skill baut, sollte das nicht wegformulieren: Sie ist ein Ausgabevertrag mit einer ehrlichen Grenze, kein Wahrheitsmechanismus.

**Marker im deutschen Fließtext.** Entschieden: feste englische Tokens (`Unverified:`, `Source:`) unabhängig von der Antwortsprache, damit eine Assertion in jeder Sprache greift. Offen bleibt, ob das in einer sonst durchgehend deutschen Antwort als Fremdkörper stört. Falls ja, ist die Alternative kein übersetzter Marker (dann ist die Prüfbarkeit weg), sondern ein sprachneutrales Zeichen — was die Lesbarkeit schlechter macht als beides. Eval 3 misst die Prüfbarkeit, nicht die Ästhetik; das entscheidet der erste echte Gebrauch.

**Default-Effort `medium`: bestätigt.** `/code-review` löst dasselbe Problem anders (es merkt sich die zuletzt genannte Stufe), was hier mangels Persistenz nicht geht.

**Verhältnis zu Teil 3 bei `low`.** Ob der Anschluss-Teil auf der niedrigsten Stufe ganz entfallen sollte, entscheidet Eval 1 — wenn er dort als Zeremonie auffällt, wird er auf `medium` aufwärts beschränkt.

## Next steps

`references/honesty.md` zuerst — Marker (`Unverified:`, `Source:`) und Quellen-Priorität sind der Kern und legen die `output_matches`-Muster von Eval 3 und 4 fest. Danach `effort-ladder.md` mit beobachtbaren Stufendefinitionen (nicht „ausführlicher", sondern „enthält zusätzlich X"). SKILL.md zuletzt, damit sie auf fertige Referenzen zeigt. Eval 1 und 3 zuerst fahren: der Anti-Zeremonie-Fall und der Marker-Fall prüfen die zwei Zusagen, die diese Skill überhaupt von einem normalen Gespräch unterscheiden. Beim Bau mitziehen: `learning-coach`s Abgrenzungssatz und die Routing-Matrix in Spec 00 §5.
