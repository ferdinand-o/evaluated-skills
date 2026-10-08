# Artefakt-Kopfzeile und Konsumenten-Regel

Gilt für jedes Artefakt, das eine Skill dieser Sammlung erzeugt (Spec 00 §1).
Die ausführbare Fassung dieser Regel ist `ARTIFACT_HEADER_RE` in
`evalkit/assertions.py`; der Eval-Typ `artifact_header` **prüft Markdown und YAML**.

## Format

Die erste nicht-leere Zeile eines erzeugten Artefakts ist seine Kopfzeile.

### Markdown

    <!-- skill: debug-ledger | schema: 1 | generated: python scripts/new_ledger.py --symptom "Login hängt" -->

Mechanisch geprüft von `artifact_header`.

### YAML

    # skill: rest-api-architect | schema: 2 | generated: python scripts/gen_ruleset.py

Mechanisch geprüft von `artifact_header`.

### JSON — Konvention ohne Prüfung

JSON kennt keine Kommentare — dort trägt das Objekt stattdessen den Schlüssel
`_meta` mit denselben drei Feldern:

    {"_meta": {"skill": "dev-report", "schema": 1, "generated": "python scripts/collect.py --since 2026-08-01"}}

**Wichtig:** Der Eval-Typ `artifact_header` prüft JSON-Artefakte **nicht**. Der
`_meta`-Schlüssel ist eine Konvention für Skill-Autoren, damit Konsumenten die
Metadaten finden, aber der Harness validiert ihn derzeit nicht mechanisch. Wer
JSON-Artefakte mit `artifact_header` prüfen will, muss zuerst ein neues
Assertion-Primitiv implementieren — eine Aufgabe für später.

## Die drei Felder

- **skill** — der Skill-Name aus dem Frontmatter, kleingeschrieben mit Bindestrichen.
  Damit ist beim Lesen sofort klar, wer die Datei besitzt.
- **schema** — eine Zählnummer pro Artefaktart, beginnend bei 1. Sie wird
  hochgezählt, wenn sich die *Struktur* ändert, nicht der Inhalt.
- **generated** — das Kommando, das die Datei erzeugt hat, so wie man es erneut
  eintippen würde. Wer die Datei verstehen will, kann sie damit neu erzeugen.

## Bootstrap-Regel

Keine Skill legt ungefragt Dateien in fremden Repos an. Der erste Lauf kündigt
die Anlage an und nennt den Pfad.

## Konsumenten-Regel

Ein Konsument nimmt nie ein Format an, sondern liest die Kopfzeile:

1. Kopfzeile fehlt → das Artefakt stammt nicht aus dieser Sammlung. Nicht parsen,
   sondern sichtbar überspringen.
2. `schema` höher als erwartet → sichtbar überspringen und melden:
   „`docs/decisions.md` schema 1 erwartet, 2 gefunden — Scan übersprungen."
3. `schema` niedriger als erwartet → lesen erlaubt, wenn der Konsument die alte
   Struktur kennt; sonst wie Fall 2 behandeln.

Stillschweigendes Raten ist der einzige verbotene Weg. Die Kopplung der Skills
untereinander hält genau so lange, wie diese Regel eingehalten wird.

## Degradations-Regel

Keine Skill *setzt* ein Artefakt voraus. Fehlt es, arbeitet die Skill ohne es
weiter und sagt, was ihr dadurch fehlt.

## Begründete Ausnahme: `handoff.md`

Die Skill `handoff` erzeugt ihr Artefakt bewusst **ohne** die Kopfzeile dieser
Konvention — `handoff.md` beginnt mit `# Handoff — <Projekt>`, keiner
Kommentarzeile mit `skill:`/`schema:`/`generated:`. Das ist kein Versehen: Die
Kopfzeile existiert, damit ein Konsument ein Artefakt maschinenlesbar
identifizieren, versionieren und bei unerwartetem Schema sichtbar überspringen
kann. `handoff.md` hat nur zwei Konsumenten — die nächste Claude-Session, die
sie am Sitzungsanfang liest, und den Menschen, der die Übergabe überfliegt.
Beide brauchen keine Schema-Version, um die Datei zu verstehen; beide würden
eine Kommentarzeile vor dem Titel eher als Reibung empfinden als als Nutzen.

