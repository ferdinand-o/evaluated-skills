<!-- skill: -- | schema: 1 | generated: von Hand, aus den Befunden von vierzehn Skill-Bauten -->
# Fehlerklassen beim Skill-Bau

Destillat aus dem Bau von vierzehn Skills, ebenso vielen unabhängigen Reviews und
über hundert echten Eval-Läufen. **Jede Klasse hier ist real aufgetreten**, meist
mehrfach und in verschiedenen Skills. Kein Autor hat seinen eigenen schwersten
Fehler selbst gefunden — deshalb steht das hier und nicht im Kopf.

Lies das vor dem Bau einer Skill und noch einmal vor dem Schreiben ihrer Evals.

## Die eine Frage

Fast jeder schwere Fund lässt sich auf dieselbe Frage zurückführen:

> **Wo meldet etwas Erfolg, ohne geprüft zu haben?**

Sie hat geliefert: ein Gate, das eine Migration freigab, die es nie gesehen hatte;
einen Export, der eine nie geprüfte Aufgabe als geprüft auswies; ein `verify`, das
ohne seine Eingabe PASS meldete; einen Drift-Check, der „kein Drift" sagte, weil er
nichts vergleichen konnte. Stell sie an jeder Stelle, an der dein Code ein Urteil
ausgibt.

## Im Code

**Was nicht erkannt wurde, ist nie „in Ordnung".** Null Ergebnisse aus einer
nichtleeren Eingabe sind ein eigener Befund. Ein Scanner, der aus einem nichtleeren
`upgrade()` keine Operation liest, hat nicht geprüft — er hat nichts gefunden. Das
ist ein Unterschied, und die Ausgabe muss ihn machen.

**`all([])` ist `True`.** Eine leere Kriterienliste macht jede Prüfung wahr. Such
in deinem Code nach `all()` und `any()` über Listen, die leer sein können.

**Der Rand ist die Regel, nicht die Ausnahme.** Eine Zusage, die an einem einzelnen
Auslöser hängt, deckt genau diesen Fall ab. Formulier sie von der Zusage her:
nicht „bei Sitzungsende schreiben", sondern „wenn etwas passiert ist, schreiben".
Sonst repariert jeder Fix einen Fall und reißt einen anderen auf — real zweimal
hintereinander passiert.

**Ableiten schlägt Validieren.** Ein Statusfeld, das jemand setzen kann, wird
gesetzt — auch entgegen der Doktrin. Berechne es aus den Rohdaten, dann kann es
ihnen nicht widersprechen. Ein redundantes Feld, das beschreibbar bleibt, ist die
Fehlerquelle, nicht die Prüfung darauf.

**Analysier statisch, importier nicht.** Fremden Code zu importieren führt ihn aus:
Datenbankverbindungen, Netzwerk, Konfiguration. Eine Skill, die ein Repo *erfassen*
soll, darf es nicht dabei starten. `ast` reicht fast immer und ist nebenbei Tier 1.

**Tier 1 ist der Standard, und meist die einzige Wahl.** Eine nicht installierte
Abhängigkeit macht eine Skill unprüfbar — sie ginge ungeprüft raus. Prüf vor jedem
Tier 2, ob die Stdlib reicht; bei diesen vierzehn Skills reichte sie fast immer.

## In der Doktrin

**Beispiele schlagen Vorschriften.** Widerspricht ein Beispiel der Regel zwei
Abschnitte darüber, folgt der Agent dem Beispiel. So wurde der Artefakt-Header
gebrochen. Prüf jedes Beispiel gegen die Regel, unter der es steht.

**Die Abgrenzungsklausel verschluckt den Pflichtfall.** Eine Description, die sich
sorgfältig von einer Nachbar-Skill abgrenzt, kann sich dabei vom eigenen
vorgeschriebenen Szenario ausschließen — zweimal passiert, einmal beim
Anti-Zeremonie-Fall, einmal bei einem Verbot, das auch legitime eigene Fragen
mitverbot.

