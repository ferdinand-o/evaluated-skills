# cli-library — Public-API und CLI-Output

Geladen bei `primary: "cli-library"`. Zwei Oberflächen zählen: die
**öffentliche API**, die andere Pakete importieren, und der **CLI-Output**,
den Menschen und Skripte lesen. Beides sind Contracts — interne
Hilfsfunktionen sind es nicht.

## Snapshot von CLI-Output

CLI-Output (stdout, stderr, Exit-Code) ist ein guter Snapshot-Kandidat — im
Gegensatz zu Domänenlogik ändert er sich selten und absichtlich, und ein Diff
zeigt sofort, was sich am sichtbaren Verhalten geändert hat.

```python
# Python: subprocess-Aufruf, drei Assertions statt eines rohen String-Snapshots
def test_cli_reports_missing_file(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "mytool", "--input", str(tmp_path / "fehlt.csv")],
        capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert "fehlt.csv" in result.stderr
    assert result.stdout == ""
```

```ts
// TypeScript: gleiche Idee, execa/child_process statt eines Shell-Strings
test("meldet fehlende Datei mit Exit-Code 2", async () => {
  const { exitCode, stderr, stdout } = await runCli(["--input", "fehlt.csv"]);
  expect(exitCode).toBe(2);
  expect(stderr).toContain("fehlt.csv");
  expect(stdout).toBe("");
});
```

**Drei separate Assertions statt eines vollen String-Snapshots**, wenn möglich:
Ein kompletter Snapshot bricht bei jeder kosmetischen Formatierungsänderung
(Leerzeichen, Farbcodes), auch wenn Exit-Code und Kernaussage unverändert
sind. Ein echter Snapshot lohnt sich für strukturierte Ausgaben mit vielen
Feldern (`--format json`, generierte Hilfetexte) — dort ist das ganze Objekt
der Contract.

## Public-API-Tests für Bibliotheken

Bei einer Library statt eines reinen CLI-Tools ist die öffentliche
Import-Schnittstelle der Contract:

- Ein Test pro exportierter Funktion/Klasse, über die **öffentliche**
  Signatur — Parameter, Rückgabewert, dokumentiertes Fehlerverhalten.
- **Typen sind Teil des Contracts**, aber kein Ersatz für einen Test:
  `mypy`/`tsc` prüfen, dass Aufrufer korrekt typisiert aufrufen — nicht, dass
  die Funktion bei korrektem Aufruf das Richtige tut.
- Ein Breaking Change an der öffentlichen Signatur ist ein Befund für die
  Versionierung (SemVer major), kein Grund, den Test klammheimlich anzupassen.
- Interne Module (nicht im Package-`__init__.py`/`index.ts`-Export gelistet)
  sind **kein** Public-API-Test-Ziel — sie dürfen sich frei ändern, solange der
  Export stabil bleibt. Das ist der Regressions-Fang-pro-Wartungskosten-Vorteil
  dieses Schnitts.

## Test-Plan-Schichten für cli-library

1. **CLI-Output-Tests** für jeden dokumentierten Befehl/jede Flag-Kombination
   mit beobachtbarem Nutzerverhalten (Erfolg, definierte Fehlerfälle,
   `--help`).
2. **Public-API-Tests** für jede exportierte Funktion/Klasse, wenn das Paket
   auch als Library importiert wird.
3. Interne Hilfsfunktionen ohne öffentlichen Export: Unit-Tests nur, wo die
   Logik komplex genug ist, dass ein CLI-/API-Test sie nicht mehr eindeutig
   lokalisiert — sonst reicht die Abdeckung über die Außensicht, und ein
   eigener Unit-Test wäre zusätzliche Wartungskosten ohne zusätzlichen
   Regressions-Fang.
