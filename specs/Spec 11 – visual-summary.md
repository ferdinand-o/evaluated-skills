# Spec 11: visual\-summary — Format\-Familie für Zusammenfassungen

Skill\-Spezifikation · Zyklus 11/14 · Entscheidung: alle Input\-Arten, HTML \+ Markdown als Doppel\-Renderer, eigenes Token\-Set · Abgeglichen mit Spec 00

## Problem

Zusammenfassungen sind heute Textwüsten oder überdesignte Einmal\-Artefakte: keine Format\-Grammatik (wann One\-Pager, wann Memo, wann Zeitstrahl), zufällige Informationshierarchie, Zahlen und Diagramme ohne Quellenbindung, und jedes Mal wird das Layout neu erfunden. Das Ergebnis wirkt beliebig und ist nicht wiedererkennbar — obwohl Zusammenfassen die häufigste wiederkehrende Wissensarbeit überhaupt ist.

## Constraints

Vier Input\-Arten: Dokumente/PDFs/Artikel, eigene Recherche\-Ergebnisse (Anschluss an Zyklus 12), Chat\-/Arbeitsverläufe, Code\-/Projektstände. Zwei Ausgabemedien aus einem Inhaltsmodell: gestyltes HTML (Token\-Set) und strukturgleiches, schmuckloses Markdown (Repo/Obsidian/Notizen). Eigenes visuelles Token\-Set (Farben, Typo, Abstände — analog enterprise\-ui\-tokens, einmal definiert). Abgrenzung: Periodische Projekt\-Reports gehören zu dev\-report (Spec 02); diese Skill übernimmt das Ad\-hoc\-„fass das zusammen". Portables Frontmatter.

## Approach

**Inhalt vor Medium: erst ein medienneutrales Inhaltsmodell, dann zwei Renderer.** So bleiben HTML und Markdown inhaltsgleich, und die Quellenbindung ist Teil des Modells statt des Layouts.

**Skill\-Struktur:**

```
visual-summary/
├── SKILL.md                (Triage, Format-Grammatik, Doktrin, Contract)
├── references/
│   ├── formats.md          (die vier Formate: wann welches, Aufbau, Längenbudget)
│   ├── evidence.md         (Quellenbindung: Claim→Ref-Regeln je Input-Art)
│   └── charts.md           (wann ein Chart, welcher Typ — schlank, verweist auf dataviz-Prinzipien)
├── assets/
│   ├── tokens.css          (persönliches Token-Set: Farben, Typo, Abstände, hell/dunkel)
│   ├── one-pager.html      (Executive-One-Pager: These, drei Belege, ein Chart)
│   ├── decision-memo.html  (Optionen-Matrix, Empfehlung, Risiken)
│   ├── timeline-brief.html (chronologische Entwicklung mit Wendepunkten)
│   ├── learn-card.html     (Konzept-Destillat: Kernidee, Beispiel, Abgrenzung, Merksatz)
│   └── md/                 (die vier Formate als Markdown-Skelette, strukturgleich)
└── evals/evals.json
```

**Triage (zwei Fragen, dann Entscheidung):** Wer liest es — und welche Entscheidung oder Handlung soll folgen? Daraus wählt die Skill Format und Medium: Entscheidung steht an → decision\-memo; Überblick für Dritte → one\-pager; Verlauf/Entwicklung → timeline\-brief; eigenes Lernen → learn\-card. Bildschirm/Teilen → HTML, Repo/Notizen → Markdown; auf Wunsch beides aus demselben Modell. Die Wahl wird in einer Zeile begründet ausgegeben — Format\-Wahl ist Teil des Outputs, nicht stilles Vorgehen.

**Inhaltsmodell (der Kern):** Vor jedem Rendern entsteht die Struktur: Kernthese (ein Satz — der TL;DR), Belege (je: Aussage, Quellenreferenz — Seite/Abschnitt/Commit/Nachricht je nach Input\-Art, Konfidenz), Datenpunkte (für Charts, mit Quelle), offene Punkte. Contract: **Keine Zahl und kein Chart ohne Quellenreferenz im Modell**; jede Aussage im gerenderten Output ist auf einen Modell\-Eintrag rückführbar; das Längenbudget des Formats ist hart (eine Seite heißt eine Seite — Kürzen ist Arbeit der Skill, nicht des Lesers).

