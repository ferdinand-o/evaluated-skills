#!/usr/bin/env python3
"""Given/When/Then aus einer feature-spec-Markdown-Datei in Test-Stubs exportieren.

Tier 1: nur Stdlib. Kein pytest-Import zur Laufzeit, kein YAML-Paket.

Dies ist der mechanische Contract aus Spec 03: Eine Spec ohne Non-Goals oder
mit Prosa-Kriterien statt Given/When/Then ist unvollständig. Dieses Skript
urteilt darüber (G2-Gate nach Spec 00 §4 — es meldet Verstoß, es blockiert
nicht, der Aufruf bleibt Teil des Workflows). Verweigert es, schreibt es
KEINE Stub-Datei — auch nicht für die Kriterien, die sauber geparst hätten.
Ein halber Export sieht aus wie ein voller und ist deshalb schlimmer als
keiner.
"""

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

SCHEMA_VERSION = 1

PYTEST_SKIP_MARKER = '@pytest.mark.skip("stub: noch nicht implementiert")'
VITEST_TODO_MARKER = "it.todo("

STUB_HEADER_RE = re.compile(r"^#\s*spec-stub:\s*(?P<slug>[a-z0-9_-]+)\s*$")
VITEST_HEADER_RE = re.compile(r"^//\s*spec-stub:\s*(?P<slug>[a-z0-9_-]+)\s*$")

_TRIPLE_QUOTE_RE = re.compile(r'"""|\'\'\'')

H1_RE = re.compile(r"^#\s+(?!#)(.+?)\s*$")
FEATURE_HEADING_RE = re.compile(r"^#\s+Feature:\s*(.+?)\s*$")
H2_RE = re.compile(r"^##\s+(?!#)(.+?)\s*$")
H3_RE = re.compile(r"^###\s+(?!#)(.+?)\s*$")
BULLET_RE = re.compile(r"^-\s+(.*)$")
GWT_ITEM_RE = re.compile(r"^(Given|When|Then|And)\b[:\s]+(.*)$", re.IGNORECASE)

_UMLAUT_MAP = str.maketrans({
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
    "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
})


