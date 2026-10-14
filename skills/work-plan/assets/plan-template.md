<!-- skill: work-plan | schema: 1 | generated: von Hand nach work-plan/assets/plan-template.md -->

# CSV-Export der Berichte — Plan

**Goal:** Berichte lassen sich mit `report --csv <datei>` als CSV schreiben — ein Satz,
der sagt, was danach anders ist. Alle Beispielwerte in diesem Template ersetzen.

**Architecture:** Welche Dateien, welche Module, wo der Code liegt und warum; was
unverändert bleibt.

**Auftrag:** „CSV-Export der Berichte mit CLI-Option `--csv` und einem Abschnitt in der
README." — Wortlaut des Nutzers, ein Issue-Link oder der Pfad eines Befunds. Liegt eine
feature-spec-Spec vor, ersetzt das Feld Spec mit ihrem Pfad in Backticks diese Zeile;
nie beide.

- Annahme: Die Spalten folgen den Schlüsseln der ersten Zeile.
- Annahme: Eine leere Liste ergibt eine leere Datei ohne Kopfzeile.

### Task 1: CSV hat Kopfzeile

**Files:**
- Create: `src/export.py`
- Test: `tests/test_export.py`

**Interfaces:**
- Consumes: (nichts Neues)
- Produces: `fn:write_csv(rows, path)`

- [ ] **Step 1: Test schreiben** — eine Liste mit zwei Zeilen ergibt eine Datei, deren
      erste Zeile die Spaltennamen trägt.
- [ ] **Step 2: Rot sehen** — der Test scheitert, solange `write_csv` fehlt.
- [ ] **Step 3: Implementieren** — `write_csv` mit `csv.writer`.
- [ ] **Step 4: Grün sehen**, dann der Verifikationsbefehl.
- [ ] **Step 5: Commit.**

### Task 2: CLI-Option und README

**Files:**
- Modify: `src/cli.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `fn:write_csv(rows, path)`
- Produces: `token:--csv`

- [ ] **Step 1: Schreiben** — Option `--csv <datei>` ruft `write_csv`; README-Abschnitt
      „Export" mit dem Aufruf.
- [ ] **Step 2: Prüfen** — der Aufruf aus der README läuft und schreibt die Datei.
- [ ] **Step 3: Commit.**

### Task 3: Verifikation

**Files:**
- Test: `CLAUDE.md`

**Interfaces:**
- Consumes: `fn:write_csv(rows, path)`, `token:--csv`
- Produces: (nichts Neues)

- [ ] **Step 1: Verifikation** — den Befehl aus der CLAUDE.md-Zeile `Verifikation:` laufen
      lassen (sonst aus `Makefile`, `package.json` oder `pyproject.toml`; ohne Befehl
      „Verifikation: keine — ungeprüft"); erwartet: grün. Befehl und Ergebnis gehören in
      die Übergabe.
