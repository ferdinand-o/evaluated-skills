# Context Harvest: welche Artefakte, wie gelesen

`collect.py` prüft nach dem Git-Sammeln definierte Repo-Artefakte als zweite
Faktenquelle. Keines davon wird vorausgesetzt.

| Quelle | Was sie beiträgt |
| --- | --- |
| `docs/debugging/INDEX.md` | Das *Warum* hinter Fix-Commits: gelöste Bugs samt Ursache |
| `docs/decisions.md` | Grundsatzentscheidungen, die den Zeitraum erklären |
| `docs/specs/wip/` | Geplantes gegen Geliefertes |
| `CHANGELOG.md` | Bereits formulierte Kundensicht |
| `handoff.md` | Offene Probleme mit Stand |

## Die Konsumenten-Regel

Jede Quelle wird über ihre Kopfzeile gelesen, nie über eine Formatannahme
(Spec 00 §1). `facts.json` führt pro Quelle einen `status`:

- `read` — Kopfzeile gefunden, Schema passt, Inhalt übernommen.
- `missing` — Datei existiert nicht. Normalfall, keine Meldung nötig.
- `no_header` — Datei da, aber ohne Kopfzeile. Sie stammt nicht aus dieser
  Sammlung und wird **nicht** geparst.
- `schema_mismatch` — Kopfzeile da, Version unbekannt. Übersprungen.

`no_header` und `schema_mismatch` gehören in den Report als Einschränkung.
Stillschweigend zu raten ist der einzige verbotene Weg.
