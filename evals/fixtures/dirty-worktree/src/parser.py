"""Übersetzt Logzeilen in Records."""


def parse_line(line: str) -> dict[str, str]:
    level, _, message = line.partition(":")
    return {"level": level.strip(), "message": message.strip()}
