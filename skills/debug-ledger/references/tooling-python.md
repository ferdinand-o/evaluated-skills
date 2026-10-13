# Tooling: Python

Drei Rezepte für das Evidenz-Log, kein „nutz halt einen Debugger". Jedes Ergebnis
gehört mit Kommando und Fund als Zeile ins `## Evidenz-Log`.

## pytest mit Breakpoint bei erstem Fehlschlag

```bash
pytest -x --pdb tests/test_login.py::test_hang
```

`-x` stoppt beim ersten Fehlschlag, `--pdb` öffnet dort eine interaktive Session.
Nützlich für einen zuverlässig reproduzierbaren Fehlschlag ohne Multi-Prozess-Anteil.
Für nicht-interaktive Läufe (CI, Subagent) `--pdb` weglassen und stattdessen
gezielt `print()`/`logging` an der vermuteten Grenze ergänzen — das Evidenz-Log
verlangt ohnehin einen Output, den man kopieren kann, keine interaktive Session.

## debugpy headless (kein Editor, kein TTY nötig)

```bash
python -m debugpy --listen 5678 --wait-for-client -m pytest tests/test_login.py::test_hang
```

Der Prozess pausiert, bis sich ein Client auf Port 5678 verbindet (VS Code, oder
`debugpy` selbst per `python -c "import debugpy; debugpy.connect(5678)"`).
Headless heißt: Der Aufruf funktioniert auch aus einem Subagent-Kontext ohne
Editor — den Client verbindet der Mensch, der die Session weiterführt.

## faulthandler bei Hängern ohne Exception

```bash
python -X faulthandler -c "
import faulthandler, signal
faulthandler.register(signal.SIGUSR1)
import myapp; myapp.run()
"
# in einem zweiten Terminal, während der Prozess hängt:
kill -SIGUSR1 <pid>
```

Dumpt alle Thread-Stacks in `stderr` — der Weg zur Ursache bei einem Hang ohne
Traceback (Deadlock, blockierender I/O, Endlosschleife in einem Thread).

## Degradation

`debugpy` ist Tier 2 (PyPI, nicht Stdlib). Fehlt es (`ModuleNotFoundError`), sagt
das die Skill sichtbar und weicht auf `faulthandler` (Stdlib) oder eingefügte
`print`-Instrumentierung aus — nie stillschweigend ohne Werkzeug weiterarbeiten,
ohne die Lücke zu nennen (Spec 00 §3).
