# Die vier Formate

Jedes Format hat ein hartes Zeilenbudget für die Markdown-Fassung (mechanisch
zählbar, deshalb die verbindliche Zahl) und eine strukturgleiche HTML-Fassung,
deren Budget nur per Sichtprüfung gilt (siehe `SKILL.md`, Selbst-Audit). Die
Zeilenzahl zählt die **gesamte** Datei inklusive Kopfzeile, Überschriften und
Quellenliste.

## one-pager — Überblick für Dritte

**Wann:** Kein Entscheidungsbedarf, jemand soll in einer Minute verstehen, worum
es geht.

**Aufbau:**
1. Kernthese (eine Überschrift, ein Satz)
2. Drei Belege — genau drei, wenn das Material sie hergibt; weniger, wenn nicht;
   nie mehr (sonst ist es kein One-Pager mehr, sondern ein Dossier)
3. Ein Chart, **nur** wenn ein Datenpunkt-Set eine Frage beantwortet, die die
   Kernthese aufwirft — sonst entfällt der Chart-Slot ausdrücklich, keine
   Alibi-Grafik
4. Quellenliste

**Budget (Markdown):** ≤ 60 Zeilen.

**Leerfall:** Weniger als drei Belege im Material → weniger Belege im Output,
keine Erfindung des dritten.

## decision-memo — Entscheidung steht an

**Wann:** Der Leser muss zwischen Optionen wählen oder eine Empfehlung
gegenzeichnen.

**Aufbau:**
1. Entscheidungsfrage (eine Überschrift, ein Satz)
2. Optionen-Matrix (Tabelle: Option, Für, Gegen, Aufwand/Risiko) — höchstens vier
   Optionen; mehr heißt, die Optionen sind nicht genug vorgefiltert
3. Empfehlung mit Begründung
4. Risiken
5. Offene Punkte — „Keine.", wenn es keine gibt
6. Quellenliste

**Budget (Markdown):** ≤ 80 Zeilen (die Matrix braucht mehr Platz als ein
One-Pager).

**Leerfall:** Keine Risiken erkennbar → „Keine erkennbaren Risiken." statt
Auslassen der Sektion (bei einer Entscheidung ist das Fehlen von Risiken selbst
eine Aussage, die der Leser prüfen will).

## timeline-brief — Verlauf/Entwicklung

**Wann:** Der Leser will nachvollziehen, wie es zum jetzigen Stand kam, nicht nur
was der Stand ist.

**Aufbau:**
1. Kernthese: die Entwicklung in einem Satz
2. Chronologie — je Eintrag Zeitpunkt/Phase, Ereignis, Referenz; Wendepunkte
   sichtbar hervorgehoben (nicht nur ein Eintrag unter vielen)
3. Ausblick/offene Fragen
4. Quellenliste

**Budget (Markdown):** ≤ 70 Zeilen.

**Leerfall:** Kein erkennbarer Wendepunkt → keiner wird markiert. Eine erfundene
Zäsur ist schlimmer als eine flache Chronologie.

## learn-card — eigenes Lernen

**Wann:** Ein Konzept soll sitzen bleiben, nicht nur dokumentiert sein. Das
knappste Format.

**Aufbau:**
1. Kernidee (ein Satz)
2. Beispiel (konkret, keine Abstraktion zweiter Ordnung)
3. Abgrenzung — wovon unterscheidet sich das, was wird oft verwechselt
4. Merksatz — ein einprägsamer Ein-Zeiler, visuell abgesetzt
5. Quelle(n) — meist ein bis zwei

**Budget (Markdown):** ≤ 40 Zeilen.

**Leerfall:** Kein Verwechslungsrisiko erkennbar → „Keine bekannte Verwechslung."
statt eine erfundene Abgrenzung.

## Format-Wahl bei Unklarheit

Trägt die Anfrage weder ein erkennbares Publikum noch einen erkennbaren
Zweck, wird nicht geraten — die zwei Triage-Fragen aus `SKILL.md` werden gestellt.
Ein zufällig gewähltes Format bei fehlendem Kontext ist der Fehler, den die
Triage verhindern soll.
