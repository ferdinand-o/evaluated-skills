"""Layer 1: Einstiegspunkt, setzt API_TOKEN und startet Layer 2 als Subprozess."""

import os
import subprocess
import sys


def main():
    env = dict(os.environ)
    env["API_TOKEN"] = "secret-token-abc"
    result = subprocess.run(
        [sys.executable, "src/layer2_process.py"], env=env, check=False,
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
