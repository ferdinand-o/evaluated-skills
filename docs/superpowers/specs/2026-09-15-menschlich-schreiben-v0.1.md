# Spec: menschlich schreiben

Version 0.1, 15.09.2026. Grundlage für den Skill. Jede Regel hat ein prüfbares Kriterium, sonst ist sie keine Regel sondern ein Wunsch.

Eingabe des Nutzers für `specs/Spec 19 – human-prose.md`; beim Bau wird dieser Text zu `skills/human-prose/references/rules.md`.

## 0. Grundsatz

Menschlicher Text unterscheidet sich von LLM-Text nicht dadurch, dass er schlechter ist. Er unterscheidet sich durch drei Dinge.

Er ist ungleichmäßig. Sätze sind mal vier Wörter lang, mal dreißig. Absätze sind nicht gleich groß. Nicht jeder Abschnitt endet mit einem Fazit.

Er ist konkret. Statt "verschiedene Faktoren" steht da "der Timeout von 30 Sekunden". Statt "viele Unternehmen" steht da ein Name oder gar nichts.

Er hat eine Richtung. Der Autor findet etwas. Er zählt nicht beide Seiten auf und schließt mit "es kommt darauf an".

Alles Weitere in dieser Spec sind Ableitungen davon.

## 1. Zeichen

### R1.1 Verbotene Zeichen

Diese Zeichen kommen im Fließtext nicht vor:

* Geviertstrich, das lange Zeichen aus dem englischen Satz
* Halbgeviertstrich als Gedankenstrich, also der Strich mit Leerzeichen davor und danach
* Semikolon

Prüfung: Suche nach diesen drei Zeichen im Text. Treffer gleich null.

### R1.2 Was erlaubt bleibt

* Bindestrich in Komposita und Bindestrichwörtern. "KI-Text", "Multi-Tenant", "Ein- und Ausgabe". Das ist ein Wortbestandteil, kein Satzzeichen.
* Bindestrich in Markdown-Listen und in Code.
* Zahlenbereiche schreibt man aus. Nicht "3 bis 5" mit Strich, sondern "3 bis 5" mit Wort, oder "von 3 bis 5".

### R1.3 Ersatz pro Funktion

Der Gedankenstrich verschwindet nicht ersatzlos, sonst entstehen Bandwurmsätze. Pro Funktion gilt:

| Funktion | Ersatz | Beispiel |
|---|---|---|
| Kurzer Einschub | Kommas | "Der Cache, seit gestern aktiv, hält 200 Einträge." |
| Nebenbemerkung, die man streichen könnte | Klammern | "Der Job läuft nachts (meistens um drei)." |
| Zäsur, Pointe, Umschwung | Punkt und neuer Satz | "Das war der Plan. Es kam anders." |
| Ankündigung einer Auflösung | Doppelpunkt | "Ein Grund bleibt: die Latenz." |
| Semikolon zwischen eng verwandten Hauptsätzen | Punkt, oder "und" beziehungsweise "aber" | "Der Test lief durch. Die Zahlen stimmten trotzdem nicht." |

### R1.4 Frequenzgrenzen für den Ersatz

Der Ersatz darf kein neuer Tick werden.

* Klammern: höchstens einmal pro 200 Wörter.
* Doppelpunkt im Fließtext: höchstens einmal pro 150 Wörter. Doppelpunkte vor Listen zählen nicht mit.
* Ausrufezeichen: in Fachtexten null, in Kurzform höchstens eins pro Nachricht.

## 2. Rhythmus

### R2.1 Satzlängenstreuung

Innerhalb von je zehn aufeinanderfolgenden Sätzen gilt:

* Mindestens ein Satz mit höchstens sechs Wörtern.
* Mindestens ein Satz mit mindestens zwanzig Wörtern.
* Die Standardabweichung der Satzlängen liegt bei mindestens 40 Prozent des Mittelwerts.

Zielkorridor für den Mittelwert: 13 bis 18 Wörter im Fachtext, 9 bis 14 in der Kurzform. `TODO Korpus`: Werte gegen eigenes Referenzkorpus nachjustieren.

### R2.2 Satzanfänge

* Keine drei aufeinanderfolgenden Sätze mit derselben Konstruktion am Anfang, also nicht dreimal Subjekt zuerst, nicht dreimal ein Konnektor zuerst.
* Kein Absatz beginnt mit "Darüber hinaus", "Zudem", "Außerdem", "Furthermore", "Moreover", "Additionally".
* Dasselbe Wort steht höchstens einmal pro fünf Sätze am Satzanfang.

### R2.3 Absätze

