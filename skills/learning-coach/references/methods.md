# Methoden — destilliert, keine Lernpsychologie-Vorlesung

## Abrufübung (Retrieval Practice) vor Input

Der am besten belegte Lerneffekt ist nicht Wiederholen-durch-Lesen, sondern
Wiederholen-durch-Abrufen: Der Lernende versucht, das Wissen aus dem Gedächtnis zu
holen, *bevor* er es noch einmal erklärt bekommt. Deshalb steht das Quiz zu fälligen
Themen am Anfang jeder Session, nicht am Ende, und deshalb ist „kurz vorlesen, dann
fragen" keine Abrufübung — die Reihenfolge ist der Punkt.

## Spacing-Regel (E4, `due_topics.py`)

Intervall in Tagen je Beherrschungsgrad, wächst mit Erfolg, schrumpft bei Fehlern:

| Grad | Intervall |
| --- | --- |
| 0 | sofort wieder fällig |
| 1 | 1 Tag |
| 2 | 3 Tage |
| 3 | 7 Tage |
| 4 | 14 Tage |

Kein volles SM-2 (keine variable Ease-Factor-Anpassung) — `learner.md` führt bewusst
keinen Wiederholungszähler pro Thema, das wäre Zeremonie ohne Gegenwert für ein
persönliches, handgepflegtes Lernlog. Ein falscher Abruf senkt den Grad sofort um
eine Stufe (kein Toleranz-Zähler): „im Zweifel erinnern statt vergessen" heißt hier,
lieber einmal zu früh wiederholen als ein instabiles Thema zu lange auf hohem Grad zu
belassen.

`due_topics.py interval --grade <alt> --result success|failure --today <datum>`
berechnet Grad und Fälligkeitsdatum deterministisch — nicht aus dem Gedächtnis
schätzen, wenn das Skript verfügbar ist. Ohne Datei-Zugriff (Tier-0-Pfad) rechnet man
die Tabelle im Kopf; sie ist klein genug dafür.

## Fehleranalyse statt „richtig korrigiert, weiter"

Eine falsche Antwort wird seziert, nicht stillschweigend berichtigt:

1. Antwort einordnen — welcher **Denkfehler** steckt dahinter, nicht nur „falsch"?
2. Den Denkfehler in einem Satz benennen, wörtlich, wie der Lernende ihn geäußert
   hat oder erkennbar gedacht hat.
3. Diesen Satz in „Typische Fehler" des betroffenen Themas eintragen — das ist der
   Teil der Datei, der beim nächsten Abruf gezielt wieder geprüft wird.
4. Erst danach den Hinweis-Leiter-Prozess starten (`hint-ladder.md`), falls der
   Lernende weiterarbeiten will.

Eine generische Notiz („Verständnisproblem", „Fehler gemacht") ist keine
Fehleranalyse — sie hilft beim nächsten Mal nicht, gezielt nachzufragen.

## Interleaving

Sind mehrere Themen fällig, nicht Thema für Thema in Blöcken abfragen (Blocking),
sondern zwischen den fälligen Themen wechseln, wenn die Session lang genug ist für
mehr als ein Thema. Interleaving macht den Abruf schwerer (der Lernende kann sich
nicht auf „wir sind ja gerade bei X" verlassen) und genau das ist der Punkt — die
künstliche Erleichterung durch Blockbildung überschätzt sonst den echten
Lernstand.

## Selbsterklärung am Ende

„Erklär es mir jetzt in zwei Sätzen zurück" ist kein Ritual, sondern der letzte
Abruf-Test der Session: Wer es in eigenen Worten (nicht nachgesprochen) erklären
kann, hat es wahrscheinlich verstanden. Eine Selbsterklärung, die nur die zuvor
gegebene Erklärung nachplappert, zählt nicht.
