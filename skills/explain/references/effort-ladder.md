# Die Effort-Leiter — fünf Stufen, je an einer Zutat erkennbar

Der Regler steuert zwei Dinge zugleich: wie viel vor der Antwort untersucht wird und
wie tief Teil 2 geht. Er steuert **nie** die Kurzantwort — die ist auf jeder Stufe
höchstens vier Sätze lang.

Die Stufen sind kumulativ. Jede enthält alles Vorherige und fügt **eine** benennbare
Schicht hinzu. Das ist der Prüfmaßstab dieser Datei: Wer zwei Antworten sieht, muss
sie allein anhand der zusätzlichen Schicht der richtigen Stufe zuordnen können. Eine
Stufe, die nur „ausführlicher" ist als die vorige, ist keine Stufe.

## Die fünf Stufen

| Stufe | Zusätzliche Schicht in Teil 2 | Teil 3 (`Next:`) | Recherche |
| --- | --- | --- | --- |
| `low` | der Mechanismus, ein Absatz, sonst nichts | entfällt | nein |
| `medium` | warum es so gebaut ist; ein durchgerechnetes Beispiel | ja | nein |
| `high` | Randfälle, verbreitete Missverständnisse, Geltungsgrenzen | ja | ja |
| `xhigh` | konkurrierende Erklärungen desselben Gegenstands und ihre Abwägung | ja | ja |
| `max` | Herkunft, Entwicklung, offene Streitfragen, Primärquellen | ja | ja |

`medium` ist der Default, wenn keine Stufe erkennbar ist.

## Dieselbe Frage über alle Stufen

Frage: **„Warum ist eine Hash-Tabelle im Durchschnitt O(1)?"**

Die Kurzantwort ist auf jeder Stufe dieselbe Größenordnung: *Weil die Hash-Funktion
den Schlüssel direkt in einen Index umrechnet, statt zu suchen — die Kosten hängen
damit nicht von der Anzahl der Einträge ab, solange die Kollisionen selten bleiben.*

**`low`** — ein Absatz Mechanismus: Schlüssel → Hash → Index → Zugriff. Fertig.

**`medium`** — dazu: warum das so gebaut wurde (Suchen kostet Vergleiche, Rechnen
kostet keinen), plus ein durchgerechnetes Beispiel mit drei Schlüsseln, einer
Tabellengröße und den konkreten Indizes.

**`high`** — dazu: der Worst Case O(n), wenn alle Schlüssel kollidieren; das
verbreitete Missverständnis, „O(1) heißt schnell" (es heißt: unabhängig von n, die
Konstante kann groß sein); die Geltungsgrenze, dass der Load Factor unter einer
Schwelle bleiben muss und Rehashing amortisiert eingerechnet gehört.

**`xhigh`** — dazu: die konkurrierenden Kollisionsmodelle nebeneinander — Verkettung
gegen offene Adressierung gegen Cuckoo-Hashing — mit der Abwägung, welche Annahme
über Speicherlayout und Löschhäufigkeit welches Verfahren gewinnen lässt. Nicht drei
Beschreibungen, sondern der Vergleich: Wo widersprechen sie sich, und woran entscheidet
es sich?

**`max`** — dazu: woher das Verfahren kommt (Hans Peter Luhn, IBM, 1953, als internes
Memo — nicht als Publikation), wie die amortisierte Analyse erst später sauber wurde,
und was heute noch offen ist (Worst-Case-Garantien ohne Randomisierung, adversariale
Hash-Kollisionen als Angriffsfläche). Mit Primärquellen, wo greifbar.

## Warum `xhigh` und `max` zwei Stufen sind

Das ist die Trennung, an der diese Leiter steht oder fällt — die vier anderen Stufen
sind unstrittig, `xhigh` ist die einzige ohne Vorbild in dieser Sammlung
(`/code-review` fährt vier Stufen).

- **`xhigh` blickt in die Breite:** Welche *anderen* Erklärungen desselben
  Gegenstands gibt es, und warum wählt man welche? Der Gegenstand bleibt derselbe,
  die Modelle konkurrieren.
- **`max` blickt in die Tiefe der Zeit:** Woher kommt diese Erklärung, wie ist sie
  entstanden, wer streitet heute worüber, und was sagen die Originalquellen?

Ein Test dafür: `xhigh` beantwortet „was hätte man stattdessen denken können?",
`max` beantwortet „wie ist man darauf gekommen, und ist es zu Ende gedacht?". Wer bei
einer Frage zwischen beiden nicht unterscheiden kann, weil der Gegenstand keine
konkurrierenden Modelle hat, nimmt `max` und sagt, dass `xhigh` hier zusammenfällt —
statt eine Modelldiskussion zu erfinden, die es nicht gibt.

## Stufenerkennung

Der Aufruf ist natürlichsprachlich. Die Slash-Form `/explain <Thema> <effort>` ist
eine Kurzschreibweise für Umgebungen, die sie kennen — im Zielsystem claude.ai/Cowork
gibt es sie nicht, und keine Regel darf sie voraussetzen.

| Formulierung | Stufe |
| --- | --- |
| „kurz", „in einem Satz", „überblicksmäßig", „nur grob" | `low` |
| keine Angabe | `medium` |
| „ausführlich", „genauer", „mit Beispielen", „richtig erklären" | `medium` bis `high` → `high` nur bei „genauer"/„ausführlich" |
| „gründlich", „mit allen Fallstricken", „worauf muss ich achten" | `high` |
| „welche Ansätze gibt es", „im Vergleich", „Alternativen abwägen" | `xhigh` |
| „in aller Tiefe", „alles dazu", „mit Quellen", „woher kommt das" | `max` |

**Bei Mehrdeutigkeit gilt die niedrigere Stufe**, und die gewählte wird genannt — ein
Halbsatz am Ende von Teil 1 oder zu Beginn von Teil 2 reicht: „(auf `medium`
erklärt — sag Bescheid, wenn du tiefer willst)". Eine Rückfrage *vor* der Antwort ist
keine Option; sie kostet einen Zug und bringt nichts, was die Nennung nicht auch
leistet.

Nennt die Anfrage eine Stufe wörtlich (`low`, `medium`, `high`, `xhigh`, `max`), gilt
sie unverändert, auch wenn die übrige Formulierung etwas anderes nahelegt.

## Recherche-Kopplung

`low` und `medium` recherchieren **nicht**. Unsicheres wird markiert
(`references/honesty.md`), nicht nachgeschlagen. Das ist kein Mangel, sondern der
Punkt: Wer schnell eine Orientierung will, wartet nicht auf eine Websuche.

Ab `high` wird recherchiert, nach der Quellen-Priorität aus `honesty.md`. Findet die
Recherche nichts Belastbares, bleibt es bei `Unverified:` — eine erfolglose Suche
macht aus einer Vermutung keine Tatsache und wird als erfolglos benannt.