* Absatzlängen variieren. In einem Text mit fünf oder mehr Absätzen gibt es mindestens einen mit einem oder zwei Sätzen und mindestens einen mit vier oder mehr.
* Kein Absatz endet mit einem zusammenfassenden Satz, der nur das Gesagte wiederholt. Der Abschluss ist entweder eine Folgerung mit neuem Inhalt oder es gibt keinen.

### R2.4 Fragmente

Unvollständige Sätze sind erlaubt und erwünscht, sparsam eingesetzt. "Nicht ideal." "Kurz gesagt: nein." Höchstens eines pro 200 Wörter in Fachtexten, freier in der Kurzform.

## 3. Struktur

### R3.1 Listen nur für Listen

Eine Aufzählung steht da, wenn der Inhalt eine Aufzählung ist. Drei Argumente in einem Gedankengang sind Fließtext, keine Bullet-Points.

Prüfung: Wenn sich die Punkte einer Liste ohne Verlust zu zwei Sätzen zusammenfügen lassen, war es keine Liste.

### R3.2 Keine Fettung als Ersatz für Satzbau

Das Muster **Begriff:** gefolgt von einem Erklärsatz ist ein starker KI-Marker. Erlaubt nur in echten Glossaren und Referenztabellen.

### R3.3 Keine Dreierregel als Automatismus

Wenn drei Beispiele nötig sind, drei. Wenn zwei reichen, zwei. Nicht jede Aufzählung besteht aus drei Elementen, und nicht jeder Satz braucht ein Trikolon.

Prüfung: Zähle die Aufzählungen mit genau drei Elementen. Liegt der Anteil über der Hälfte, ist es ein Muster.

### R3.4 Überschriften

* Keine Überschrift für weniger als drei Sätze Inhalt.
* Überschriften benennen die Sache, nicht die Funktion. "Warum der Cache überläuft" statt "Herausforderungen".
* Kein Text hat mehr Überschriften als Absätze pro Überschrift.

### R3.5 Kein Rahmen um alles

Weg mit dem einleitenden Satz, der ankündigt was gleich kommt, und dem Schlusssatz, der zusammenfasst was gerade stand. Der Text beginnt beim Thema und endet, wenn er fertig ist.

Verboten als Eröffnung: "In diesem Artikel", "Im Folgenden", "Lass uns", "Let's dive in", "In this guide".
Verboten als Abschluss: "Zusammenfassend lässt sich sagen", "Fazit:", "In conclusion", "At the end of the day", "Ultimately".

## 4. Wortwahl

### R4.1 Tote Phrasen Deutsch

Ersatzlos streichen oder durch Konkretes ersetzen:

"in der heutigen Welt", "im digitalen Zeitalter", "in der heutigen schnelllebigen Zeit", "spielt eine entscheidende Rolle", "ist von entscheidender Bedeutung", "es ist wichtig zu beachten", "es sei darauf hingewiesen", "nicht nur X, sondern auch Y" als Standardmuster, "ein echter Gamechanger", "auf das nächste Level", "umfassender Leitfaden", "maßgeschneiderte Lösung", "nahtlos", "ganzheitlich", "revolutionieren", "vielfältig", "sorgfältig ausgewählt", "Tauchen wir ein", "die Wahl hängt von Ihren individuellen Anforderungen ab", "es gibt keine Einheitslösung".

### R4.2 Tote Phrasen Englisch

"delve", "tapestry", "meticulous", "pivotal", "testament to", "a plethora of", "a multitude of", "it is important to note", "it's worth noting", "in today's fast-paced world", "navigate the landscape", "unlock the potential", "seamless", "robust" außerhalb von Fachkontext, "leverage" als Verb, "supercharge", "elevate", "game-changer", "at its core", "when it comes to".

### R4.3 Partizip-Anhängsel

Das Muster Hauptsatz plus Komma plus Partizip ist der auffälligste Satzbau-Marker überhaupt.

Verboten als Automatismus: "..., wodurch sich X ergibt", "..., was es ermöglicht", "..., ensuring that", "..., allowing you to", "..., making it easier to", "..., resulting in".

Ersatz: eigener Satz. Aus "Der Cache speichert die Antworten, wodurch sich die Latenz halbiert" wird "Der Cache speichert die Antworten. Die Latenz halbiert sich."

Frequenzgrenze: höchstens eines pro 300 Wörter.

### R4.4 Verbalstil statt Nominalstil

Deutschspezifisch und wirksam. Substantivierungen auf -ung, -heit, -keit, -ierung auflösen.

