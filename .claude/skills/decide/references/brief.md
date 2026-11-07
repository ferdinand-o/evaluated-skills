# Auftrag an einen Subagenten

Vorlage für den Auftrag, den der Hauptagent in den Prompt eines Subagenten schreibt (SKILL.md,
Ablauf 6). Es gibt kein Skript und keine Datei dazu: Der Auftrag ist eine Frage an einen frischen
Kontext, keine Zusammenfassung des eigenen. Er sagt, was der Subagent klären soll und wo er
nachsieht, nicht, was der Hauptagent schon denkt. Sonst bestätigt der Subagent nur dessen Sicht.

## Die sechs Felder

Jedes Feld ist eine Überschrift mit einer Zeile oder wenigen Zeilen darunter; der ganze Auftrag
bleibt kurz, sonst geht der Vorteil des frischen Kontexts verloren. Wer kürzt, kürzt nie die
Zeilen zu offenen großen Fragen unter Feste Vorgaben.

- **Frage**: ein Satz, neutral, ohne Empfehlung und ohne bevorzugte Option.
- **Anlass**: die laufende Aufgabe und ihr Ziel, ein bis zwei Sätze.
- **Wo nachsehen**: Pfade und Suchmuster, keine Dateiinhalte; lesen tut der Subagent.
- **Schon entschieden**: Einträge zum Thema aus dem Protokoll der Sitzung
  (`.skills/cache/decide/<session>/log.md`, alle Zeilen mit diesem Thema — `summary` zeigt nur die
  zehn jüngsten und lässt `nie fragen` aus) und Blöcke in `docs/big-decisions.md` mit Status
  `freigegeben` oder `abgelehnt`, je mit Quelle; `—`, wenn keine.
- **Feste Vorgaben**: was nicht zur Wahl steht (Nutzer, Spec, Plan, Regeln aus `rules.md`), je mit
  Quelle; dazu jede offene große Frage aus `decide_log.py open` — auch aus früheren Sitzungen und
  ohne Thema — mit „nicht entscheiden, nicht darauf aufbauen“. Ist die Ablage nicht lesbar, steht
  hier „Ablage nicht gelesen — bei jeder teuren Frage zurückgeben statt entscheiden“.
- **Rückgabe**: Optionen mit Belegen `datei:zeile`, Folgen, Umkehrbarkeit, dann eine Empfehlung
  mit Grund; darunter der feste Satz:

> Du arbeitest als Subagent. Trag keine Entscheidung und keine Frage mit decide_log.py ein und schreib nicht nach docs/big-decisions.md. Stößt du auf eine Frage mit zwei Lesarten oder auf einen teuer umkehrbaren Schritt, der nicht ausdrücklich in deinem Auftrag steht, entscheide und handle nicht, sondern nenn ihn in deiner Rückgabe: Frage, Optionen mit Belegen datei:zeile, Folgen, Umkehrbarkeit, Empfehlung. Der Hauptagent ordnet ihn ein.

Derselbe Satz beendet jeden anderen Auftrag an einen Subagenten, solange decide geladen ist,
wörtlich und nicht sinngemäß. Eine offene große Frage ist für den Subagenten keine Entscheidung:
Bis zur Freigabe unterbleibt die ganze Antwort darauf.

## Was nicht hineingehört

- Eine Neigung des Hauptagenten: keine Empfehlung, keine bevorzugte Option, kein „ich glaube“.
- Ein Feld außer den sechs und Text vor dem ersten Feld.
- Inhalte von Dateien, der Verlauf der Sitzung oder eine Zusammenfassung des Gesprächs.
- Eine Anweisung, selbst etwas mit `decide_log.py` einzutragen.

## Wertende Wörter (Hinweis für den Hauptagenten)

Ob die Frage neutral ist, prüft kein Skript; der Hauptagent liest die Frage vor dem Dispatch
selbst gegen diese Liste (G1). Gebeugte Formen und andere Wertungen zählen genauso.

- `sollte`
- `besser`
- `lieber`
- `empfehle`
- `ich würde`
- `offensichtlich`