**Renderer:** HTML\-Templates sind fertige, getestete Seiten mit tokens.css (selbstenthalten, hell/dunkel); Claude füllt Slots, statt Layout zu erfinden — dieselbe Asset\-Logik wie bei motion\-landing und enterprise\-ui. Markdown\-Skelette spiegeln die Struktur ohne Styling (Überschriften, Tabellen, Zitat\-Refs als Fußnoten). Charts im HTML inline (leichtgewichtig, aus den Datenpunkten generiert), im Markdown als Tabelle der Datenpunkte — nie als totes Bild.

**Abschlusstest (Selbst\-Audit):** Vor Lieferung prüft die Skill: Überlebt die Kernaussage, wenn der Leser nur Headline und Chart sieht? Ist jeder Beleg klickbar/auffindbar? Ist das Budget eingehalten? Bei HTML zusätzlich Layout\-Sichtprüfung (Screenshot ansehen).

**Anti\-Rationalisierungs\-Tabelle (Auszug):** „Mehr Details machen es wertvoller" → das Budget ist die Wertgrenze; Kürzen ist die Leistung. „Die Zahl stand irgendwo im Dokument" → ohne Fundstelle keine Zahl. „Ein schickes Diagramm wertet es auf" → ein Chart ohne Frage, die es beantwortet, fliegt (charts.md). „Format mische ich passend" → ein Format pro Output; Mischbedarf heißt: falsches Format gewählt.

**Evals:** (1) 40\-Seiten\-PDF mit einer versteckten Schlüsselzahl — landet sie als These\-Beleg mit Seitenreferenz? (2) Chat\-Verlauf mit drei Entscheidungen und viel Rauschen — extrahiert das Sitzungs\-Destillat genau die Entscheidungen? (3) Provozierte unbelegte Zahl im Entwurf — greift der Contract? (4) „Fass zusammen" ohne Kontext — stellt die Skill die zwei Triage\-Fragen, statt ein Zufallsformat zu wählen? (5) Budget\-Trap: Material für drei Seiten, Format erlaubt eine — wird destilliert statt geschrumpft\-gequetscht?

## Alternatives considered

Dokument\-Pipeline (PDF/Word) als Medium verworfen zugunsten HTML\+Markdown (Nutzerentscheidung) — nachrüstbar als dritter Renderer über demselben Modell. Ein Universal\-Template statt vier Formaten verworfen: Die Format\-Wahl *ist* die halbe Verdichtungsleistung. Neutral\-Design verworfen — Wiedererkennbarkeit ist Teil des Nutzens (Token\-Set). Freies Layout pro Anlass (Status quo) ist genau das Problem.

## Out of scope

Periodische Projekt\-/Statusreports (dev\-report, Spec 02), Präsentationen/Slides (eigene pptx\-Skills), Langform\-Dokumente, automatische Verteilung (Mail/Slack), Übersetzung.

## Open questions

Wohin schreibt die Skill ihr Ergebnis? Der Abgleich mit Spec 00 hat gezeigt, dass diese Spec als einzige keinen Ablageort nennt — vom Nutzer pro Lauf angegeben, oder ein Default wie `docs/summaries/` für den Repo\-Fall? Woher kommt das initiale Token\-Set — aus einem bestehenden persönlichen Stil ableiten (kleines Setup\-Interview) oder mit gutem Default starten und anpassen? Sitzungs\-Destillat: Zugriff auf den Chat\-Verlauf ist umgebungsabhängig — Konvention, dass der Nutzer den Verlauf markiert/übergibt? Chart\-Rendering im HTML: Inline\-SVG generiert vs. kleine Chart\-Lib eingebettet (Selbstenthaltenheit vs. Komfort)?

## Next steps

tokens.css und one\-pager.html zuerst bauen und visuell testen (das Format mit dem größten Nutzen); Inhaltsmodell\-Schema festziehen; Markdown\-Skelette ableiten; evidence.md mit Referenz\-Regeln je Input\-Art schreiben; Eval 1 (PDF\-Schlüsselzahl) und 5 (Budget\-Trap) zuerst fahren.
