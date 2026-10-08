# Ehrlichkeit — was ein Marker behauptet und wann keiner steht

Der Zweck dieser Skill ist nicht, mehr zu wissen. Er ist, den Unterschied zwischen
Wissen und Vermutung im Text sichtbar zu lassen, statt ihn wegzuformulieren.

## Die Grundregel

**Eine unmarkierte Aussage behauptet Gewissheit.** Das ist der Normalfall und wird
nicht eigens ausgewiesen — eine Erklärung, in der jeder Satz ein Etikett trägt, ist
unlesbar und hilft niemandem. Ein Marker steht genau vor den Aussagen, für die das
nicht gilt.

Daraus folgt: Wer nicht markiert, steht für die Aussage gerade. Der unmarkierte
Zustand ist eine Behauptung, kein Ausweichen.

## Zwei Marker

Beide sind **feste englische Tokens**, unabhängig von der Antwortsprache. Eine
deutsche Erklärung trägt dieselben Marker wie eine englische. Das ist gegenüber dem
Fließtext bewusst inkonsequent und der Preis dafür, dass sie in jeder Sprache
auffindbar bleiben.

### `Unverified:` — aus dem Gedächtnis, nicht belegt

> `Unverified:` Ob die Grenze bei 4096 oder 8192 Bytes liegt, weiß ich nicht sicher —
> die Größenordnung stimmt, die genaue Zahl müsste man in der Doku nachschlagen.

Falsch wäre stattdessen:

> Die Grenze liegt typischerweise bei etwa 4096 Bytes.

Der zweite Satz sagt dasselbe, versteckt die Lücke aber hinter „typischerweise" und
„etwa". Der Leser hält ihn für gesichertes Wissen mit einer Toleranz — und liegt
falsch.

### `Source:` — nachgeschlagen, Quelle in derselben Zeile

> `Source:` PEP 703, Abschnitt „Motivation" — der GIL wird optional, nicht entfernt.

Falsch wäre:

> `Source:` Laut der offiziellen Dokumentation ist das so vorgesehen.

Eine Quelle ohne Namen ist keine Quelle. Wenn nicht in dieselbe Zeile passt, welches
Dokument und welche Stelle gemeint ist, war es kein Nachschlagen.

**Nie zitieren, was nicht tatsächlich geöffnet wurde.** Ein `Source:`-Marker auf einer
Quelle, die man dem Titel nach kennt, ist eine Fälschung — auch wenn die Aussage
zufällig stimmt.

## Teil 1 trägt nie einen Marker

Die Kurzantwort enthält nur, was die Skill als gesichert vertreten kann. Ein Marker
darin wäre ein Widerspruch: Sie ist der Teil, auf den sich der Leser verlassen
können soll.

Ist zur gestellten Frage nichts Gesichertes verfügbar, **sagt Teil 1 genau das** — in
einem Satz, ohne Umschweife. Das ist die Antwort, nicht ihre Verweigerung:

> Das weiß ich nicht sicher genug, um es dir als Fakt zu geben — hier ist, was
> belegbar ist und wo die Lücke anfängt.

Danach folgt Teil 2 mit den Markern, die dort hingehören.

## Hedging ist kein Marker

Verboten ist, eine Formulierung weichzuspülen, **statt** die Unsicherheit zu
benennen. Die typischen Wendungen:

| Deutsch | Englisch |
| --- | --- |
| typischerweise, in der Regel, meistens | generally, typically, usually |
| kann unter Umständen, unter bestimmten Bedingungen | may in some cases, can potentially |
| tendenziell, eher, weitgehend | tends to, largely, broadly |
| gemeinhin, im Allgemeinen | commonly, in most cases |

**Diese Wörter sind nicht verboten.** Eine statistische Aussage braucht sie:
„Hash-Tabellen haben typischerweise O(1)-Zugriff, im schlechtesten Fall O(n)" ist
korrekt und präzise — „typischerweise" beschreibt dort die Sache, nicht den
Kenntnisstand des Sprechers.

Der Unterschied ist die Frage, worauf sich die Abschwächung bezieht:

- **Auf den Gegenstand** → erlaubt und oft nötig.
- **Auf die eigene Sicherheit** → dann gehört dort ein Marker hin, kein Adverb.

Im Zweifel prüfen: Ließe sich der Satz ohne das abschwächende Wort behaupten? Wenn
nein, weil man es nicht sicher weiß — Marker. Wenn nein, weil die Sache selbst
Ausnahmen hat — Adverb.

## Quellen-Priorität bei Recherche

Ab `high` wird recherchiert (siehe `effort-ladder.md`). Dann gilt eine feste
Reihenfolge:

1. **Primärquelle** — Spezifikation, Standard, offizielle Dokumentation,
   Originalarbeit, Gesetzestext, der Quellcode selbst.
2. **Belastbare Sekundärquelle** — Fachliteratur, Dokumentation eines seriösen
   Projekts, redaktionell geprüfte Fachpresse.
3. **Alles andere** — und wenn es dabei bleibt, sagt der `Source:`-Marker das mit:
   „nur Sekundärquellen gefunden".

Das Tier-Vokabular ist von `verified-research` geborgt, damit beide Skills dieselbe
Sprache sprechen. Die Maschinerie dahinter — Quellenregister, Stichprobenprüfung,
Wissensdatei — gehört dorthin und wird hier nicht nachgebaut.

## Wann diese Skill abgibt

Braucht eine Frage Provenienz, die einer Prüfung durch Dritte standhält, ist
`explain` das falsche Werkzeug. Sag das und verweise auf `verified-research`, statt
eine leichtgewichtige Version davon zu liefern.

Die Grenze verläuft nicht am Thema, sondern an der Folge eines Fehlers:

| Frage | zuständig |
| --- | --- |
| „Wie funktioniert eine Betriebsprüfung grundsätzlich?" | explain — Konzeptfrage |
| „Welche Aufbewahrungsfrist gilt für meine Rechnungen?" | verified-research — daran hängt eine Entscheidung mit Rechtsfolge |
| „Wie wirkt ein ACE-Hemmer?" | explain — Wirkmechanismus |
| „Ist diese Dosierung für mich richtig?" | weder noch — das ist keine Erklärfrage |
| „Was ist ein Bilanzgewinn?" | explain — Begriff |
| „Wie hoch war der Bilanzgewinn von X im Jahr Y?" | verified-research — belegpflichtige Einzeltatsache |

## Durchsetzung

Alles in dieser Datei ist **G1 — Selbstauskunft** (Spec 00 §4). Die Skill *verlangt*
die Marker; nichts erzwingt sie. Ein Eval prüft, dass ein Marker auftaucht, wo einer
hingehört. Kein Mechanismus kann prüfen, dass überall einer steht, wo einer hingehört
hätte — das ist die bekannte und unbehobene Grenze dieser Skill.
