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
Commit-Messages des Bereichs — aber nur ab **zwei** Commits im Range; ein einzelner Commit
beschreibt mit seiner Subject-Zeile den Diff, nicht das Ziel dahinter (Tautologie-Vermeidung).
Ist nichts davon da, ist `source == "none"` und der Top-Level-Befund `no_soll` erscheint.

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
| Feature-Spec ohne Given/When/Then | zählt trotzdem als Soll, mit `excerpt` statt `criteria` |
| Symbol mit > 20 Aufrufern | `callers.shown` hat 20 Einträge, `callers.note` nennt den Rest |
| Range mit nur einem Commit | dessen Message zählt nicht als Soll (Tautologie-Vermeidung) |
