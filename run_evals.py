#!/usr/bin/env python3
"""Eval-Runner für die Skill-Sammlung. Tier 1: nur Stdlib.

    python run_evals.py --skill handoff --class contract
"""

import sys

from evalkit.runner import main

if __name__ == "__main__":
    sys.exit(main())
