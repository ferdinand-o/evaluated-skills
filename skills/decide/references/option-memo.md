# Vorlage für eine große Frage

Eine große Frage geht an den Nutzer als Vorlage, die er in einer Minute entscheiden kann: Er
liest keine Herleitung, sondern wählt zwischen Optionen, deren Folgen und Umkehrbarkeit dastehen.
Die Vorlage steht zweimal: als Text an den Nutzer und als Block in `docs/big-decisions.md`.
Beide sagen dasselbe; den Block legt `decide_log.py add --class gross` an.

## Form der Vorlage

1. **Auftrag zuerst.** Ein Satz: Was ist die laufende Aufgabe, und was hängt an der Antwort?
   (Der Anlass aus `brief`, derselbe Gedanke: ohne ihn weiß der Nutzer nicht, wofür er
   entscheidet.)
2. **Frage.** Ein Satz, neutral, ohne Empfehlung darin.
3. **Zwei bis vier Optionen**, je mit Buchstabe, Inhalt, Folgen und Umkehrbarkeit. Weniger als
   zwei ist keine Wahl, mehr als vier lehnt das Skript mit Exit 1 ab (und `AskUserQuestion` nimmt
   höchstens vier). Sind es mehr, fasse verwandte zusammen. Umkehrbarkeit nennt, was ein
   Zurücknehmen kostet, in den Worten von `references/reversibility.md` (billig, per Revert,
   nicht umkehrbar).
4. **Empfehlung mit Grund.** `B, weil …` — eine Option und ein Grund, der aus Belegen folgt, nicht
   „am besten". Hat Claude keine Empfehlung, ist die Frage noch nicht erarbeitet.
5. **Was bis zur Antwort unterbleibt**, ein Satz: die ganze Antwort auf die Frage, nicht nur ihr
   teuerster Teil.

## Mehrere Fragen bündeln

Große Fragen sammeln sich, die übrige Arbeit läuft weiter. Gestellt werden sie gemeinsam, mit
einem `AskUserQuestion`-Aufruf je Gruppe:

- höchstens vier Optionen je Frage; bei mehr Optionen vorher zusammenfassen;
- höchstens vier Fragen je Aufruf; mehr Fragen gehen in einen zweiten Aufruf;
- die Reihenfolge nach Abhängigkeit: Wovon eine andere Antwort abhängt, kommt zuerst;
- jede Option trägt Buchstaben und Kurzform im Label, Folgen und Umkehrbarkeit in der Beschreibung;
  die empfohlene steht zuerst und trägt „(empfohlen)";
- jede Frage bleibt eine eigene: Zwei Fragen, die nur zusammen Sinn ergeben, sind eine.

Ohne `AskUserQuestion` in der Werkzeugliste (unbeaufsichtigt, jeder Subagent) bleibt der Block
offen; die Übergabe nennt `D-<n>`.

## Der Block in `docs/big-decisions.md`

`add --class gross` legt ihn mit Status `offen` an. Beispiel, so schreibt ihn das Skript:

```
## D-1 · 2026-11-03 · offen
Frage: Datumsangaben mit einer neuen Abhängigkeit parsen oder mit der Stdlib?
Thema: Abhängigkeiten
Schlüssel: dependency:pyproject.toml#python-dateutil
Optionen:
- A: python-dateutil aufnehmen — Folgen: neue Laufzeitabhängigkeit, parst fast jedes Format — Umkehrbarkeit: per Revert, aber Lieferkette
- B: datetime.strptime mit drei festen Formaten — Folgen: nur diese Formate, kein neues Paket — Umkehrbarkeit: billig
Empfehlung: B, weil die Eingaben nur drei Formate haben und keine Abhängigkeit nötig ist
Antwort: —
Quelle der Antwort: —
```

Aufruf dazu. `decide_log.py` steht in dieser Datei für den Aufruf mit vollem Pfad, wie ihn die
SKILL.md nennt; der Rest der Zeile gilt wörtlich:

```bash
decide_log.py add --class gross \
  --topic Abhängigkeiten \
  --question "Datumsangaben mit einer neuen Abhängigkeit parsen oder mit der Stdlib?" \
  --key "dependency:pyproject.toml#python-dateutil" \
  --option "A: python-dateutil aufnehmen — Folgen: … — Umkehrbarkeit: per Revert, aber Lieferkette" \
  --option "B: datetime.strptime mit drei festen Formaten — Folgen: … — Umkehrbarkeit: billig" \
  --recommendation "B, weil die Eingaben nur drei Formate haben und keine Abhängigkeit nötig ist"
```

