# Narration schreiben: Schichten benennen, Einstiegspfade erklären

Die Narration ist der einzige Teil von `ARCHITECTURE.md`, den das LLM formuliert — der
Graph selbst kommt ausschließlich aus den Skripten. Zwei Regeln halten das auseinander.

## Fakt vs. Einschätzung

Jede Struktur-Behauptung ("Modul X hängt von Y ab", "es gibt einen Zyklus zwischen A und
B") muss im Graph-JSON belegbar sein — sie beschreibt eine Kante oder einen Befund, der
tatsächlich extrahiert wurde. Eine Aussage, die das nicht ist ("dieses Modul wirkt wie
der zentrale Einstiegspunkt", "diese Aufteilung folgt vermutlich Domain-Driven Design"),
ist eine Beobachtung — sie wird als solche markiert: **„Beobachtung (nicht
graph-belegt): …"**. Genau wie bei `dev-report`s „Einschätzung:"-Regel gilt: ohne
Markierung gehört der Satz nicht in den Text.

## Schichten benennen

Wenn `layers.json` existiert, übernimm ihre Namen unverändert — sie sind die vom Nutzer
gewählte Sprache für sein System. Wenn sie fehlt, leite Schichtnamen nur vorsichtig aus
der Verzeichnisstruktur ab (`domain/`, `api/`, `infra/` sind übliche Konventionen) und
markiere das als Beobachtung, nie als bestätigte Architektur — dafür bräuchte es die
Konfiguration.

## Verantwortlichkeiten je Modul/Schicht

Eine kurze, konkrete Beschreibung: was lebt hier, warum ist es von den Nachbarn
getrennt. Kein Nacherzählen des Codes ("hier steht eine Funktion `parse()`, die einen
String nimmt und …") — das liest jeder selbst. Stattdessen die Frage beantworten: warum
gibt es diese Grenze, was würde brechen, wenn man sie auflöst.

## Einstiegspfade für Neue

Mindestens ein Satz pro Ebene: "Wenn du an X arbeiten willst, fang bei Y an." Das ist
der eigentliche Nutzwert der Kontext- und Modul-Ebene für jemanden, der die Codebase
nicht kennt — wichtiger als Vollständigkeit.

## Befund-Einschätzung

Für jeden Befund aus `references/finding-catalog.md`: eine Zeile, ob er real
problematisch ist oder eine bewusste Ausnahme — mit Begründung. „Der Zyklus ist
bestimmt Absicht" ohne Begründung ist keine Einschätzung, das ist die
Anti-Rationalisierung aus der SKILL.md. Eine Ausnahme, die dokumentiert wird, bleibt
im Dokument stehen; sie wird nicht stillschweigend aus der Befund-Liste entfernt — die
Liste selbst kommt unverändert aus `analyze_graph.py`.