Diese Ausnahme gilt nur, solange es bei diesen zwei Konsumenten bleibt. Sobald
ein drittes Werkzeug `handoff.md` automatisiert parst (ein Dashboard, ein
weiterer Skill, ein CI-Schritt), kippt die Begründung, und die Datei braucht
die Kopfzeile wie jedes andere Artefakt dieser Sammlung.

## Begründete Ausnahme: die Stub-Dateien von `feature-spec`

`export_stubs.py` (Skill `feature-spec`) schreibt pro Akzeptanzkriterium eine
Test-Stub-Datei, deren erste Zeile `# spec-stub: <kriterium-slug>` lautet —
nicht die generische `skill: … | schema: … | generated: …`-Kopfzeile. Auch
das ist kein Versehen: Der Marker hat hier eine andere Aufgabe als die
Kopfzeile bei jedem anderen Artefakt. Die generische Kopfzeile existiert,
damit ein *Konsument* ein Artefakt erkennen, versionieren und bei
unerwartetem Schema sichtbar überspringen kann (siehe Konsumenten-Regel
oben). Eine Stub-Datei hat aber keinen solchen Konsumenten — sie wird nie
von einer anderen Skill gelesen und geparst. Ihr Marker ist stattdessen ein
Überschreibschutz für `export_stubs.py` selbst: Ein Re-Export überschreibt
die Datei nur, solange sie noch `# spec-stub: <slug>` **und**
`@pytest.mark.skip("stub: noch nicht implementiert")` trägt. Sobald jemand
den Test implementiert und den Skip-Marker entfernt, bleibt die Datei
unangetastet — der spezifische Marker trägt hier die Überschreiblogik direkt
im Namen, eine zusätzliche generische Kopfzeile daneben würde nichts
zusätzlich leisten, nur die Datei um eine Zeile verlängern, die pytest beim
Sammeln als Docstring-fremde Zeile mitschleppt.

Diese Ausnahme gilt nur für die generierten Stub-Dateien selbst — der
Spec-Entwurf, aus dem sie erzeugt werden (`docs/specs/wip/<feature>.md`),
und `docs/decisions.md` tragen die reguläre Kopfzeile wie jedes andere
Wissens-Artefakt, weil beide echte Konsumenten haben (künftige Scans lesen
`docs/decisions.md`, ein Mensch liest den Spec-Entwurf während der Arbeit).

## Begründete Ausnahme: die Anki-CSV von `exercise-forge`

`skills/exercise-forge/scripts/export.py` schreibt neben dem
Markdown-Übungsblatt (mit regulärer Kopfzeile) eine Anki-CSV — bewusst **ohne**
Kopfzeile. Anki interpretiert Zeilen, die mit `#` beginnen, als
Import-Direktiven (`#separator:comma`, `#html:true`, `#columns:…`); eine
Kommentar-Kopfzeile nach dieser Konvention läge in genau diesem Namensraum und
könnte den Import stören oder von Anki fehlinterpretiert werden. Die CSV hat
nur einen Konsumenten — den Anki-Import des Menschen, der die Datei erzeugt
hat — und der braucht keine Schema-Version, um die Datei zu verstehen.

Diese Ausnahme gilt nur, solange es bei diesem einen Konsumenten bleibt.
Parst ein automatisiertes Werkzeug diese CSV künftig maschinell, braucht sie
eine andere Lösung (z. B. eine begleitende `.meta.json`-Datei), keine
`#`-Kopfzeile.

**Für Skill-Autoren:** Diese Regel gilt für *jedes* Artefakt (siehe oben).
Die drei dokumentierten Ausnahmen sind `handoff.md`, die Stub-Dateien von
`feature-spec` und die Anki-CSV von `exercise-forge` — jede mit einem hier
ausgeschriebenen Grund, keine davon, weil die Kopf-Regel optional wäre. Wer
eine neue Skill baut und eine ähnliche Ausnahme für gerechtfertigt hält,
dokumentiert sie hier nach demselben Muster, statt sich stillschweigend auf
einen Präzedenzfall zu berufen.
