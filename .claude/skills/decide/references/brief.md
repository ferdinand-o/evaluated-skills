# Entscheidungsauftrag an einen Subagenten

Ein Auftrag ist eine Frage an einen frischen Kontext, keine Zusammenfassung des eigenen: Er sagt
dem Subagenten, was er klären soll und wo er nachsieht, nicht, was der Hauptagent schon denkt.
Sonst bestätigt der Subagent nur die Sicht des Hauptagenten.

`decide_log.py brief --topic <thema>` schreibt den Auftrag nach
`.skills/cache/decide/<session>/brief-<n>.md` (Nummer: die höchste plus eins) und nennt den Pfad
relativ zur Repo-Wurzel. Vor dem Dispatch prüft ihn `decide_log.py brief --check <datei>`; ein
relativer Pfad, der im Arbeitsverzeichnis fehlt, gilt relativ zur Repo-Wurzel. Den Satz für
Subagenten und die Wortliste unten liest das Skript aus dieser Datei; eine zweite Fassung im
Skript gibt es nicht.

## Form

Zeile 1 ist die Kopfzeile `<!-- skill: decide | schema: 1 | generated: … -->`; sie zählt nicht
zu den Feldern und nicht zu den Zeilen. Sie nennt den Befehl lesbar, bei einem Thema mit `--` aber
nicht wörtlich kopierbar: `--` steht dort als `‐‐` (U+2010), weil `--` in einem HTML-Kommentar nicht
erlaubt ist. Danach genau die sechs Felder unten, jedes als
Überschrift `## <Feld>`, der Inhalt in den Zeilen darunter. Jede Überschrift außerhalb eines
Codezauns ist ein Feld, auch eine `###`; in einem Codezaun (```` ``` ```` oder `~~~`) ist eine
Zeile mit `#` Text des Feldes. Ein Auftrag hat höchstens 25 Zeilen mit Text ohne die Kopfzeile;
Leerzeilen zählen nicht. Die Grenze ist gesetzt, nicht gemessen: Ein längerer Auftrag nimmt dem
Subagenten den Vorteil des frischen Kontexts. Bleiben in einem Auftrag, wie `brief --topic` ihn
schreibt, für Frage, Anlass und Wo nachsehen keine drei Zeilen mehr (mehr als 22, etwa bei vielen
Regeln oder erledigten Fragen zum Thema), sagt es „Hinweis: Auftrag hat schon <n> Zeilen ohne Kopf,
höchstens 25 (davon <r> Regeln, <d> unter Schon entschieden, <o> zu offenen Fragen); für Frage, Anlass
und Wo nachsehen bleiben <m> Zeilen, mindestens 3 nötig — Regeln oder ältere Einträge unter Schon
entschieden kürzen, die Zeilen zu offenen Fragen nie“; geschrieben wird er trotzdem.

## Die sechs Felder

| Feld | Inhalt | füllt |
| --- | --- | --- |
| Frage | ein Satz, neutral, ohne Wörter der Wortliste | Hauptagent |
| Anlass | die laufende Aufgabe und ihr Ziel | Hauptagent |
| Feste Vorgaben | was nicht zur Wahl steht — Nutzer, Spec, Plan, Regeln, offene große Fragen —, je mit Quelle | Skript: zuerst, ist `docs/big-decisions.md` unlesbar oder übersprungen (Konsumenten-Regel), `- Ablage docs/big-decisions.md nicht gelesen (<Grund>) — offene große Fragen zum Thema möglich; nichts entscheiden, was teuer umkehrbar ist, sondern zurückgeben` (fehlt sie, nichts); dann jede offene große Frage des Themas aus der Ablage, aus jeder Sitzung, als `- D-<n> offen: <frage> — nicht entscheiden, nicht darauf aufbauen` (ohne lesbare Ablage, bei doppeltem Block oder anderem Status: `Status unbekannt`) und jeder offene Block ohne Zeile `Thema:` (oder leer) als `- D-<n> offen, ohne Thema: <frage> — prüfen, ob sie das Thema betrifft`; ein Block mit anderem Thema bleibt draußen, ob das Thema passt, prüft das Skript nicht (G1); dann jede Regel aus `.skills/decide/rules.md` und `~/.skills/decide/rules.md` mit Datei und Zeile; Hauptagent: Nutzer, Spec, Plan |
| Schon entschieden | die Einträge der Sitzung mit demselben Thema und die Blöcke des Themas in `docs/big-decisions.md`, die freigegeben (mit Antwort; per Auftrag freigegeben: mit dem Zitat) oder abgelehnt sind, aus jeder Sitzung, jede Frage einmal | Skript, aus Protokoll und Ablage; `—`, wenn keiner |
| Wo nachsehen | Pfade und Suchmuster, keine Inhalte | Hauptagent |
| Rückgabe | Optionen mit Belegen `datei:zeile`, Folgen, Umkehrbarkeit, Empfehlung; dazu der Satz für Subagenten | Skript |

## Der Satz für Subagenten

Unter Rückgabe steht wörtlich der Satz aus Spec 28, Ablauf 5. Das Skript liest ihn aus diesem
Abschnitt (`load_subagent_sentence`): das eine Zitat `> …` bis zur nächsten Überschrift außerhalb
eines Codezauns, über mehrere Zeilen zu einer zusammengezogen; jede Zeile des Zitats beginnt mit `> `.
Der Abschnitt beginnt an der ersten Überschrift außerhalb eines Codezauns; ein Beispiel im Zaun zählt
nicht. Eine Zeile direkt nach dem Zitat, die mit ```` ``` ````, `~~~`, `- `, `* `, `+ `, einer Ziffer
mit `. `, `#` oder `<!--` beginnt, beendet es wie in Markdown; nur eine andere Textzeile ohne `>` gilt
als Fortsetzung und ist ein Fehler.
Sonst endet `brief --topic` mit Exit 2 und schreibt nichts; die Meldung nennt die Ursache:
„ungeprüft — references/brief.md fehlt“ bzw. „… nicht lesbar (<Ursache>)“, „ungeprüft — Satz für
Subagenten fehlt in references/brief.md (…)“ (kein Abschnitt, kein Zitat), „ungeprüft — Satz für
Subagenten mehrfach in references/brief.md (…)“ (zwei Zitate) und „ungeprüft —
references/brief.md:<n>: … ohne „>““ für eine Zeile ohne `>` mitten im Zitat, die den Satz sonst
still kürzte.

> Du arbeitest als Subagent. Trag keine Entscheidung und keine Frage mit decide_log.py ein und schreib nicht nach docs/big-decisions.md. Stößt du auf eine Frage mit zwei Lesarten oder auf einen teuer umkehrbaren Schritt, der nicht ausdrücklich in deinem Auftrag steht, entscheide und handle nicht, sondern nenn ihn in deiner Rückgabe: Frage, Optionen mit Belegen datei:zeile, Folgen, Umkehrbarkeit, Empfehlung. Der Hauptagent ordnet ihn ein.

Derselbe Satz beendet jeden anderen Auftrag an einen Subagenten, solange decide geladen ist —
wörtlich, nicht sinngemäß. `brief --check` prüft ihn bewusst nicht: Ob er dasteht und ob der
Subagent sich daran hält, bleibt G1. Eine offene große Frage ist für den Subagenten keine
Entscheidung: Bis zur Freigabe unterbleibt die ganze Antwort darauf (Spec 28, Ablauf 4).

## Was nicht hinein gehört

- Eine Neigung des Hauptagenten: keine Empfehlung, keine bevorzugte Option, kein „ich glaube“.
  Der Subagent soll prüfen, nicht bestätigen.
- Ein Feld außer den sechs, etwa „Empfehlung des Hauptagenten“, „Hintergrund“ oder „Meine
  Einschätzung“, und Text vor dem ersten Feld.
- Inhalte von Dateien: Wo nachsehen nennt Pfade und Suchmuster, lesen tut der Subagent.
- Der Verlauf der Sitzung oder eine Zusammenfassung des bisherigen Gesprächs.
- Eine Anweisung, selbst etwas mit `decide_log.py` einzutragen.

## Wertende Wörter

`brief --check` meldet jedes Wort der Wortliste unten in der Frage — als ganzes Wort, ohne
Rücksicht auf Groß- und Kleinschreibung (`Sollte` trifft, `verbessern` nicht). Ein Wort endet an
jedem Zeichen, das weder Buchstabe noch Ziffer ist, auch an `_` (`_sollte_` trifft, `sollte2`
nicht); bei einer Wortfolge darf beliebig viel Leerraum zwischen den Wörtern stehen. Gebeugte
Formen und andere Wertungen prüft es nicht (G1). Das Skript liest die Liste aus dem Abschnitt
`## Wortliste` (`load_wordlist`; die erste solche Überschrift außerhalb eines Codezauns): Dort steht bis zur nächsten Überschrift je Zeile nur ein
Listenpunkt `- ` oder `* ` mit einem Wort oder einer Wortfolge in Backticks; Leerzeilen sind
erlaubt. Fehlt die Datei, fehlt der Abschnitt oder steht darin eine andere Zeile — Prosa, ein
Punkt mit `+ ` oder `1.`, ein Wort ohne Backticks —, endet `brief --check` mit Exit 2
„ungeprüft — …“ und der Zeilennummer, nie mit Erfolg.

## Wortliste

- `sollte`
- `besser`
- `lieber`
- `empfehle`
- `ich würde`
- `offensichtlich`

## Was brief --check meldet

- mehr als 25 Zeilen mit Text ohne die Kopfzeile;
- ein Feld außer den sechs, Text vor dem ersten Feld, ein fehlendes oder doppeltes Feld
  (Überschriften in Codezäunen zählen nicht);
- Wörter der Wortliste in der Frage.

Exit 1 bei mindestens einem Befund, sonst 0. Exit 2 „ungeprüft — …“, wenn die Datei fehlt oder
nicht lesbar ist, wenn ihr die Kopfzeile von decide fehlt oder `schema` höher als 1 ist
(Konsumenten-Regel, `docs/artifact-header.md`) und wenn die Wortliste nicht gelesen werden kann.
Ob die Frage ohne diese Wörter neutral ist und ob Frage, Anlass und Wo nachsehen ausgefüllt sind,
prüft es nicht.