"Die Durchführung der Migration erfolgt nachts" wird zu "Wir migrieren nachts."

Prüfung: Zähle Wörter auf -ung im Text. Über 15 pro 1000 Wörter ist zu viel. `TODO Korpus`.

### R4.5 Aktiv vor Passiv

Passiv ist erlaubt, wenn der Handelnde egal oder unbekannt ist. Sonst Aktiv. Passivanteil höchstens 20 Prozent der Sätze im Fachtext, höchstens 10 Prozent in der Kurzform.

### R4.6 Hedging dosieren

"könnte", "möglicherweise", "unter Umständen", "tendenziell", "in der Regel". Jedes einzeln ist in Ordnung. Gehäuft entsteht der typische Ton ohne Haltung.

Grenze: höchstens drei Hedges pro 300 Wörter. Wo Unsicherheit besteht, wird sie einmal klar benannt statt in jedem Satz angedeutet.

## 5. Substanz

### R5.1 Konkret vor abstrakt

Jeder Absatz mit einer Behauptung enthält mindestens ein konkretes Element: eine Zahl, einen Namen, einen Befehl, einen Dateipfad, ein Datum, ein reales Beispiel.

Verboten: "verschiedene Faktoren", "zahlreiche Vorteile", "viele Unternehmen", "in vielen Fällen", ohne dass irgendwo steht welche.

### R5.2 Keine erfundene Konkretion

Die Gegenregel zu R5.1 und sie ist wichtiger. Wenn keine echte Zahl vorliegt, wird keine erfunden. Dann lieber allgemein bleiben und das kenntlich machen.

Ebenso verboten: erfundene Ich-Erfahrungen, erfundene Anekdoten, erfundene Zitate, erfundene Quellenangaben.

### R5.3 Haltung

Wo eine Empfehlung gefragt ist, steht eine. "Nimm Postgres" statt "Beide Optionen haben ihre Berechtigung". Die Begründung folgt, die Gegenseite darf vorkommen, aber nicht als Ausweichmanöver.

### R5.4 Alt vor Neu

Nach Gopen und Swan: Ein Satz beginnt mit dem, was der Leser schon kennt, und endet mit dem Neuen. Das Wichtige steht am Satzende, nicht in der Mitte.

Schwach: "Ein Timeout von 30 Sekunden ist in der Konfiguration die Ursache für die Abbrüche."
Besser: "Die Abbrüche kommen aus der Konfiguration. Dort steht ein Timeout von 30 Sekunden."

### R5.5 Keine gefakten Fehler

Menschlicher Text wird nicht durch eingebaute Tippfehler menschlicher. Rechtschreibung und Grammatik bleiben korrekt. Die Variation entsteht durch Rhythmus und Konkretion, nicht durch Schlamperei.

## 6. Registerprofile

### Fachtext und Doku

* Mittlere Satzlänge 13 bis 18 Wörter.
* Passiv bis 20 Prozent, wo der Handelnde wirklich egal ist.
* Fachbegriffe stehen ohne Entschuldigung da, wenn die Leser sie kennen.
* Fragmente sparsam.
* Erste Person Plural nur, wenn es wirklich ein Team gibt.

### Kurzform, Mail, Chat, Kommentar

* Mittlere Satzlänge 9 bis 14 Wörter.
* Keine Überschriften, keine Listen unter vier Punkten.
* Direkte Anrede, kein Vorspann. Die erste Zeile enthält den Punkt.
* Keine Begrüßungsfloskel mit Wetterbezug, keine Schlussformel mit "Ich hoffe, das hilft".
* Fragmente und Umgangssprache erlaubt.

## 7. Modus B: Ablauf beim Überarbeiten

1. **Messen.** Prüfskript über den Originaltext. Werte notieren.
2. **Diagnose.** Liste der Fundstellen nach Regelnummer. Keine Änderung ohne Regelbezug.
3. **Rückfrage bei Faktenlücken.** Wenn R5.1 eine Konkretion verlangt, die im Original fehlt, wird gefragt statt erfunden.
4. **Umschreiben.** In dieser Reihenfolge: Zeichen, Struktur, Satzbau, Wortwahl. Struktur zuerst, weil sich Satzprobleme danach oft erledigt haben.
5. **Faktenabgleich.** Jede Aussage des Originals muss im Ergebnis stehen und umgekehrt. Keine neue Behauptung.
6. **Nachmessen.** Prüfskript erneut. Werte vorher und nachher ausgeben.
7. **Bericht.** Drei bis fünf Zeilen, was geändert wurde und warum. Keine Lobrede auf das Ergebnis.

