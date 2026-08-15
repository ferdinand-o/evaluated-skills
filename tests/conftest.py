"""Gemeinsame Test-Helfer. Skill-Skripte liegen außerhalb von evalkit/ und sind
keine Pakete — sie werden per importlib geladen, statt sys.path zu verbiegen."""

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_script(relpath: str):
    """Lade ein Skill-Skript als Modul, z. B. 'skills/dev-report/scripts/collect.py'."""
    path = REPO_ROOT / relpath
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    # Vor exec_module registrieren: `dataclasses` schlägt beim Auswerten eines
    # Feldes in `sys.modules[cls.__module__]` nach, um aufgeschobene Annotationen
    # aufzulösen. Fehlt der Eintrag, stirbt jede Skill, die `from __future__ import
    # annotations` mit einem @dataclass kombiniert, schon beim Import — mit einem
    # AttributeError auf None, der wie ein Fehler im Skill-Code aussieht und nicht
    # wie einer im Testhelfer.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
