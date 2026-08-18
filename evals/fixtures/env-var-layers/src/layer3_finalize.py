"""Layer 3: braucht API_TOKEN, um den Vorgang abzuschliessen."""

import os


def main():
    token = os.environ.get("API_TOKEN")
    if not token:
        raise RuntimeError("API_TOKEN missing")
    print("Layer 3: fertig mit Token", token)


if __name__ == "__main__":
    main()
