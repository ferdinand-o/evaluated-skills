# Review-Auftrag je Paket

Referenz für den Hauptagenten (Ablauf Schritt 4). Hier steht, was du einem Reviewer je Paket
sagst und in welcher Form das Ergebnis zurückkommt, in drei Fassungen:

| Fassung | wann |
| --- | --- |
| [Fokus `bugs` mit `/code-review`](#fassung-1-code-review-fokus-bugs) | Normalfall, auch Profil `checkpoint` |
| [Fokus `quality`](#fassung-2-fokus-quality) | „Wartbarkeit“, „Qualität“, „Code-Hygiene“ |
| [Review ohne /code-review](#review-ohne-code-review) | `/code-review` ist nicht verfügbar (claude.ai, andere Agenten) |

Fokus `security` ruft `/security-review` einmal für das Paket `s1` auf, mit den Gegenstellen
aller Dateien als Kontext. Es gilt dasselbe [Rückgabeformat](#rückgabeformat).

Wie `packets/<id>.md` aufgebaut ist und wie ein Reviewer es liest, steht in
[counterparts.md](counterparts.md): [Zeilenformat des Paketblocks](counterparts.md#zeilenformat-des-paketblocks)
und [Lesehilfe für den Reviewer](counterparts.md#lesehilfe-für-den-reviewer). Was im Auftrag
unter „Bereich“ steht, erklärt [packets.md](packets.md#paket-bereich-was-der-reviewer-sieht).
Beides wird hier nicht wiederholt.

## Fassung 1: `/code-review`, Fokus `bugs`

Je Paket in Plan-Reihenfolge ein Aufruf:

```
/code-review --max-findings all <von>..<bis>
```

- `<von>..<bis>` ist das `range` des Pakets, so wie `counterparts` es je Paket ausgibt
  (`<id>: <bereich> · …`). Bei `split: false` ist das der Originalbereich.
- Den Inhalt von `packets/<id>.md` gibst du **jedem Unteragenten unverändert** mit: nicht
  gekürzt, nicht umformuliert, nicht nach Verdacht ausgewählt. Auch der Satz zu den nicht
  aufgelösten Stellen und eine Kappung bleiben stehen.
- Bei Delphi-Dateien im Paket gibst du zusätzlich [delphi.md](delphi.md) mit.
- Im Profil `checkpoint` hängst du das Soll aus `--soll-file` an, als eigenen Abschnitt
  „Soll“ unter dem Auftrag.

Auftrag an den Reviewer (Platzhalter in `<…>` ersetzt du):

> Prüfe die Änderung `<von>..<bis>` (Paket `<id>`) auf Fehler im Verhalten. Unten steht der
> Paketblock mit den Gegenstellen der geänderten Aufrufe, `except`-Klauseln und (Delphi)
> Freigaben, mechanisch gesammelt.
>
> 1. **Prüfe den Vertrag der Gegenstelle.** Nimm jeden Eintrag unter „Gegenstellen“ und
>    vergleiche, was die geänderte Stelle annimmt, mit dem, was die Gegenstelle zusagt:
>    Signatur und Default-Werte, `wirft:` gegen die gefangenen Typen, bei `Weg:` die
>    Bedingung, die den neuen Wert prüft, bei Besitz wer freigibt. Öffne die genannte
>    Stelle (`<datei>:<zeile>`), bevor du einen Fund daraus machst.
> 2. Prüfe danach die geänderten Zeilen selbst: Logik, Randwerte, Fehlerpfade, Folgen für
>    Aufrufer außerhalb des Pakets.
> 3. Stellen, die der Block „nicht aufgelöst“ nennt, und Dateien ohne Block („Gegenstellen
>    nicht gesammelt“) prüfst du im normalen Review. Ein leerer Abschnitt heißt nicht, dass es
>    keine Verträge gibt.
> 4. Melde nur, was du mit einem konkreten Ablauf belegen kannst: Eingabe, Weg, falsches
>    Ergebnis. Keine Vermutung ohne Ablauf.
> 5. Antworte nur mit der JSON-Liste aus dem [Rückgabeformat](#rückgabeformat), bei keinem
>    Fund mit `[]`.
>
> Paketblock:
>
> `<Inhalt von packets/<id>.md, unverändert>`

Der Fund an einer Gegenstelle hat als `file` die Datei der Gegenstelle, nicht die des
Aufrufers. Der Aufrufer steht dann in `summary`.

## Fassung 2: Fokus `quality`

Je Paket `/code-review` mit einem anderen Auftrag. Der Block sagt „Gegenstellen nicht
gesammelt (Fokus quality).“ Das ist richtig so; es gibt nichts zu vergleichen. `/simplify` ist
hier nicht der Weg, weil es Änderungen schreibt, und deep-review behebt nichts.

> Prüfe die Änderung `<von>..<bis>` (Paket `<id>`) ausschließlich auf Wartbarkeit, Doppelung
> und Vereinfachung. Fehler im Verhalten und Sicherheit melde nicht, auch wenn du welche siehst.
>
> Melde einen Fund nur mit Grundlage, und nenne sie in `summary` nach „Grundlage:“. Gültig
> sind drei:
>
> - **Projektregel:** die Regel mit Fundstelle (Datei und Abschnitt), gegen die die Änderung
>   verstößt.
> - **Messwert:** eine Zahl, die man nachzählen kann, etwa Länge der Funktion, Tiefe der
>   Verschachtelung oder Zahl der Kopien derselben Logik mit ihren Fundstellen.
> - **Konkreter Lesefehler:** die Stelle, die man beim Lesen falsch versteht, und wie
>   (irreführender Name, Reihenfolge, die etwas anderes nahelegt, als geschieht).
>
> Geschmack, Stil ohne Regel und „könnte schöner sein“ ohne eine dieser Grundlagen melde nicht.
> `failure_scenario` nennt, was bei der nächsten Änderung an der Stelle schiefgeht, oder `null`.
> Antworte nur mit der JSON-Liste aus dem [Rückgabeformat](#rückgabeformat), bei keinem Fund mit
> `[]`.
>
> Paketblock:
>
> `<Inhalt von packets/<id>.md, unverändert>`

## Review ohne /code-review

Ohne `/code-review` läuft dieselbe Paketfolge im Hauptkontext. Die Pakete, die Gegenstellen
und das `record` sind dieselben; nur der Reviewer bist du selbst. Der Bericht sagt in der
Kopfzeile beim Werkzeug und in der Übergabe wörtlich **„Review ohne /code-review“**, damit der
Leser weiß, dass hier kein eigener Unteragent und kein zweiter Blick gelesen hat.

Je Paket, in Plan-Reihenfolge, eines nach dem anderen:

1. Lies `packets/<id>.md` ganz.
2. Lies die Änderung mit `git diff <von>..<bis>` (nur die Paketdateien). Das Soll steht in
   `git log <von>..<bis>`, im Profil `checkpoint` in der Datei von `--soll-file`.
3. Der Reviewer liest den Arbeitsbaum, nicht ZIEL. Nennt der Plan unter `notes`
   `worktree_differs` oder `target_not_head`, lies den Stand mit `git show <ziel>:<datei>`.
4. Gehe die Einträge unter „Gegenstellen“ der Reihe nach durch und prüfe den Vertrag wie in
   Fassung 1, Punkt 1. Öffne die genannte Stelle, bevor du einen Fund schreibst.
5. Gehe danach die geänderten Zeilen durch: Logik, Randwerte, Fehlerpfade, Aufrufer außerhalb
   des Pakets. Bei Delphi-Dateien nimmst du [delphi.md](delphi.md) als Prüfliste.
6. Schreibe die Liste im [Rückgabeformat](#rückgabeformat), rufe `record` auf und beginne
   erst dann das nächste Paket.

Regeln:

- Kein Paket überspringen und keine zwei Pakete in einer Liste mischen; `record` nimmt je
  Paket genau ein Ergebnis an.
- Ein Fund braucht einen Ablauf (Eingabe, Weg, falsches Ergebnis) in `failure_scenario`. Kannst
  du keinen angeben, ist es kein Fund, sondern eine Frage für den Nutzer, und gehört in die
  Übergabe, nicht in die Liste.
- Fokus `quality`: der Auftrag aus Fassung 2 gilt unverändert, ebenfalls ohne Vergleich der
  Gegenstellen.
- Fokus `security` ohne `/security-review`: ein Paket `s1`, derselbe Ablauf, Prüfblick auf
  Eingaben von außen, Rechte, Geheimnisse und Injektion. Der Bericht nennt den Ausfall des
  Werkzeugs ebenso.
- `--tool` ist dann `"Review ohne /code-review"`.

## Rückgabeformat

Die Antwort ist eine JSON-Liste. Je Fund ein Objekt mit genau diesen Feldern, dieselben, die
`review_kit.py record` annimmt:

| Feld | Inhalt |
| --- | --- |
| `file` | Pfad im Repo, Pflicht. `/` als Trenner; ein absoluter Pfad im Repo wird relativ gemacht, `..` und Pfade außerhalb werden abgewiesen |
| `line` | eine Zahl, ein Bereich `"a-b"` oder `null`, wenn keine einzelne Zeile gemeint ist |
| `summary` | Text, Pflicht: was falsch ist, in einem Satz |
| `failure_scenario` | Text mit dem Ablauf, der scheitert, oder `null` |

```json
[
  {"file": "billing/invoice.py", "line": 57,
   "summary": "total wird jetzt mit mode=\"floor\" gerundet; round_cents schneidet dann ab statt zu runden",
   "failure_scenario": "Eine Position von 19,999 ergibt 19,99 statt 20,00, die Summe der Positionen weicht vom Rechnungsbetrag ab."},
  {"file": "billing/rounding.py", "line": "28-31",
   "summary": "Der Zweig für mode == \"floor\" liefert int statt Decimal (Gegenstelle zu invoice.py:57)",
   "failure_scenario": null}
]
```

- Ein Paket ohne Funde liefert `[]`. Weglassen des Ergebnisses ist kein Ergebnis; `audit`
  meldet das Paket dann unter `missing`.
- Weitere Felder fallen weg. Fehlt `summary` oder `file`, ist die ganze Liste ungültig; es
  wird nichts geschrieben.
- Ein Objekt mit der Liste unter `findings` geht auch, die reine Liste ist der Normalfall.

Übergabe an das Skript, ohne Skriptpfad hier (der steht in der SKILL.md):

```
review_kit.py record --run <lauf> --packet <id> --tool <werkzeug> <datei|->
```

- `<werkzeug>` ist das, was lief: `/code-review`, `/security-review` oder
  `"Review ohne /code-review"`. Der Bericht übernimmt es.
- `-` liest die Liste von stdin als UTF-8.
- Angenommen wird nur, wenn das Paket im Plan steht und noch kein Ergebnis hat. Ein zweites
  Ergebnis wird abgewiesen; eine falsche Liste ebenso, und dann bleibt `results/` unberührt.
  Korrigiere die Liste und rufe `record` erneut auf.
