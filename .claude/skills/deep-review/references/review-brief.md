# Review-Auftrag je Paket

Referenz für den Hauptagenten (Ablauf Schritt 4). Hier steht, was du einem Reviewer je Paket
sagst und in welcher Form das Ergebnis zurückkommt, in drei Fassungen:

| Fassung | wann |
| --- | --- |
| [Fokus `bugs` mit `/code-review`](#fassung-1-code-review-fokus-bugs) | Normalfall, auch Profil `checkpoint` |
| [Fokus `quality`](#fassung-2-fokus-quality) | „Wartbarkeit“, „Qualität“, „Code-Hygiene“ |
| [Review ohne /code-review](#review-ohne-code-review) | `/code-review` ist nicht verfügbar (claude.ai, andere Agenten) |

Fokus `security` hat ein Paket `s1`. Ob `/security-review` es prüfen kann, hängt am Bereich
des Plans; die zwei Fälle stehen unter [Fokus `security`](#fokus-security). Es gilt dasselbe
[Rückgabeformat](#rückgabeformat).

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

- `<von>..<bis>` ist immer das `range` des Pakets, so wie `counterparts` es je Paket ausgibt
  (`<id>: <bereich> · …`). Den Originalbereich setzt du nicht selbst ein: Er ist es nur bei
  `split: false` ohne Wurzel-Commit. Beim Wurzel-Commit (`root: true`) und nach `--since` mit
  Übernahme (eine Datei in `file_keys` hat `reused_from`) bekommt auch ein einzelnes Paket
  Hilfscommits, und dann ist es deren `<von>..<bis>`. Ein `--since`, das nichts übernommen
  hat, lässt den Plan, wie er war.
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

## Fokus `security`

`/security-review` wählt seinen Bereich selbst: die Änderungen von HEAD gegen die
Merge-Basis mit `origin/HEAD`, dem Default-Branch des Remotes. Einen Bereich nimmt es nicht
an. Darum prüfst du zuerst, ob sich dieser Umfang mit dem Bereich des Plans deckt. Er deckt
sich nur, wenn alle vier Bedingungen gelten:

- ZIEL ist HEAD: `target` aus `plan.json` gleich `git rev-parse HEAD`, unter `notes` kein
  `target_not_head`.
- BASIS ist die Basis von `/security-review`: `git rev-parse --verify --quiet origin/HEAD`
  findet `origin/HEAD`, und `base` aus `plan.json` ist gleich `git merge-base HEAD
  origin/HEAD`. Ein Upstream des Branches zählt nicht: Gegen `origin/<branch>` vergleicht
  `/security-review` nicht.
- Unter `notes` steht kein `worktree_differs` und kein `worktree_unknown`. Sonst sieht
  `/security-review` andere Dateistände als der Plan.
- Keine Datei ist übernommen: In `file_keys` hat keine Datei `reused_from`. Nach `--since`
  mit Übernahme deckt `s1` nur die übrigen Dateien ab, `/security-review` prüft aber alles.

Fehlt `origin/HEAD`, oder gilt eine der Bedingungen nicht, deckt sich der Umfang nicht. Dann
prüfst du im Hauptkontext, und zwar über den Bereich `<von>..<bis>`, den `counterparts` für
`s1` ausgegeben hat (`s1: <bereich> · …`), nicht über `range` aus `plan.json`. Beim
Wurzel-Commit ist `range` nur `<ziel>`; `git diff <ziel>` vergliche dann mit dem Arbeitsbaum.
Der Bereich von `counterparts` sind die Hilfscommits.

| Fall | Beispiel | Review | `--tool` |
| --- | --- | --- | --- |
| Umfang deckt sich | Plan `main..HEAD`, `origin/HEAD` zeigt auf `main`, `base` gleich `git merge-base HEAD origin/HEAD`, keine Hinweise zum Arbeitsbaum, keine übernommene Datei | `/security-review` einmal für `s1`, die Gegenstellen aller Dateien als Kontext | `security-review` |
| Umfang deckt sich nicht | gepushter Feature-Branch mit Plan `origin/feature..HEAD` (die Basis ist nicht die Merge-Basis mit `origin/HEAD`); kein `origin/HEAD`; Wurzel-Commit; Bereich `v1.2..v1.3`; ZIEL nicht HEAD; `worktree_differs` oder `worktree_unknown`; Folgelauf mit `--since`, der Dateien übernommen hat | im Hauptkontext über den Bereich von `s1`, den `counterparts` ausgegeben hat, Ablauf wie [Review ohne /code-review](#review-ohne-code-review), Prüfblick auf Eingaben von außen, Rechte, Geheimnisse und Injektion | `"Review ohne /security-review"` |

Im zweiten Fall nennt der Bericht das Werkzeug wörtlich „Review ohne /security-review“ in der
Kopfzeile und in der Übergabe, wie beim Review ohne /code-review.

## Review ohne /code-review

Ohne `/code-review` läuft dieselbe Paketfolge im Hauptkontext. Die Pakete, die Gegenstellen
und das `record` sind dieselben; nur der Reviewer bist du selbst. Der Bericht sagt in der
Kopfzeile beim Werkzeug und in der Übergabe wörtlich **„Review ohne /code-review“**, damit der
Leser weiß, dass hier kein eigener Unteragent und kein zweiter Blick gelesen hat.

Je Paket, in Plan-Reihenfolge, eines nach dem anderen:

1. Lies `packets/<id>.md` ganz.
2. Lies die Änderung mit `git diff <von>..<bis>` (nur die Paketdateien). `<von>..<bis>` ist
   immer der Bereich, den `counterparts` für das Paket ausgegeben hat, auch bei `split: false`:
   Beim Wurzel-Commit und nach `--since` mit Übernahme sind es Hilfscommits, nicht der
   Originalbereich. Das
   Soll steht in `git log <von>..<bis>`, im Profil `checkpoint` in der Datei von `--soll-file`.
3. Ein Review liest sonst den Arbeitsbaum, nicht ZIEL. Nennt der Plan unter `notes`
   `target_not_head`, `worktree_differs` oder `worktree_unknown` (Index fehlt, Arbeitsbaum
   nicht geprüft), lies jede Paketdatei mit `git show <ziel>:<datei>`, nicht aus dem
   Arbeitsbaum.
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
- Fokus `security`, wenn sich der Umfang von `/security-review` nicht mit dem Bereich des
  Plans deckt, `origin/HEAD` fehlt oder `/security-review` fehlt ([Fokus
  `security`](#fokus-security)): ein Paket `s1`, derselbe Ablauf über den Bereich, den
  `counterparts` für `s1` ausgegeben hat, Prüfblick auf Eingaben von außen, Rechte,
  Geheimnisse und Injektion. `--tool` ist dann `"Review ohne /security-review"`.
- Sonst ist `--tool` `"Review ohne /code-review"`.

## Rückgabeformat

Die Antwort ist eine JSON-Liste. Je Fund ein Objekt mit genau diesen Feldern, dieselben, die
`review_kit.py record` annimmt:

| Feld | Inhalt |
| --- | --- |
| `file` | Pfad im Repo als Text, Pflicht |
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
- Ein Objekt mit der Liste unter `findings` geht auch, die reine Liste ist der Normalfall.
- Weitere Felder fallen weg.

`record` prüft jeden Fund so, und **ein** ungültiger Fund macht die ganze Liste ungültig; es
wird nichts geschrieben:

| Prüfung | angenommen | abgewiesen |
| --- | --- | --- |
| Antwort | JSON-Liste, oder Objekt mit Liste unter `findings`; über stdin und aus einer Datei UTF-8, mit oder ohne BOM am Anfang | kein JSON, anderes JSON, stdin kein UTF-8, Datei kein UTF-8 |
| Fund | ein Objekt | alles andere, etwa ein Text oder eine Liste |
| `file` | nicht leerer Text; `\` wird `/`, `./` fällt weg, ein absoluter Pfad im Repo wird relativ | fehlt, leer oder kein Text; ein Glied `..`; ein absoluter Pfad außerhalb des Repos |
| `line` | ganze Zahl ≥ 0; Text `12`, `L12`, `12-14`, `12 - 14`, `12–14`, `L12-L14`, `12 bis 14` (vertauschte Enden werden sortiert, `12-12` wird 12); `null`, fehlt oder leerer Text wird `null` | negative Zahl, Kommazahl, `true`/`false`, Objekt, Liste; Text ohne diese Form, etwa `"near 40"`, `"ca. 12"` oder `"12, 15"` |
| `summary` | nicht leerer Text | fehlt, leer oder kein Text |
| `failure_scenario` | Text (leer wird `null`), `null` oder fehlt | Zahl, Objekt, Liste, `true`/`false` |

Steht keine einzelne Zeile fest, ist `line` `null`, nicht eine Umschreibung wie `"near 40"`. Der
Ablauf in `failure_scenario` ist ein Satz als Text, kein Objekt mit Feldern.

Übergabe an das Skript, ohne Skriptpfad hier (der steht in der SKILL.md):

```
review_kit.py record --run <lauf> --packet <id> --tool <werkzeug> <datei|->
```

- `<werkzeug>` ist das, was lief: `code-review`; `security-review` nur, wenn ZIEL HEAD
  ist, `base` gleich `git merge-base HEAD origin/HEAD`, unter `notes` kein
  `worktree_differs` und kein `worktree_unknown` steht und keine Datei in `file_keys`
  `reused_from` hat; `"Review ohne /security-review"` für ein Sicherheitsreview im
  Hauptkontext über den Bereich von `s1` aus `counterparts` in jedem anderen Fall, auch ohne
  `origin/HEAD` und nach `--since` mit Übernahme ([Fokus `security`](#fokus-security)); sonst
  `"Review ohne /code-review"`.
- Die Namen der beiden Werkzeuge stehen ohne Schrägstrich am Anfang: Git Bash unter Windows
  schreibt ein Argument wie `/code-review` in einen Windows-Pfad um
  (`C:/Program Files/Git/code-review`), und die Kopfzeile des Berichts passte dann nie.
  `record` speichert `code-review` als `/code-review` und `security-review` als
  `/security-review`; auch ein so umgeschriebener Pfad wird zurückgelegt. „Review ohne
  /code-review" beginnt nicht mit `/` und bleibt, wie es ist. Der Bericht übernimmt das
  gespeicherte Werkzeug aus `results/<id>.json` (`_meta.tool`), also `/code-review`.
- `-` liest die Liste von stdin als UTF-8, eine Datei ebenso; ein BOM am Anfang zählt in
  beiden Fällen nicht.
- Angenommen wird nur, wenn das Paket im Plan steht und noch kein Ergebnis hat. Ein zweites
  Ergebnis wird abgewiesen; eine falsche Liste ebenso, und dann bleibt `results/` unberührt.
  Korrigiere die Liste und rufe `record` erneut auf.
