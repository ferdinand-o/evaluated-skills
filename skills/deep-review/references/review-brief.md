# Review-Auftrag je Paket

Referenz für den Hauptagenten (Ablauf Schritt 4). Hier steht, was du einem Reviewer je Paket
sagst und in welcher Form das Ergebnis zurückkommt, in drei Fassungen, dazu der Auftrag an den
Unteragenten je Paket und an den Prüfer von `verify`:

| Fassung | wann |
| --- | --- |
| [Fokus `bugs` mit `/code-review`](#fassung-1-code-review-fokus-bugs) | Normalfall, auch Profil `checkpoint` |
| [Fokus `quality`](#fassung-2-fokus-quality) | „Wartbarkeit“, „Qualität“, „Code-Hygiene“ |
| [Auftrag an den Unteragenten je Paket](#auftrag-an-den-unteragenten-je-paket) | Fassung 1 und 2: was die Hauptschleife je Paket einem Unteragenten schickt (Standard) |
| [Review ohne /code-review](#review-ohne-code-review) | `/code-review` ist nicht verfügbar (claude.ai, andere Agenten) |
| [Prüfer-Auftrag für `verify`](#prüfer-auftrag-für-verify) | ein Fund soll unabhängig geprüft werden (Profil `checkpoint` oder `--verify`) |

Fokus `security` hat ein Paket `s1`. Ob `/security-review` es prüfen kann, hängt am Bereich
des Plans; die zwei Fälle stehen unter [Fokus `security`](#fokus-security). Es gilt dasselbe
[Rückgabeformat](#rückgabeformat).

Wie `packets/<id>.md` aufgebaut ist und wie ein Reviewer es liest, steht in
[counterparts.md](counterparts.md): [Zeilenformat des Paketblocks](counterparts.md#zeilenformat-des-paketblocks)
und [Lesehilfe für den Reviewer](counterparts.md#lesehilfe-für-den-reviewer). Was im Auftrag
unter „Bereich“ steht, erklärt [packets.md](packets.md#paket-bereich-was-der-reviewer-sieht).
Beides wird hier nicht wiederholt.

## Fassung 1: `/code-review`, Fokus `bugs`

Je Paket in Plan-Reihenfolge ein Aufruf, mit der Stufe des Plans (`level`, die Zeile `Reviews:`
von `plan` nennt sie; Standard `medium`, im Profil `checkpoint` `high`):

```
/code-review <stufe> --max-findings all <von>..<bis>
```

Der Auftrag ist die Datei `packets/<id>.prompt.md` des Laufs. Ihren Pfad nennt `counterparts`
je Paket, relativ zum Repo (`.skills/cache/deep-review/<lauf>/packets/<id>.prompt.md`); er
steht nicht im Aufruf, sondern absolut im Auftragstext an den Reviewer. Aufruf, Auftragstext
und `record` schickt die Hauptschleife je Paket einem Unteragenten, wörtlich nach der Vorlage
unter [Auftrag an den Unteragenten je Paket](#auftrag-an-den-unteragenten-je-paket).

- `<von>..<bis>` ist immer das `range` des Pakets, so wie `counterparts` es je Paket ausgibt
  (`<id>: <bereich> · …`). Den Originalbereich setzt du nicht selbst ein: Er ist es nur bei
  `split: false` ohne Wurzel-Commit und außerhalb des Pfad-Modus. Im Pfad-Modus (`mode: path`),
  beim Wurzel-Commit (`root: true`) und nach `--since` mit
  Übernahme (eine Datei in `file_keys` hat `reused_from`) bekommt auch ein einzelnes Paket
  Hilfscommits, und dann ist es deren `<von>..<bis>`. Ein `--since`, das nichts übernommen
  hat, lässt den Plan, wie er war.
- Die Datei `packets/<id>.prompt.md` (Auftrag, Block, Rückgabeformat und Marke) gibst du
  **jedem Unteragenten unverändert** mit, als Pfad oder als ganzen Text: nicht gekürzt, nicht
  umformuliert, nicht nach Verdacht ausgewählt. Auch der Satz zu den nicht aufgelösten Stellen
  und eine Kappung bleiben stehen. Im Pfad-Modus (`mode: path`) steht dort unter dem
  Bereich `<von>..<bis>` zusätzlich der Pfad mit dem Ziel; die Dateien stehen als neu, der
  Aufruf bleibt `/code-review <stufe> --max-findings all <von>..<bis>`.
- Hat das Paket eine Spanne, nennt die Datei sie (`datei:von-bis`): Nur diese Zeilen sind
  geändert, der Rest der Datei steht auf dem Stand des Ziels.
- Bei Delphi-Dateien im Paket steht [delphi.md](delphi.md) schon darin.
- Im Profil `checkpoint` steht das Soll aus `--soll-file` schon darin, als eigener Abschnitt
  „Soll“ unter dem Auftrag.

Auftrag an den Reviewer (Platzhalter in `<…>` ersetzt du):

> Prüfe die Änderung `<von>..<bis>` (Paket `<id>`) auf Fehler im Verhalten. Der Paketblock
> mit den Gegenstellen der geänderten Aufrufe, `except`-Klauseln und (Delphi) Freigaben,
> mechanisch gesammelt, steht unten in dieser Datei.
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
> 5. Antworte nur mit dem JSON-Objekt aus dem [Rückgabeformat](#rückgabeformat) (`marke`,
>    `stufe`, `findings`), bei keinem Fund mit `"findings": []`.
>
> Paketblock:
>
> `<der Block, von counterparts unten eingesetzt>`

Der Fund an einer Gegenstelle hat als `file` die Datei der Gegenstelle, nicht die des
Aufrufers. Der Aufrufer steht dann in `summary`. Eine Gegenstelle mit „(Name eindeutig, ohne
Sammler)“ ist nur nach Namen gefunden; der Reviewer prüft am Aufruf, ob sie gemeint ist
([counterparts.md](counterparts.md#namens-rückfall)).

## Auftrag an den Unteragenten je Paket

Standard für Fassung 1 und 2: je Paket, in Plan-Reihenfolge, ein Unteragent. Die Hauptschleife
füllt diese Vorlage aus und schickt sie als ganzen Auftrag; sie liest danach weder Block noch
Fundliste, nur die Zeile, die der Unteragent zurückgibt (Spec 28, Ergebnis der Sonde B).

| Platzhalter | setzt die Hauptschleife ein |
| --- | --- |
| `<repo>` | absoluter Pfad der Repo-Wurzel, für die `plan` lief (`git -C <ordner von --repo> rev-parse --show-toplevel`); `counterparts` nennt Pfade relativ dazu |
| `<skript>` | absoluter Pfad von `review_kit.py`, so wie er in den Aufrufen der SKILL.md aufgelöst steht; `${CLAUDE_SKILL_DIR}` ist im Unteragenten nicht gesetzt, darum nie die Variable einsetzen |
| `<lauf>` | die Lauf-ID aus der ersten Ausgabezeile von `plan` |
| `<id>`, `<von>..<bis>`, `<auftrag>` | aus der Zeile `<id>: <von>..<bis> · <auftrag> · …` von `counterparts` |
| `<stufe>` | die Stufe des Plans (Zeile `Reviews:`) |

```text
Arbeite im Repository <repo>: führe zuerst `cd "<repo>"` aus, alle Befehle laufen dort.
Lauf <lauf>, Paket <id>.

1. Starte `/code-review <stufe> --max-findings all <von>..<bis>` mit diesem Auftragstext:
   „Lies zuerst die Datei `<repo>/<auftrag>` vollständig bis zur letzten Zeile und folge ihr;
   gib den Auftrag an jeden Unteragenten weiter. Das Endergebnis ist das JSON-Objekt aus dem
   Abschnitt Rückgabeformat dieser Datei (marke aus der letzten Zeile, stufe = die wirklich
   gelaufene), nicht eine Liste."
2. Gib das Objekt, das /code-review liefert ({"marke", "stufe", "findings"}, ohne Funde
   "findings": []), unverändert auf stdin an record:
   python "<skript>" record --repo "<repo>" --run <lauf> --packet <id> --tool code-review - <<'EOF'
   <das JSON-Objekt>
   EOF
3. Weist record ab, korrigiere das Objekt nach der Meldung, ohne einen Fund wegzulassen, und
   rufe record erneut auf, bis es angenommen ist.
4. Antworte nur mit der Ausgabezeile von record („<id>: <n> Fund(e) angenommen → …“), ohne
   Objekt und ohne Fundliste.
```

- `<repo>/<auftrag>` ist der absolute Pfad der Datei; der kurze Pfad `packets/<id>.prompt.md`
  allein findet sie nicht, und ein relativer scheitert, wenn der Unteragent woanders startet
  (etwa bei `--repo ../projekt`).
- Fokus `quality` (Fassung 2): dieselbe Vorlage; den Auftrag dafür hat `counterparts` schon
  in die Datei geschrieben.
- Fokus `security` mit `/security-review` (nur wenn der Umfang sich deckt, [Fokus
  `security`](#fokus-security)): `/security-review` statt des Aufrufs, im Auftragstext ohne
  „stufe = …“, und `--tool security-review`.
- Ohne Agent-Werkzeug (deep-review läuft selbst als Unteragent, oder der Kontext hat keines)
  startet die Hauptschleife `/code-review` je Paket selbst mit demselben Auftragstext (Schritt
  1, ab „Lies zuerst“) und ruft `record` wie in Schritt 2 und 3 selbst auf. Fehlt
  `/code-review`, gilt [Review ohne /code-review](#review-ohne-code-review).

## Fassung 2: Fokus `quality`

Je Paket `/code-review` mit einem anderen Auftrag. Der Block sagt „Gegenstellen nicht
gesammelt (Fokus quality).“ Das ist richtig so; es gibt nichts zu vergleichen. `/simplify` ist
hier nicht der Weg, weil es Änderungen schreibt, und deep-review behebt nichts.

> Prüfe die Änderung `<von>..<bis>` (Paket `<id>`) ausschließlich auf Wartbarkeit, Doppelung
> und Vereinfachung. Fehler im Verhalten und Sicherheit melde nicht, auch wenn du welche siehst.
> Der Paketblock steht unten in dieser Datei.
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
> Antworte nur mit dem JSON-Objekt aus dem [Rückgabeformat](#rückgabeformat) (`marke`, `stufe`,
> `findings`), bei keinem Fund mit `"findings": []`.
>
> Paketblock:
>
> `<der Block, von counterparts unten eingesetzt>`

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

### Auftrag an den Reviewer

Was oben steht, entscheidest du als Hauptagent. Der Reviewer bekommt in beiden Fällen nur
diesen Auftrag; `counterparts` schreibt ihn in `packets/s1.prompt.md`.

> Prüfe die Änderung `<von>..<bis>` (Paket `<id>`) ausschließlich auf Sicherheit. Der
> Paketblock mit den Gegenstellen der geänderten Aufrufe steht als Kontext unten in dieser
> Datei.
>
> 1. **Eingaben von außen.** Wo kommen Daten aus Anfrage, Datei, Umgebung, Kommandozeile oder
>    Netz in die geänderten Zeilen, und werden sie geprüft, bevor sie wirken?
> 2. **Rechte.** Prüft die geänderte Stelle, wer sie aufrufen oder was er lesen und schreiben
>    darf, und lässt sich die Prüfung umgehen (fehlt, kommt zu spät, Pfad außerhalb des
>    erlaubten Bereichs)?
> 3. **Geheimnisse.** Landen Schlüssel, Passwörter oder Tokens im Code, in Logs, in
>    Fehlermeldungen oder in Ausgaben?
> 4. **Injection.** Gelangt eine Eingabe von außen ungeprüft in SQL, Shell, Pfade, Templates,
>    `eval` oder eine Deserialisierung?
> 5. Melde nur, was du mit einem konkreten Ablauf belegen kannst: Eingabe, Weg, Schaden.
>    Fehler im Verhalten ohne Folge für die Sicherheit und Wartbarkeit melde nicht.
> 6. **Rückgabe.** Antworte nur mit dem JSON-Objekt aus dem [Rückgabeformat](#rückgabeformat)
>    (`marke`, `findings`), bei keinem Fund mit `"findings": []`.
>
> Paketblock:
>
> `<der Block, von counterparts unten eingesetzt>`

## Review ohne /code-review

Ohne `/code-review` läuft dieselbe Paketfolge im Hauptkontext. Die Pakete, die Gegenstellen
und das `record` sind dieselben; nur der Reviewer bist du selbst. Der Bericht sagt in der
Kopfzeile beim Werkzeug und in der Übergabe wörtlich **„Review ohne /code-review“**, damit der
Leser weiß, dass hier kein eigener Unteragent und kein zweiter Blick gelesen hat.

Je Paket, in Plan-Reihenfolge, eines nach dem anderen:

1. Lies die Datei, die `counterparts` für das Paket nennt
   (`.skills/cache/deep-review/<lauf>/packets/<id>.prompt.md`), ganz (Auftrag, Block und Marke).
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
6. Schreibe das Objekt im [Rückgabeformat](#rückgabeformat), rufe `record` auf und beginne
   erst dann das nächste Paket.

Regeln:

- Kein Paket überspringen und keine zwei Pakete in einem Ergebnis mischen; `record` nimmt je
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

Die Antwort ist ein JSON-Objekt `{"marke", "stufe", "findings"}`:

- `marke`: die Marke aus der letzten Zeile von `packets/<id>.prompt.md` (`Paket-Marke: …`),
  genau so; nur dort steht sie, die Zeile nach der Kopfzeile verweist bloß auf das Ende.
- `stufe`: nur nach `/code-review` die Stufe, mit der es wirklich lief (`low`, `medium`,
  `high`, `xhigh` oder `max`). Die Stufe in `packets/<id>.prompt.md` ist die Vorgabe für den
  Aufruf `/code-review <stufe>`, kein Wert zum Abschreiben: Lief es niedriger, steht hier die
  niedrigere, und `audit` nennt das Paket unter `below_level`. Nach `/security-review` und
  bei einem Review im Hauptkontext gibt es keine Stufe; das Feld fehlt dann (der Auftrag von
  `s1` verlangt keines), und es gilt die Stufe des Plans. Steht es doch da, speichert `record`
  es bei diesen Werkzeugen nicht und sagt das.
- `findings`: die Liste der Funde, leer bei keinem Fund.

Je Fund ein Objekt mit genau diesen Feldern, dieselben, die `review_kit.py record` annimmt:

| Feld | Inhalt |
| --- | --- |
| `file` | Pfad im Repo als Text, Pflicht |
| `line` | eine Zahl, ein Bereich `"a-b"` oder `null`, wenn keine einzelne Zeile gemeint ist |
| `summary` | Text, Pflicht: was falsch ist, in einem Satz |
| `failure_scenario` | Text mit dem Ablauf, der scheitert, oder `null` |
| `evidence` | optional: der Befehl und seine Ausgabe oder zitierte Zeilen mit `Datei:Zeile`; ein Fund mit `evidence` gilt als belegt und bekommt von `verify` keinen Prüfauftrag |

```json
{"marke": "dr-p1-3f9a2c", "stufe": "<stufe>", "findings": [
  {"file": "billing/invoice.py", "line": 57,
   "summary": "total wird jetzt mit mode=\"floor\" gerundet; round_cents schneidet dann ab statt zu runden",
   "failure_scenario": "Eine Position von 19,999 ergibt 19,99 statt 20,00, die Summe der Positionen weicht vom Rechnungsbetrag ab."},
  {"file": "billing/rounding.py", "line": "28-31",
   "summary": "Der Zweig für mode == \"floor\" liefert int statt Decimal (Gegenstelle zu invoice.py:57)",
   "failure_scenario": null}
]}
```

- Ein Paket ohne Funde liefert das Objekt mit `"findings": []`. Weglassen des Ergebnisses ist
  kein Ergebnis; `audit` meldet das Paket dann unter `missing`.
- Eine bloße Liste der Funde nimmt `record` nur mit `--no-block` an, also ohne
  Gegenstellen-Block; `audit` nennt das Paket dann unter `no_block`. `--no-block` vermerkt
  das immer (`no_block: true`), auch bei einem Objekt mit passender Marke; eine genannte `stufe`
  wird auch dann geprüft und gespeichert, außer bei den Werkzeugen ohne Stufe. Nimm es nur, wenn
  der Reviewer die Datei nicht bekam; `no_block` macht den Lauf nicht unvollständig, der
  Bericht nennt das Paket.
- Die Marke ist eine Auskunft, kein Beleg: Sie zeigt nur, dass der Schreiber des Ergebnisses
  die Datei bis zur letzten Zeile kennt. Dass der Unteragent den Auftrag sah, belegt nur sein
  Transkript.
- Weitere Felder fallen weg.

`record` prüft jeden Fund so, und **ein** ungültiger Fund macht die ganze Liste ungültig; es
wird nichts geschrieben:

| Prüfung | angenommen | abgewiesen |
| --- | --- | --- |
| Antwort | Objekt mit der Marke des Pakets unter `marke`, der Liste unter `findings` und einer Stufe unter `stufe` — außer bei `security-review`, „Review ohne /security-review" und „Review ohne /code-review": dort keine, eine genannte wird ignoriert; mit `--no-block` auch eine bloße Liste oder ein Objekt ohne passende Marke; über stdin und aus einer Datei UTF-8, mit oder ohne BOM am Anfang | kein JSON, anderes JSON, ohne `--no-block` eine bloße Liste, keine oder eine fremde Marke, ohne `--no-block` keine Stufe bei einem anderen Werkzeug als diesen dreien, eine unbekannte Stufe; stdin kein UTF-8, Datei kein UTF-8 |
| Fund | ein Objekt | alles andere, etwa ein Text oder eine Liste |
| `file` | nicht leerer Text; `\` wird `/`, `./` fällt weg, ein absoluter Pfad im Repo wird relativ | fehlt, leer oder kein Text; ein Glied `..`; ein absoluter Pfad außerhalb des Repos |
| `line` | ganze Zahl ≥ 0; Text `12`, `L12`, `12-14`, `12 - 14`, `12–14`, `L12-L14`, `12 bis 14` (vertauschte Enden werden sortiert, `12-12` wird 12); `null`, fehlt oder leerer Text wird `null` | negative Zahl, Kommazahl, `true`/`false`, Objekt, Liste; Text ohne diese Form, etwa `"near 40"`, `"ca. 12"` oder `"12, 15"` |
| `summary` | nicht leerer Text | fehlt, leer oder kein Text |
| `failure_scenario` | Text (leer wird `null`), `null` oder fehlt | Zahl, Objekt, Liste, `true`/`false` |

Steht keine einzelne Zeile fest, ist `line` `null`, nicht eine Umschreibung wie `"near 40"`. Der
Ablauf in `failure_scenario` ist ein Satz als Text, kein Objekt mit Feldern.

Übergabe an das Skript, ohne Skriptpfad hier (der steht in der SKILL.md):

```
review_kit.py record --run <lauf> --packet <id> --tool <werkzeug> [--no-block] <datei|->
```

- `<werkzeug>` ist das, was lief: `code-review`; `security-review` nur, wenn ZIEL HEAD
  ist, `base` gleich `git merge-base HEAD origin/HEAD`, unter `notes` kein
  `worktree_differs` und kein `worktree_unknown` steht und keine Datei in `file_keys`
  `reused_from` hat; `"Review ohne /security-review"` für ein Sicherheitsreview im
  Hauptkontext über den Bereich von `s1` aus `counterparts` in jedem anderen Fall, auch ohne
  `origin/HEAD` und nach `--since` mit Übernahme ([Fokus `security`](#fokus-security)); sonst
  `"Review ohne /code-review"`.
- Die Namen der beiden Werkzeuge stehen ohne Schrägstrich am Anfang (Git Bash unter Windows
  schreibt sonst einen Pfad daraus); `record` setzt ihn wieder ein, auch bei `code-review high`.
  Einzelheiten und die Namen „Review ohne …“: [packets.md](packets.md#werkzeugname-und-git-bash).
- `-` liest das Ergebnis von stdin als UTF-8, eine Datei ebenso; ein BOM am Anfang zählt in
  beiden Fällen nicht.
- Angenommen wird nur, wenn das Paket im Plan steht und noch kein Ergebnis hat. Ein zweites
  Ergebnis wird abgewiesen; ein falsches ebenso, und dann bleibt `results/` unberührt.
  Korrigiere es und rufe `record` erneut auf.

## Prüfer-Auftrag für `verify`

`verify --run <lauf>` schreibt je Fund ohne `evidence` und ohne Urteil `verify/<n>.md`. Je Auftrag
startest du einen Unteragenten (Modell Sonnet) und gibst ihm die Datei unverändert mit; er
bekommt weder den Paketblock noch das Ergebnis des Reviewers. Der Auftrag enthält nur:

- Datei, Zeile und das Szenario des Reviewers (`failure_scenario`) sowie den Commit, dessen Stand
  er liest (`git show <commit>:<datei>`), nicht die `summary`; so schreibt er die Behauptung nicht
  ab, sondern prüft sie mit einem eigenen Ablauf (Eingabe, Weg, Ergebnis);
- den Schlüssel des Funds (`key`), den er unverändert zurückgibt;
- die Grenzen: Schreiben nur unter `verify/<key>/work/` im Laufordner, Python nur mit `-I`,
  Code aus dem Repo nicht importieren oder starten, sondern lesen. Das verlangt die Datei, ein
  Mechanismus erzwingt es nicht (G1).

Die Antwort ist ein Objekt `{"key", "urteil", "beleg"}`:

| `urteil` | `beleg` |
| --- | --- |
| `bestätigt` | der Ablauf mit `Datei:Zeile` |
| `widerlegt` | Pflicht: was den Ablauf verhindert, als zitierte Zeilen mit `Datei:Zeile` oder Befehl und Ausgabe |
| `unklar` | woran es fehlt |

Übergabe an das Skript, danach `merge`, damit das Urteil in `findings.json` steht:

```
review_kit.py verdict --run <lauf> <datei|->
review_kit.py merge --run <lauf>
```

Gab ein Prüfer keinen `key` zurück, nennt `--number <n>` den Auftrag, dessen Schlüssel gilt.
`verdict` weist `widerlegt` ohne Beleg ab und weiß nichts davon, was ein Prüfer wirklich geprüft
hat; das Urteil ist eine Auskunft eines zweiten Lesers. Was `verify` und `verdict` sonst tun,
steht in [packets.md](packets.md#prüfen-verify-und-verdict).