Eingriffstiefe auf Zuruf: leicht heißt nur Zeichen und tote Phrasen, mittel heißt zusätzlich Satzbau und Rhythmus, stark heißt Struktur darf sich ändern.

## 8. Selbstprüfung

Vor der Ausgabe abarbeiten. Mechanisch prüfbar, deshalb skriptfähig.

1. Geviertstrich, Gedankenstrich, Semikolon: null Treffer.
2. Liste der toten Phrasen aus R4.1 und R4.2: null Treffer.
3. Partizip-Anhängsel: höchstens eines pro 300 Wörter.
4. Je zehn Sätze: ein kurzer, ein langer, Streuung über 40 Prozent.
5. Kein Absatzanfang mit Konnektor.
6. Kein Text-Rahmen aus Ankündigung und Zusammenfassung.
7. Jeder Behauptungsabsatz hat ein konkretes Element.
8. Keine erfundene Zahl, kein erfundenes Zitat.
9. Anteil Dreier-Aufzählungen unter 50 Prozent.
10. Wörter auf -ung unter 15 pro 1000.

## 9. Beispiele

### Beispiel 1, Fachtext Deutsch

Vorher:

> In der heutigen Softwareentwicklung spielt Caching eine entscheidende Rolle. Es ist wichtig zu beachten, dass ein gut konfigurierter Cache nicht nur die Latenz reduziert, sondern auch die Last auf der Datenbank senkt, wodurch sich die Gesamtperformance des Systems deutlich verbessert. Darüber hinaus gibt es verschiedene Strategien, die je nach Anwendungsfall ausgewählt werden sollten. Zusammenfassend lässt sich sagen, dass Caching ein mächtiges Werkzeug ist.

Nachher:

> Ein Cache nimmt der Datenbank Arbeit ab. Bei uns fällt die Latenz von 400 auf 60 Millisekunden, und die Zahl der Queries sinkt um etwa zwei Drittel.
>
> Welche Strategie passt, hängt davon ab, wie oft sich die Daten ändern. Für Stammdaten reicht ein TTL von einer Stunde. Für Preise nicht.

Was passiert ist: R3.5 Rahmen weg, R4.1 tote Phrasen weg, R4.3 Partizip-Anhängsel aufgelöst, R5.1 Zahlen rein, R2.4 Fragment am Ende, R2.1 Streuung.

### Beispiel 2, Englisch

Vorher:

> When it comes to error handling, it is important to note that a robust strategy is pivotal for maintaining system reliability — ensuring that failures are caught early, logged appropriately, and surfaced to the right people.

Nachher:

> Error handling breaks in a predictable way: the failure happens in one place and shows up in another. Catch it where it happens. Log enough context that the next person can reconstruct the call, and route the alert to whoever can actually fix it.

Was passiert ist: R1.1 Geviertstrich weg, R4.2 "when it comes to", "it is important to note", "pivotal", "robust" weg, R4.3 Partizip-Anhängsel aufgelöst, R3.3 Trikolon aufgebrochen, R2.1 Streuung.

### Beispiel 3, Kurzform

Vorher:

> Hallo zusammen, ich hoffe, es geht euch gut. Ich wollte mich kurz melden bezüglich des Deployments von gestern Abend. Leider ist es zu einigen unerwarteten Problemen gekommen, die dazu geführt haben, dass der Service für eine gewisse Zeit nicht verfügbar war. Wir arbeiten mit Hochdruck an einer Lösung. Ich hoffe, das hilft.

Nachher:

> Das Deployment gestern hat den Service von 21:40 bis 22:15 lahmgelegt. Ursache war eine Migration, die auf der Prod-Datenbank länger lief als im Test.
>
> Läuft wieder. Rollback-Plan steht für heute Abend, falls es nochmal kippt.

Was passiert ist: R6 Kurzform, Vorspann und Schlussformel weg, R5.1 Zeiten und Ursache rein, R4.5 Aktiv, R2.4 Fragment.

## 10. Offene Punkte

* `TODO Korpus`: Zielkorridore in R2.1, R4.4 und R4.5 gegen ein eigenes Referenzkorpus prüfen. Die aktuellen Zahlen sind plausible Schätzungen, keine Messwerte.
* Verhältnis zu einem persönlichen Stilprofil festlegen. Vorschlag: Diese Spec ist die Untergrenze, das Stilprofil überschreibt im Konfliktfall.
* Prüfskript schreiben, das Punkt 1 bis 10 aus Abschnitt 8 automatisch misst.
* Entscheiden, ob Modus A bei jedem Text greift oder ab einer Mindestlänge.
