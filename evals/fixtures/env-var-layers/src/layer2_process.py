"""Layer 2: liest API_TOKEN, ruft Layer 3 auf.

BUG: baut fuer den Subprozess ein komplett neues Environment und vergisst dabei
API_TOKEN mitzugeben -- der Token existiert in diesem Prozess, geht aber beim
Aufruf von Layer 3 verloren.
"""

import os
import subprocess
import sys


def main():
    token = os.environ.get("API_TOKEN")
    if not token:
        print("Layer 2: API_TOKEN fehlt bereits hier", file=sys.stderr)
        sys.exit(1)

    child_env = {"PATH": os.environ.get("PATH", "")}  # API_TOKEN fehlt hier
    result = subprocess.run(
        [sys.executable, "src/layer3_finalize.py"], env=child_env, check=False,
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