Status ist `offen`, `freigegeben` oder `abgelehnt`; der Block bleibt nach der Antwort stehen.

**Schlüssel** `<kategorie>:<pfadmuster>[#<text>]`: Kategorie aus `reversibility.md` (`api`,
`migration`, `data-delete`, `unsaved-work`, `push`, `external`, `permissions`, `dependency`,
`cost`) oder `rule:<thema>`, wenn eine Regel `immer fragen` das Thema trifft. Das Pfadmuster ist
relativ zur Repo-Wurzel; endet es auf `/`, ist es ein Präfix. Mit `#<text>` gibt der Eintrag eine
Datei nur frei, wenn ihre hinzugefügten Zeilen `<text>` enthalten — im Beispiel nur die Zeile mit
`python-dateutil` in `pyproject.toml`, nicht jede andere Änderung dort. Nur entfernte Zeilen gibt
nur ein Schlüssel ohne Text frei (Entfernen einer Abhängigkeit, Löschen einer Migration:
`dependency:pyproject.toml`); ein Text, der mit `-` oder `+` beginnt, wird abgewiesen. Eine
Freigabe gilt für ihren Schlüssel, nicht für eine einzelne Änderung: Wer sie enger will, nimmt
`#<text>`.

## Quelle der Antwort

Jeder Block nennt, woher die Antwort kommt. Genau drei Werte:

| Quelle der Antwort: | Wann | Wer schreibt sie |
| --- | --- | --- |
| `Nutzer in Sitzung` | der Nutzer hat die Vorlage beantwortet | `resolve` |
| `Auftrag: „<Zitat>"` | der Nutzer hat genau diesen Schritt beauftragt | `add --approved-by-request` |
| `von Hand` | jemand hat den Block in der Datei selbst bearbeitet | niemand im Skript |

## Pflichtfelder je Weg

| Weg | Pflicht | Optionen | Schlüssel |
| --- | --- | --- | --- |
| `add --class gross` | `--topic`, `--question`, `--key`, `--recommendation` | zwei bis vier `--option`, sonst Exit 1 | Kategorie aus `reversibility.md`, oder `rule:<thema>` bei einer Regel `immer fragen` — sonst Exit 1 |
| `add --class gross --approved-by-request "<Zitat>"` | `--topic`, `--question`, `--key`, Zitat | keine; der Block nennt „Optionen: — (Auftrag)" | wie oben |
| `add --class klein`, von `immer fragen` hochgestuft | `--topic`, `--question`, `--decision`, `--evidence` | zwei bis vier `--option`, sonst Exit 1; `--decision` wird die Empfehlung | `rule:<thema>`, von `check` nie verglichen |

Eine Frage, die nur wegen einer Regel `immer fragen` groß ist, legt Claude mit `add --class gross`
und `--key "rule:<thema>"` ab; das ist der vorgesehene Weg (Spec 28, Ablauf 2). Die dritte Zeile
beschreibt, was das Skript tut, wenn Claude die Regel übersehen und `--class klein` aufgerufen hat:
Es stuft den Eintrag hoch und verlangt dafür die Optionen.

`--approved-by-request` gilt nur, wenn Handlung und Gegenstand im Auftrag stehen („nimm `httpx`
als Abhängigkeit auf"). Ein Auftrag, der das Ergebnis offen lässt, gibt die Aufgabe frei, nicht die
Wahl darin. Der Schlüssel nennt genau den beauftragten Gegenstand:

```bash
decide_log.py add --class gross --topic Abhängigkeiten --question "httpx als Abhängigkeit aufnehmen?" \
  --key "dependency:pyproject.toml#httpx" --approved-by-request "nimm httpx als Abhängigkeit auf"
```

## Antwort eintragen

Beaufsichtigt, nach `AskUserQuestion`, einer der beiden Aufrufe:

```bash
decide_log.py resolve D-1 --answer "B, wie empfohlen"
decide_log.py resolve D-1 --reject
```

`resolve` setzt den Status auf `freigegeben` (mit `--reject` auf `abgelehnt`), schreibt die Antwort
und als Quelle `Nutzer in Sitzung`:

```
## D-1 · 2026-11-03 · freigegeben
…
Antwort: B, wie empfohlen
Quelle der Antwort: Nutzer in Sitzung
```

`resolve` ändert nur Blöcke mit Status `offen`; ein beantworteter Block bleibt, wie er ist. Erst
nach `freigegeben` handelt Claude; bei `abgelehnt` unterbleibt der Schritt, und die Aufgabe
sucht den Weg ohne ihn. `decide_log.py open` listet, was noch offen ist.
