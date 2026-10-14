#!/usr/bin/env python3
"""Wörter einer Notiz zählen. Tier 1: nur Stdlib."""
import sys
from pathlib import Path

print(len(Path(sys.argv[1]).read_text(encoding="utf-8").split()))
