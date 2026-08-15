"""Kommandozeilen-Einstieg."""

import sys

from parser import parse_line


def main() -> int:
    for line in sys.stdin:
        record = parse_line(line)
        print(f"{record['level']}\t{record['message']}")
    return 0
