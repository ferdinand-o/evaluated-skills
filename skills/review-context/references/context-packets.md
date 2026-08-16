# Kontextpakete: was hineingehört, je Linse gewichtet, und warum

`collect_context.py` baut **ein** JSON-Objekt (`.skills/cache/review-context.json`), das drei
Teilpakete unter `packages` trägt — eines je Linse aus Spec 04. Die Linsen selbst startet diese
Skill nicht (das tut `/code-review`); die Gewichtung bestimmt nur, was in welches Teilpaket
kommt, damit `/code-review` (oder ein Mensch) direkt weiß, welcher Teil für welche Frage zählt.

## Top-Level-Struktur

```
{
  "_meta": {"skill": "review-context", "schema": 1, "generated": "…"},
  "range": {"mode": "range"|"uncommitted", "base": "…", "head": "…"|null, "raw": "…"|null},
  "diff": {"files": [...], "total_files": N, "total_insertions": N, "total_deletions": N, "empty": bool},
  "findings": [{"id": "...", "message": "..."}],
  "packages": {"spec_compliance": {...}, "correctness": {...}, "simplification": {...}}
}
```

`findings` ist die einzige Stelle, an der das Skript selbst urteilt — und nur über zwei Dinge:
einen leeren Diff (`empty_diff`) und ein fehlendes Soll bei nicht-leerem Diff (`no_soll`, exakter
Wortlaut: „Änderung ohne benanntes Soll ist nicht reviewbar."). Alles andere ist Rohmaterial.

## Spec-Compliance — viel Soll

```
packages.spec_compliance = {
  "soll": {
    "source": "feature_spec" | "pr_description" | "commit_messages" | "none",
    "weak": false | true | null,
    "spec": [...],       # nur bei source == "feature_spec"
    "text": "…",         # nur bei source == "pr_description" | "commit_messages"
    "count": N           # nur bei source == "commit_messages"
  },
  "decisions": {"status": "read"|"missing"|"no_header"|"schema_mismatch", "entries": [...]},
  "diff_files": ["…"]
}
```

**Soll-Priorität** (R13): Feature-Spec unter `docs/specs/wip/*.md` zuerst — ihr ideales Format
sind Given/When/Then-Blöcke (Spec 03). Fehlt sie, zählt eine explizit übergebene PR-Beschreibung
(`--pr-description`/`--pr-description-file`), markiert `"weak": true`. Fehlt auch die, zählen
Commit-Messages des Bereichs, ebenfalls `"weak": true`. Ist nichts davon da, ist
`source == "none"` und der Top-Level-Befund `no_soll` erscheint.

**Existenz reicht bei keiner Quelle — es zählt der Inhalt** (Fix-Runde, siehe
`docs/known-limits.md`). Eine Feature-Spec-Datei zählt nur, wenn `_has_meaningful_spec_content()`
sie als tragfähig einstuft: ein vollständiges Given/When/Then-Kriterium reicht immer, sonst
müssen mindestens `MIN_SPEC_CONTENT_CHARS` (40) Zeichen Prosa jenseits von Überschriften und
Leerzeilen übrig bleiben. Eine leere Datei, eine mit nur Leerraum oder eine mit nur einer
Überschrift zählt nicht — die frühere Fassung prüfte nur, ob überhaupt eine `.md`-Datei im
Ordner lag, und unterdrückte damit den `no_soll`-Befund fälschlich. Eine Commit-Message zählt
über `_is_meaningful_commit_message()`: ein Body jenseits der Betreffzeile zählt immer; ohne
Body muss die (um ein Conventional-Commit-Präfix bereinigte) Betreffzeile mindestens
`MIN_SUBJECT_CHARS` (20) Zeichen haben und darf kein reiner Platzhalter sein
(`GENERIC_COMMIT_SUBJECTS`: `wip`, `fix`, `tmp`, `misc`, …). Die **Anzahl** der Commits im Range
ist dabei irrelevant — auch ein einzelner, ausführlicher Commit zählt als Soll; umgekehrt bleiben
mehrere durchweg generische Commits ("wip", "fix", "fix") weiterhin kein Soll.

**Given/When/Then-Format**, das `parse_given_when_then()` erkennt:

```markdown
### Kriterium: Leerzeilen ergeben None

- **Given** eine Zeile
- **When** sie nur Leerzeichen enthält
- **Then** liefert parse() None
- And <optionale Zusatzbedingung>
```

Überschriften (`#`–`######`) werden als Kriterien-Titel übernommen. Ein Kriterium zählt erst,
wenn Given, When und Then alle gesetzt sind — unvollständige Blöcke werden verworfen, nicht
raten-ergänzt. Eine gefundene Spec **ohne** erkennbare Given/When/Then-Blöcke zählt trotzdem als
Soll (`source == "feature_spec"`), trägt dann aber einen rohen Textauszug (`"excerpt"`) statt
strukturierter `"criteria"` — R13 verlangt nur „gar nichts gefunden" als Auslöser für den
Befund, nicht „nicht ideal formatiert".

`decisions` folgt derselben Konsumenten-Regel wie `dev-report`s Harvest: `docs/decisions.md`
ohne die Artefakt-Kopfzeile (`docs/artifact-header.md`) oder mit unbekanntem Schema wird sichtbar
übersprungen (`no_header`/`schema_mismatch`), nie geraten geparst.

## Korrektheit — viel Ist

```
packages.correctness = {
  "files": [{"path", "status", "before", "before_truncated", "before_note",
             "after", "after_truncated", "after_note", "patch", "patch_truncated"}, ...],
  "symbols": [{"name", "kind", "signature", "lineno", "file",
               "callers": {"total": N, "shown": [{"file","line","text","caller_signature"}], "note"}}]
}
```

Vorher-/Nachher-Stand je berührter Datei, plus der Patch-Text. **Symbole:** Python exakt über
`ast` (Zeilenbereich des Knotens überlappt einen geänderten Bereich → Signatur wird auch bei
mehrzeiligen Headern korrekt rekonstruiert). TypeScript/JS grep-basiert (R16) — eine Deklaration
zählt nur als berührt, wenn ihre **eigene Zeile** im geänderten Bereich liegt; anders als bei
Python wird eine reine Body-Änderung ohne Signaturänderung nicht erkannt. Benannte Grenze, kein
stiller Kompromiss.

**Aufrufer** je berührtem Symbol: repoweite grep-Suche (`\bname\s*\(`), für beide Sprachen —
auch für Python-Aufrufer-*Fundstellen* wird nicht projektweit mit `ast` gearbeitet, nur die
Signatur der umschließenden Funktion wird bei Python-Dateien per `ast` aufgelöst. Gedeckelt auf
20 Treffer; darüber steht die Zahl der nicht gezeigten im `note`-Feld, nie stilles Abschneiden.
Die Suche ist namensbasiert ohne Scope-Analyse und zählt deshalb eher zu viel als zu wenig:
`self.name(...)` oder eine gleichnamige Methode auf einem völlig anderen Objekt (z. B. ein
`set.add()`-Aufruf, wenn das berührte Symbol `add` heißt) wird mitgezählt. Bei viel Rauschen
füllt das die gedeckelten 20 Plätze mit falsch-positiven Treffern und verdrängt echte Aufrufer
aus der gezeigten Liste — siehe `docs/known-limits.md` für das reproduzierte Beispiel.

## Vereinfachung — Projekt-Konventionen und Umgebungscode

```
packages.simplification = {
  "conventions": {
    "sibling_files": {"<verzeichnis>": {"files": [...], "note": "…"|null}},
    "convention_markers": ["pyproject.toml", "tsconfig.json", …]
  },
  "diff_files": ["…"]
}
```

Geschwisterdateien je berührtem Verzeichnis (Namen, nicht Inhalt — das hält das Paket klein und
zeigt trotzdem, woran sich die Änderung stilistisch messen lassen muss), gedeckelt auf 15 je
Verzeichnis. Dazu die Existenz bekannter Konventions-Marker (`pyproject.toml`, `ruff.toml`,
`tsconfig.json`, `.eslintrc*`, `setup.cfg`) — nicht ihr Inhalt, nur ob sie da sind.

## Ränder, die das Skript benennt statt zu verschweigen

| Rand | Verhalten |
| --- | --- |
| Diff ist leer | `diff.empty == true`, Befund `empty_diff`, alle Pakete bleiben leer/kompakt |
| Datei ist neu | `before == null`, `before_note == "neu, kein Vorher-Stand"` |
| Datei ist gelöscht | `after == null`, `after_note == "gelöscht"`, keine Symbolerkennung (bekannte Grenze) |
| Binärdatei | `status == "binary"`, kein Inhalt, kein Patch, keine Symbolerkennung |
| `docs/decisions.md` fehlt | `decisions.status == "missing"` |
| Feature-Spec ohne Given/When/Then, aber mit genug Prosa | zählt als Soll, mit `excerpt` statt `criteria` |
| Feature-Spec leer, nur Leerraum oder nur eine Überschrift | zählt **nicht** als Soll — `find_feature_spec()` filtert sie heraus |
| Symbol mit > 20 Aufrufern | `callers.shown` hat 20 Einträge, `callers.note` nennt den Rest — bei viel Rauschen (z. B. gleichnamige Methoden auf anderen Objekten) können die 20 gezeigten Treffer vollständig aus falsch-positiven Fundstellen bestehen |
| Einzelner, ausführlicher Commit im Range | zählt als Soll — die Anzahl der Commits im Range ist irrelevant, nur der Inhalt jeder Message zählt |
| Mehrere generische Commits im Range ("wip", "fix") | zählen weiterhin nicht als Soll, unabhängig von ihrer Anzahl |
