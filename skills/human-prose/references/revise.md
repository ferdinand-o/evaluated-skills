# Modus B: Überarbeiten in sieben Schritten

Aus Abschnitt 7 des Entwurfs (`rules.md`), mit dem Ein-Zug-Verhalten aus Spec 19: Die
Skill wartet nie auf eine Antwort. Sie schreibt um, lässt Lücken allgemein und fragt
am Ende. So verhält sie sich im Chat und im `-p`-Modus gleich; im Chat füllt die
Antwort des Nutzers die Lücken in einer zweiten Runde.

## Die Schritte

1. **Messen.** `measure.py <original> --register <fach|kurz>`; Werte lesen, nicht
   überfliegen. Liegt der Text nicht in einer Datei, zuerst nach
   `.skills/cache/human-prose/original.md` schreiben.
2. **Diagnose.** Fundstellen nach Regelnummer, aus dem Artefakt und aus den fünf
   Urteilen unter `judgement`. Keine Änderung ohne Regelbezug.
3. **Faktenlücken markieren.** Wo R5.1 eine Zahl, einen Namen oder ein Datum verlangt,
   das im Original fehlt: die vage Formel fällt („verschiedene Faktoren" wird zu „die
   Ursache"), die Stelle bleibt allgemein, und sie kommt auf die Liste für Schritt 7.
   Nichts wird erfunden — keine Zahl, kein Name, kein Datum, kein Zitat, keine Anekdote
   (R5.2). Was der Auftrag liefert („Deployment gestern 21:40 bis 22:15"), darf hinein.
4. **Umschreiben,** in dieser Reihenfolge: Zeichen (R1), Struktur (R3), Satzbau (R2,
   R4.3 bis R4.5), Wortwahl (R4.1, R4.2, R4.6). Struktur vor Satzbau, weil sich
   Satzprobleme danach oft erledigt haben. Eingriffstiefe auf Zuruf:
   - *leicht*: nur Zeichen und tote Phrasen;
   - *mittel* (Default): dazu Satzbau und Rhythmus;
   - *stark*: Struktur darf sich ändern, Absätze und Überschriften eingeschlossen.
   Fremde Verträge bleiben: Kopfzeilen wie `# Handoff — <Projektname>`, Tokens wie
   `Next:` oder `Unverified:`, Marker wie `Einschätzung:` sind Vertragsbestandteil der
   Skill, die den Text erzeugt hat. R1.1 gilt für den Fließtext dazwischen.
5. **Faktenabgleich.** Jede Aussage des Originals steht im Ergebnis und umgekehrt.
   Kürzen ist erlaubt; eine weggelassene Aussage ist ein Befund im Bericht, keine
   stille Entscheidung. Bei mehr als fünf Aussagen: Tabelle Aussage → Stelle im Ergebnis.
6. **Nachmessen.** `measure.py <original> --after <ergebnis> --register <…> --out
   .skills/cache/human-prose/measure.json`. Liegt der Text in einer Datei, ersetzt das
   Ergebnis sie; sonst steht es in der Antwort. Ein Befund, der bleibt, wird benannt,
   nicht wegformuliert.
7. **Bericht.** Drei bis fünf Zeilen: was sich geändert hat, nach Regelnummer, mit den
   Zahlen aus Vorher und Nachher. Keine Lobrede. Danach, falls Schritt 3 etwas
   gesammelt hat, die Zeile `Rückfrage:` mit einer Liste der Stellen und der Frage
   dazu. Zuletzt `Register: <fach|kurz>`.

## Format des Berichts

```
Überarbeitet (Register: fach, Eingriffstiefe mittel): R1.1 zwei Geviertstriche und ein
Semikolon weg; R4.1 drei Phrasen gestrichen; R4.3 ein Partizip-Anhängsel als eigener
Satz; R3.5 Schlussfloskel weg. Vorher 4 Befunde, nachher 0, 2 ungeprüft.
Rückfrage:
- Absatz 2 nennt „verschiedene Faktoren" — welche? Latenz, Last, beides?
- „viele Unternehmen" — gibt es einen Namen, oder soll die Aussage weg?
Register: fach
```

Ohne Faktenlücke entfällt die `Rückfrage:`-Zeile. Ohne Skript lautet die erste Zeile
„ungeprüft: measure.py nicht verfügbar", und der Bericht zählt nur, was von Hand
geprüft wurde.

## Was der Bericht nicht tut

Er lobt das Ergebnis nicht, er erklärt die Regeln nicht, und er wiederholt den Text
nicht. Wer wissen will, warum ein Geviertstrich ein Marker ist, liest `rules.md`.
