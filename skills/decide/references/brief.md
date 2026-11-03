# Entscheidungsauftrag an einen Subagenten

Ein Auftrag ist eine Frage an einen frischen Kontext, keine Zusammenfassung des eigenen: Er sagt
dem Subagenten, was er klären soll und wo er nachsieht, nicht, was der Hauptagent schon denkt.
Sonst bestätigt der Subagent nur die Sicht des Hauptagenten.

`decide_log.py brief --topic <thema>` schreibt den Auftrag nach
`.skills/cache/decide/<session>/brief-<n>.md` (Nummer: die höchste plus eins). Vor dem Dispatch
prüft ihn `decide_log.py brief --check <datei>`. Die Wortliste unten liest das Skript aus dieser
Datei; eine zweite Liste im Skript gibt es nicht.

## Form

Zeile 1 ist die Kopfzeile `<!-- skill: decide | schema: 1 | generated: … -->`; sie zählt nicht
zu den Feldern und nicht zu den Zeilen. Danach genau die sechs Felder unten, jedes als
Überschrift `## <Feld>`, der Inhalt in den Zeilen darunter. Jede Überschrift ist ein Feld, auch
eine `###`. Ein Auftrag hat höchstens 25 Zeilen mit Text ohne die Kopfzeile; Leerzeilen zählen
nicht. Die Grenze ist gesetzt, nicht gemessen: Ein längerer Auftrag nimmt dem Subagenten den
Vorteil des frischen Kontexts.

## Die sechs Felder

| Feld | Inhalt | füllt |
| --- | --- | --- |
| Frage | ein Satz, neutral, ohne Wörter der Wortliste | Hauptagent |
| Anlass | die laufende Aufgabe und ihr Ziel | Hauptagent |
| Feste Vorgaben | was nicht zur Wahl steht — Nutzer, Spec, Plan, Regeln —, je mit Quelle | Skript: jede Regel aus `.skills/decide/rules.md` und `~/.skills/decide/rules.md` mit Datei und Zeile; Hauptagent: Nutzer, Spec, Plan |
| Schon entschieden | die Einträge der Sitzung mit demselben Thema | Skript, aus dem Protokoll; `—`, wenn keiner |
| Wo nachsehen | Pfade und Suchmuster, keine Inhalte | Hauptagent |
| Rückgabe | Optionen mit Belegen `datei:zeile`, Folgen, Umkehrbarkeit, Empfehlung; dazu der Satz für Subagenten | Skript |

## Der Satz für Subagenten

Unter Rückgabe steht wörtlich der Satz aus Spec 28, Ablauf 5:

> Du arbeitest als Subagent. Trag keine Entscheidung und keine Frage mit decide_log.py ein und schreib nicht nach docs/big-decisions.md. Stößt du auf eine Frage mit zwei Lesarten oder auf einen teuer umkehrbaren Schritt, der nicht ausdrücklich in deinem Auftrag steht, entscheide und handle nicht, sondern nenn ihn in deiner Rückgabe: Frage, Optionen mit Belegen datei:zeile, Folgen, Umkehrbarkeit, Empfehlung. Der Hauptagent ordnet ihn ein.

Derselbe Satz beendet jeden anderen Auftrag an einen Subagenten, solange decide geladen ist —
wörtlich, nicht sinngemäß. `brief --check` prüft ihn bewusst nicht: Ob er dasteht und ob der
Subagent sich daran hält, bleibt G1.

## Was nicht hinein gehört

- Eine Neigung des Hauptagenten: keine Empfehlung, keine bevorzugte Option, kein „ich glaube“.
  Der Subagent soll prüfen, nicht bestätigen.
- Ein Feld außer den sechs, etwa „Empfehlung des Hauptagenten“, „Hintergrund“ oder „Meine
  Einschätzung“, und Text vor dem ersten Feld.
- Inhalte von Dateien: Wo nachsehen nennt Pfade und Suchmuster, lesen tut der Subagent.
- Der Verlauf der Sitzung oder eine Zusammenfassung des bisherigen Gesprächs.
- Eine Anweisung, selbst etwas mit `decide_log.py` einzutragen.

## Wortliste

`brief --check` meldet jedes dieser Wörter in der Frage — als ganzes Wort, ohne Rücksicht auf
Groß- und Kleinschreibung (`Sollte` trifft, `verbessern` nicht); bei einer Wortfolge darf
beliebig viel Leerraum zwischen den Wörtern stehen. Gebeugte Formen und andere Wertungen prüft
es nicht (G1). Das Skript liest die Liste aus diesem Abschnitt (`load_wordlist`): je Listenpunkt
ein Wort oder eine Wortfolge in Backticks, bis zur nächsten Überschrift. Fehlt die Datei, fehlt
der Abschnitt oder steht ein anderer Listenpunkt darin, endet `brief --check` mit Exit 2
„ungeprüft — …“, nie mit Erfolg.

- `sollte`
- `besser`
- `lieber`
- `empfehle`
- `ich würde`
- `offensichtlich`

## Was brief --check meldet

- mehr als 25 Zeilen mit Text ohne die Kopfzeile;
- ein Feld außer den sechs, Text vor dem ersten Feld, ein fehlendes oder doppeltes Feld;
- Wörter der Wortliste in der Frage.

Exit 1 bei mindestens einem Befund, sonst 0. Exit 2 „ungeprüft — …“, wenn die Datei fehlt oder
nicht lesbar ist, wenn ihr die Kopfzeile von decide fehlt oder `schema` höher als 1 ist
(Konsumenten-Regel, `docs/artifact-header.md`) und wenn die Wortliste nicht gelesen werden kann.
Ob die Frage ohne diese Wörter neutral ist und ob Frage, Anlass und Wo nachsehen ausgefüllt sind,
prüft es nicht.
