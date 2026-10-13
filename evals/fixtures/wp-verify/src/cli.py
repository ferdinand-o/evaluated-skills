"""Kommandozeile `report`: gibt den Bericht als Text aus."""
import argparse

from src.report import rows


def main(argv=None):
    parser = argparse.ArgumentParser(prog="report")
    parser.parse_args(argv)
    for row in rows():
        print(f"{row['monat']}: {row['umsatz']}")


if __name__ == "__main__":
    main()
