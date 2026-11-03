"""Kommandozeile: zählt die Zeilen einer Datei."""
import sys
from pathlib import Path


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("Aufruf: python -m app.cli <datei>", file=sys.stderr)
        return 2
    path = Path(argv[0])
    if not path.is_file():
        print("Fehler: ENOENT", file=sys.stderr)
        return 1
    print(len(path.read_text(encoding="utf-8").splitlines()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