**Ein Contract darf nicht mehr versprechen, als sein Gate hält.** „Gilt nur bei
valider Begründung als kaputt" ist falsch, wenn der Mechanismus jede Fehlwahl
gleich markiert. Zieh die Formulierung auf das zurück, was wirklich geleistet wird.

**Doktrin ist G1 und kann versagen.** Eine verschärfte SKILL.md wurde gemessen und
hat nicht gehalten; erst der Mechanismus half. Wo etwas mechanisch prüfbar ist,
gehört kein Appell hin.

## In den Evals

**Ein Ergebnis ist eine Stichprobe.** Derselbe Eval, derselbe Commit, einmal rot,
einmal grün — mehrfach belegt. Es schwankt, *ob* eine Skill geladen wird, *wie
weit* sie ihren Ablauf durchläuft, und ob ein Judge zustimmt. **Vor jeder Fix-Runde
gehört ein zweiter Lauf**, sonst repariert man eine funktionierende Skill.

**Zusammengesetzte Judge-Claims verdecken Defekte.** Ein Claim mit verketteten
Bedingungen („erkennt X und tut Y statt Z") wird bejaht, wenn der Judge eine
Bedingung erfüllt sieht — auch wenn die wichtigste verletzt ist. Zerleg ihn, und
zieh jede mechanisch prüfbare Bedingung ganz aus dem Judge heraus.

**Prüf Struktur, nicht Wortlaut.** Eine Regex, die nur „keine … fällig" kennt,
fällt an „kein Thema fällig". Und was du prüfst, muss die SKILL.md auch fordern —
sonst prüfst du eine Formulierung, die nie versprochen wurde.

**`must_not` plus Abwesenheit ist eine doppelte Verneinung.** `must_not:
file_absent` heißt „die Datei muss existieren". Fast immer ein Denkfehler.

**Die Fixture muss die Vorbedingung ihrer Assertion herstellen.** Ohne
`"git": true` gibt es kein Repo, Artefakte landen außerhalb des Workspace, und
keine Assertion sieht sie. Das hat sechs Evals auf einmal falsch rot gemacht.

**Fremde Skills sind sichtbar** — gemessen sechzehn, trotz Isolationsflagge. Eine
Assertion, die eine fremde Skill genauso erfüllen könnte, belegt nichts über deine.
Häng sie an Artefakte, die nur deine Skill erzeugt.

**Prüf die eiserne Regel deiner Skill.** `architecture-map` existiert, damit
Diagramme generiert statt gemalt werden — und kein Eval prüfte das. Ein
handgezeichnetes Diagramm mit den richtigen Wörtern bestand alle.

**Ein Budget wird nicht nachgezogen, bis es passt.** Erst zählen, was die Fixture
überhaupt erzwingt. Bei einem Fall waren es drei Funde bei sechzig erlaubten Zeilen
— das Budget war großzügig, die Ausgabe geschwätzig. Die Zahl anzuheben hätte den
Eval zur Formalie gemacht.

## In den Tests

**Die Verdrahtung ist ungetestet.** Reine Funktionen zu testen und ihre Verbindung
auszulassen hat eine Regression durch 154 grüne Tests spazieren lassen.

**Ein Test, der nicht fehlschlagen kann, ist Dekoration.** Bau die Regression
einmal wieder ein und sieh zu, dass der Test fällt. `assert "x" in str(e) or
e["reason"]` ist wegen Operatorpriorität immer wahr.

## Über Schnittstellen

**Parallel gebaute Skills prüfen jede ihre eigene Annahme.** Ein Erzeuger schrieb
ein Objekt, der Konsument erwartete ein Array — beide Testsuiten grün, beide
Reviews sauber, jede real erzeugte Datei wäre als fehlerhaft gemeldet worden.
Sichtbar wurde es nur, weil ein Autor seine Annahme als Annahme meldete. Leg beide
Seiten nebeneinander, bevor du sie für fertig hältst.