class SpecParseError(RuntimeError):
    """Die Spec verletzt den Contract — Export verweigert, nichts geschrieben."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("; ".join(problems))


@dataclass(frozen=True)
class Criterion:
    title: str
    slug: str
    heading_line: int
    given: tuple[str, ...]
    when: tuple[str, ...]
    then: tuple[str, ...]


def slugify(text: str, max_len: int = 60) -> str:
    text = text.translate(_UMLAUT_MAP).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    if not text:
        return "kriterium"
    return text[:max_len].rstrip("-") or "kriterium"


def ident(slug: str) -> str:
    """Slug als Python-/JS-taugliches Namensfragment (Bindestrich -> Unterstrich)."""
    return slug.replace("-", "_")


def derive_feature(lines: list[str], spec_path: Path) -> str:
    for line in lines:
        match = FEATURE_HEADING_RE.match(line)
        if match:
            return slugify(match.group(1))
    for line in lines:
        match = H1_RE.match(line)
        if match:
            return slugify(match.group(1))
    return slugify(spec_path.stem)


def _find_section(lines: list[str], title: str) -> tuple[int, int] | None:
    """Bereich einer `## <title>`-Sektion als (start, end) exklusiv, 0-basiert.

    `start` zeigt auf die Überschriftzeile selbst, `end` auf die nächste
    `## `-Überschrift oder das Dateiende.
    """
    start = None
    for i, line in enumerate(lines):
        match = H2_RE.match(line)
        if match and match.group(1).strip().lower() == title.lower():
            start = i
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if H2_RE.match(lines[j]):
            end = j
            break
    return start, end


def _extract_top_bullets(lines: list[str], start: int, end: int) -> list[tuple[int, str]]:
    """`- `-Zeilen im Bereich [start, end), als (1-basierte Zeilennummer, Text)."""
    out: list[tuple[int, str]] = []
    for i in range(start, end):
        match = BULLET_RE.match(lines[i])
        if match:
            out.append((i + 1, match.group(1).strip()))
    return out


def _parse_criterion_block(
    title: str, heading_line: int, lines: list[str], start: int, end: int, problems: list[str]
) -> Criterion | None:
    bullets = _extract_top_bullets(lines, start, end)
    if not bullets:
        problems.append(
            f"Zeile {heading_line}: Kriterium '{title}' ist nicht als Given/When/Then "
            f"formuliert (keine '- '-Liste unter der Überschrift — sieht nach Prosa aus)"
        )
        return None

    buckets: dict[str, list[str]] = {"given": [], "when": [], "then": []}
    current: str | None = None
    ok = True
    for line_no, text in bullets:
        match = GWT_ITEM_RE.match(text)
        if not match:
            problems.append(
                f"Zeile {line_no}: '{text[:60]}' beginnt nicht mit Given/When/Then/And — "
                f"Kriterium '{title}' ist (teilweise) Prosa, kein Given/When/Then"
            )
            ok = False
            continue
        keyword = match.group(1).lower()
        rest = match.group(2).strip()
        if keyword == "and":
            if current is None:
                problems.append(
                    f"Zeile {line_no}: 'And' ohne vorausgehendes Given/When/Then in "
                    f"Kriterium '{title}'"
                )
                ok = False
                continue
        else:
            current = keyword
        buckets[current].append(rest)

    if not ok:
        return None

    missing = [k for k in ("given", "when", "then") if not buckets[k]]
    if missing:
        problems.append(
            f"Zeile {heading_line}: Kriterium '{title}' fehlt {', '.join(missing)} — "
            f"Given/When/Then unvollständig"
        )
        return None

    return Criterion(
        title=title,
        slug=slugify(title),
        heading_line=heading_line,
        given=tuple(buckets["given"]),
        when=tuple(buckets["when"]),
        then=tuple(buckets["then"]),
    )


def parse_spec(lines: list[str]) -> list[Criterion]:
    """Validiere und parse eine Spec. Wirft SpecParseError mit ALLEN Verstößen gesammelt.

    Kein früher Abbruch: fehlende Non-Goals UND ein Prosa-Kriterium erscheinen
    beide in derselben Fehlermeldung, statt dass der Nutzer sie nacheinander
    entdecken muss.
    """
    problems: list[str] = []

    non_goals = _find_section(lines, "Non-Goals")
    if non_goals is None:
        problems.append(
            "## Non-Goals fehlt — laut Contract ist die Spec unvollständig "
            "(mindestens ein explizites 'bauen wir nicht' nötig)"
        )
    else:
        ng_start, ng_end = non_goals
        if not _extract_top_bullets(lines, ng_start + 1, ng_end):
            problems.append(
                f"Zeile {ng_start + 1}: ## Non-Goals ist leer — mindestens ein "
                f"'bauen wir nicht' nötig"
            )

    criteria: list[Criterion] = []
    acceptance = _find_section(lines, "Akzeptanzkriterien")
    if acceptance is None:
        problems.append(
            "## Akzeptanzkriterien fehlt — kein Kriterium zum Exportieren gefunden"
        )
    else:
        ak_start, ak_end = acceptance
        h3_indices = [i for i in range(ak_start + 1, ak_end) if H3_RE.match(lines[i])]
        if not h3_indices:
            problems.append(
                f"Zeile {ak_start + 1}: ## Akzeptanzkriterien enthält keine Kriterien "
                f"(keine '### Titel'-Überschriften)"
            )
        seen_slugs: dict[str, int] = {}
        for idx, h3_i in enumerate(h3_indices):
            title = H3_RE.match(lines[h3_i]).group(1).strip()
            heading_line = h3_i + 1
            block_end = h3_indices[idx + 1] if idx + 1 < len(h3_indices) else ak_end
            slug = slugify(title)
            if slug in seen_slugs:
                problems.append(
                    f"Zeile {heading_line}: Kriterium '{title}' erzeugt denselben Slug "
                    f"'{slug}' wie Zeile {seen_slugs[slug]} — Titel eindeutiger formulieren"
                )
                continue
            seen_slugs[slug] = heading_line
            criterion = _parse_criterion_block(
                title, heading_line, lines, h3_i + 1, block_end, problems
            )
            if criterion is not None:
                criteria.append(criterion)

    if problems:
        raise SpecParseError(problems)
    return criteria


def _pytest_stub_content(feature: str, criterion: Criterion, spec_path: Path) -> str:
    doc_lines = [f'Stub für Akzeptanzkriterium "{criterion.title}" aus {spec_path.as_posix()}.', ""]
    doc_lines += [f"Given {g}" for g in criterion.given]
    doc_lines += [f"When {w}" for w in criterion.when]
    doc_lines += [f"Then {t}" for t in criterion.then]
    fn_name = f"test_{ident(feature)}_{ident(criterion.slug)}"
    body = [
        f"# spec-stub: {criterion.slug}",
        '"""' + "\n".join(doc_lines) + '\n"""',
        "import pytest",
        "",
        "",
        PYTEST_SKIP_MARKER,
        f"def {fn_name}():",
        "    # Arrange",
        "    ...",
        "",
        "    # Act",
        "    ...",
        "",
        "    # Assert",
        "    ...",
    ]
    return "\n".join(body) + "\n"


def _vitest_stub_content(feature: str, criterion: Criterion, spec_path: Path) -> str:
    given = "; ".join(criterion.given)
    when = "; ".join(criterion.when)
    then = "; ".join(criterion.then)
    title_escaped = criterion.title.replace("'", "\\'")
    return (
        f"// spec-stub: {criterion.slug}\n"
        f"// Kriterium aus {spec_path.as_posix()}: {criterion.title}\n"
        f"// Given {given}\n"
        f"// When {when}\n"
        f"// Then {then}\n"
        "import { describe, it } from 'vitest';\n"
        "\n"
        f"describe('{feature}: {title_escaped}', () => {{\n"
        f"  it.todo('{title_escaped}');\n"
        "});\n"
    )


def _first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""


def _code_lines(text: str) -> list[str]:
    """Zeilen außerhalb von Docstrings/Triple-Quote-Strings.

    Naiv per Vorkommen-Parität von `'''`/`\"\"\"` erkannt, kein echter
    Python-Parser — reicht aber, um einen Marker zu unterscheiden, der als
    aktive Code-Zeile steht, von einem, der nur als Text innerhalb eines
    Docstrings erwähnt wird (z. B. in einer Beschreibung, die den Marker
    zitiert). Reicht für die generierten Stubs (ein Docstring-Block pro
    Datei) und für die Fälle, die dieser Contract abwehren soll.
    """
    out: list[str] = []
    in_string = False
    for line in text.splitlines():
        occurrences = len(_TRIPLE_QUOTE_RE.findall(line))
        if in_string:
            if occurrences % 2 == 1:
                in_string = False
            continue
        if occurrences % 2 == 1:
            in_string = True
            continue
        out.append(line)
    return out


def should_write_pytest(target: Path) -> bool:
    """Sicher (neu) zu schreiben, solange Header UND ein aktiver Skip-Marker
    noch da sind.

    "Aktiv" heißt: eine Code-Zeile (nicht in einem Docstring), deren Inhalt
    exakt der generierte Marker ist — nicht bloß irgendwo im Dateitext
    enthalten. Ein auskommentierter Marker (`# @pytest.mark.skip(...)`) oder
    einer, der nur als Text in einem Docstring auftaucht, zählt nicht als
    aktiv: Beides ist der naheliegendste Weg, einen Stub zu "aktivieren",
    und darf den nächsten Export nicht dazu bringen, die Implementierung
    stillschweigend mit einem leeren Stub zu überschreiben.
    """
    if not target.is_file():
        return True
    text = target.read_text(encoding="utf-8", errors="replace")
    has_header = bool(STUB_HEADER_RE.match(_first_nonempty_line(text)))
    has_active_skip = any(line.strip() == PYTEST_SKIP_MARKER for line in _code_lines(text))
    return has_header and has_active_skip


def should_write_vitest(target: Path) -> bool:
    """Vitest-Pendant zu `should_write_pytest`: ein aktives `it.todo(` ist eine
    Zeile, die damit beginnt und nicht mit `//` auskommentiert ist."""
    if not target.is_file():
        return True
    text = target.read_text(encoding="utf-8", errors="replace")
    has_header = bool(VITEST_HEADER_RE.match(_first_nonempty_line(text)))
    has_active_todo = any(
        line.strip().startswith(VITEST_TODO_MARKER)
        for line in text.splitlines()
        if not line.strip().startswith("//")
    )
    return has_header and has_active_todo


def write_pytest_stubs(
    criteria: list[Criterion], feature: str, spec_path: Path, out_dir: Path
) -> tuple[list[str], list[str]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    skipped: list[str] = []
    for criterion in criteria:
        target = out_dir / f"test_{ident(feature)}_{ident(criterion.slug)}.py"
        if should_write_pytest(target):
            target.write_text(_pytest_stub_content(feature, criterion, spec_path), encoding="utf-8")
            created.append(target.as_posix())
        else:
            skipped.append(target.as_posix())
    return created, skipped


def write_vitest_stubs(
    criteria: list[Criterion], feature: str, spec_path: Path, out_dir: Path
) -> tuple[list[str], list[str]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    skipped: list[str] = []
    for criterion in criteria:
        target = out_dir / f"{feature}.{criterion.slug}.test.ts"
        if should_write_vitest(target):
            target.write_text(_vitest_stub_content(feature, criterion, spec_path), encoding="utf-8")
            created.append(target.as_posix())
        else:
            skipped.append(target.as_posix())
    return created, skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Given/When/Then aus einer feature-spec-Markdown-Datei in Test-Stubs exportieren"
    )
    parser.add_argument("spec", type=Path, help="Pfad zur Spec-Markdown-Datei")
    parser.add_argument("--feature", help="Feature-Name für Dateipräfixe (sonst aus der Spec abgeleitet)")
    parser.add_argument("--out-dir", type=Path, default=Path("tests"), help="Zielverzeichnis für pytest-Stubs")
    parser.add_argument("--vitest", action="store_true", help="zusätzlich it.todo()-Stubs für Vitest erzeugen")
    parser.add_argument(
        "--vitest-out-dir", type=Path, default=Path("tests/js"), help="Zielverzeichnis für Vitest-Stubs"
    )
    args = parser.parse_args(argv)

    if not args.spec.is_file():
        print(f"Spec nicht gefunden: {args.spec}", file=sys.stderr)
        return 1

    lines = args.spec.read_text(encoding="utf-8").splitlines()
    feature = args.feature or derive_feature(lines, args.spec)

    try:
        criteria = parse_spec(lines)
    except SpecParseError as exc:
        print(f"Export verweigert — {args.spec} erfüllt den Contract nicht:", file=sys.stderr)
        for problem in exc.problems:
            print(f"  {problem}", file=sys.stderr)
        print("Keine Stub-Datei wurde geschrieben.", file=sys.stderr)
        return 1

    created, skipped = write_pytest_stubs(criteria, feature, args.spec, args.out_dir)
    for path in created:
        print(f"erzeugt: {path}")
    for path in skipped:
        print(f"übersprungen (bereits implementiert): {path}")
    summary = [f"{len(created)} pytest-Stub(s) erzeugt", f"{len(skipped)} übersprungen"]

    if args.vitest:
        v_created, v_skipped = write_vitest_stubs(criteria, feature, args.spec, args.vitest_out_dir)
        for path in v_created:
            print(f"erzeugt (vitest): {path}")
        for path in v_skipped:
            print(f"übersprungen (vitest, bereits implementiert): {path}")
        summary.append(f"{len(v_created)} Vitest-Stub(s) erzeugt")
        summary.append(f"{len(v_skipped)} Vitest übersprungen")

    print(", ".join(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
