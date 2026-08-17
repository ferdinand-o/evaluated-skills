"""Gemeinsame Test-Helfer. Skill-Skripte liegen außerhalb von evalkit/ und sind
keine Pakete — sie werden per importlib geladen, statt sys.path zu verbiegen."""

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_script(relpath: str):
    """Lade ein Skill-Skript als Modul, z. B. 'skills/dev-report/scripts/collect.py'.

    Registriert das Modul in `sys.modules`, bevor es ausgeführt wird — ohne das
    scheitert `@dataclass` unter Python 3.13 an `sys.modules.get(cls.__module__)`,
    weil der Klassen-Namespace beim Ausführen noch nirgends eingetragen ist.
    """
    path = REPO_ROOT / relpath
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
