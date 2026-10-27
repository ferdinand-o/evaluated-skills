#!/usr/bin/env python3
"""mobile-audit Stufe 1: Quelltext-Checks ohne Browser. Tier 1, nur Stdlib.

Vier der sieben Checks aus Spec 15 brauchen keine Geräte-Matrix, weil ihr Defekt
schon im Quelltext steht: `100vh`, zu kleine Eingabefeld-Schriften, Zoom-Sperren im
Viewport-Meta und Hover-Interaktionen ohne Touch-Pfad. Sie laufen deshalb immer —
auch dort, wo Playwright fehlt.

Das ist die Lehre aus `motion-landing/scripts/verify.py`: Dessen Wert hängt
vollständig an einer Tier-3-Toolchain, und in der Umgebung, in der es entstand, lief
nie etwas anderes als sein Degradationszweig. Ein Audit, das ohne Browser gar nichts
sagen kann, sagt im Zweifel gar nichts.

Was dieses Skript NICHT kann, steht als `stage_2: ungeprüft` in jedem Bericht:
horizontales Overflow, echte Hit-Area-Größen und Safe-Area-Verletzungen entstehen
erst im Layout. Stufe 1 spricht nie für Stufe 2 (Spec 00 §4: ein übersprungener
Check meldet nie Erfolg).

G2 nach Spec 00 §4: Das Skript fällt ein maschinelles Urteil und meldet Verstöße,
der Aufruf bleibt freiwillig — es blockiert nichts.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCHEMA_VERSION = 1

# Das Preset liegt neben dem Skript, nicht im aufrufenden Projekt: ein repo-relativer
# Pfad fand es nur im evaluated-skills-Repo selbst und brach überall sonst ab
# (Testlauf-Befund an lint_schema.py:29).
SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = SKILL_DIR / "assets" / "audit-config.json"
PROJECT_OVERRIDE_PATH = Path(".skills") / "mobile-audit" / "audit-config.json"
CACHE_PATH = Path(".skills") / "cache" / "mobile-audit-static.json"

# --- Muster ----------------------------------------------------------------------

VIEWPORT_UNIT_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)vh(?![\w-])")
INPUT_SELECTOR_RE = re.compile(r"\b(?:input|select|textarea)\b", re.I)
FONT_SIZE_RE = re.compile(r"font-size\s*:\s*(\d+(?:\.\d+)?)px", re.I)
VIEWPORT_META_RE = re.compile(r"<meta[^>]*name\s*=\s*[\"']viewport[\"'][^>]*>", re.I)
CONTENT_ATTR_RE = re.compile(r"content\s*=\s*[\"']([^\"']*)[\"']", re.I)
USER_SCALABLE_RE = re.compile(r"user-scalable\s*=\s*(no|0)", re.I)
MAXIMUM_SCALE_RE = re.compile(r"maximum-scale\s*=\s*(\d+(?:\.\d+)?)", re.I)

HOVER_RULE_RE = re.compile(r"([^{}]*:hover[^{}]*)\{([^{}]*)\}", re.I)
# Eine Hover-Regel ist nur dann ein Verstoß, wenn sie Sichtbarkeit oder Position
# ändert. Reine Hover-Stile (Farbe, Schatten, Rahmen) sind ausdrücklich keiner —
# ein Check, der jeden :hover meldet, ist die Fehlalarm-Maschine aus gate.py.
REVEALING_PROPS = ("display", "visibility", "opacity", "transform", "pointer-events", "max-height")
TOUCH_EQUIVALENT_RE = re.compile(r":focus-within|:focus-visible|:focus\b|\[aria-expanded|\.is-open|\[data-open", re.I)
HOVER_MEDIA_RE = re.compile(r"@media[^{]*\(\s*hover\s*:\s*hover\s*\)", re.I)
FIX_HINT = {
    "viewport-units": "`100vh` durch `100dvh`/`100svh` ersetzen — die statische Einheit rechnet die "
                      "ein- und ausfahrende Browserleiste nicht mit (references/fixes.md#viewport-units)",
    "input-font-size": "Eingabefelder auf mindestens 16px setzen, sonst zoomt iOS beim Fokus in das Feld "
                       "hinein und die Seite bleibt verschoben (references/fixes.md#input-font-size)",
    "zoom-lock": "`user-scalable=no`/`maximum-scale=1` aus dem Viewport-Meta entfernen — Zoom zu sperren "
                 "ist ein Zugänglichkeitsdefekt, kein Layout-Werkzeug (references/fixes.md#zoom-lock)",
    "hover-only": "Touch-Pfad ergänzen: dieselbe Sichtbarkeit über `:focus-within`, `[aria-expanded]` oder "
                  "einen expliziten Tap, oder die Hover-Regel in `@media (hover: hover)` kapseln "
                  "(references/fixes.md#hover-only)",
}


class AuditError(RuntimeError):
    """Der Lauf konnte nicht durchgeführt werden — kein Befund, sondern ein Abbruch."""


# --- Konfiguration ---------------------------------------------------------------


def load_config(repo: Path) -> dict:
    """Mitgeliefertes Preset, projektüberschrieben nach Spec 00 §1 unter `.skills/<skill>/`."""
    if not DEFAULT_CONFIG_PATH.is_file():
        raise AuditError(f"Preset fehlt: {DEFAULT_CONFIG_PATH}")
    config = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    config.pop("_meta", None)

    override = Path(repo) / PROJECT_OVERRIDE_PATH
    if override.is_file():
        # Flach überschreiben: nicht genannte Schlüssel behalten den Preset-Wert,
        # damit ein Projekt einen Grenzwert anheben kann, ohne alle zu wiederholen.
        config.update({k: v for k, v in json.loads(override.read_text(encoding="utf-8")).items()
                       if k != "_meta"})
    return config


# --- Einzel-Checks ---------------------------------------------------------------


def _finding(check: str, path: str, line: int, measured: str, threshold: str, detail: str) -> dict:
    return {
        "check": check,
        "file": path,
        "line": line,
        "measured": measured,
        "threshold": threshold,
        "detail": detail,
        "evidence": "gemessen",
        "fix": FIX_HINT[check],
    }


def check_viewport_units(text: str, relpath: str) -> list[dict]:
    out = []
    for number, line in _matches(VIEWPORT_UNIT_RE, text):
        out.append(_finding("viewport-units", relpath, line, f"{number}vh", "dvh/svh",
                            "statische Viewport-Einheit ignoriert die mobile Browserleiste"))
    return out


def check_input_font_size(text: str, relpath: str, minimum: int) -> list[dict]:
    """Nur Regeln, deren Selektor ein Eingabeelement trifft — eine kleine Bildunterschrift
    ist kein Mobile-Defekt und gehört nicht in diesen Bericht."""
    out = []
    for selector, body, start_line in _rules(text):
        if not INPUT_SELECTOR_RE.search(selector):
            continue
        for match in FONT_SIZE_RE.finditer(body):
            size = float(match.group(1))
            if size < minimum:
                line = start_line + body[: match.start()].count("\n")
                out.append(_finding("input-font-size", relpath, line, f"{match.group(1)}px",
                                    f"{minimum}px", f"iOS zoomt beim Fokus in Felder unter {minimum}px"))
    return out


def check_zoom_lock(text: str, relpath: str) -> list[dict]:
    out = []
    for match in VIEWPORT_META_RE.finditer(text):
        content_match = CONTENT_ATTR_RE.search(match.group(0))
        if not content_match:
            continue
        content = content_match.group(1)
        line = text[: match.start()].count("\n") + 1
        if USER_SCALABLE_RE.search(content):
            out.append(_finding("zoom-lock", relpath, line, "user-scalable=no", "kein Zoom-Verbot",
                                "Zoom ist gesperrt"))
            continue
        scale = MAXIMUM_SCALE_RE.search(content)
        if scale and float(scale.group(1)) <= 1:
            out.append(_finding("zoom-lock", relpath, line, f"maximum-scale={scale.group(1)}",
                                "kein Zoom-Verbot", "Zoom ist auf Ausgangsgröße begrenzt"))
    return out


def check_hover_only(text: str, relpath: str) -> list[dict]:
    """Enge Verstoßdefinition aus Spec 15.

    JS-Listener (`mouseenter`) sind aus dem Quelltext nicht zuverlässig zu erkennen und
    aus der laufenden Seite nicht enumerierbar — `getEventListeners` ist DevTools-Konsole,
    nicht Playwright. Dieser Check rät deshalb nicht: Er sieht CSS, und was er nicht sieht,
    steht als bekannte Grenze in docs/known-limits.md.
    """
    out = []
    guarded_spans = [m.span() for m in HOVER_MEDIA_RE.finditer(text)]
    for match in HOVER_RULE_RE.finditer(text):
        selector, body = match.group(1).strip(), match.group(2)
        if not any(f"{prop}:" in body.replace(" ", "") for prop in REVEALING_PROPS):
            continue
        if _within_hover_media(match.start(), guarded_spans, text):
            continue
        if _has_touch_equivalent(selector, text):
            continue
        # Ab dem ersten Zeichen des Selektors zählen, nicht ab match.start(): Der
        # Selektor-Teil des Musters beginnt direkt hinter der vorigen `}` und damit
        # noch auf deren Zeile — der Befund zeigte sonst eine Zeile zu früh.
        raw = match.group(1)
        selector_start = match.start(1) + (len(raw) - len(raw.lstrip()))
        line = text[:selector_start].count("\n") + 1
        out.append(_finding("hover-only", relpath, line, selector[:60], "Touch-Pfad vorhanden",
                            "Sichtbarkeit hängt allein an :hover — auf Touch gibt es kein Hover"))
    return out


# --- Hilfsfunktionen -------------------------------------------------------------


def _matches(pattern: re.Pattern, text: str):
    for match in pattern.finditer(text):
        yield match.group(1), text[: match.start()].count("\n") + 1


def _rules(text: str):
    """(Selektor, Rumpf, Startzeile) je CSS-Regel — grob, aber ohne CSS-Parser auskommend."""
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", text):
        yield match.group(1).strip(), match.group(2), text[: match.start(2)].count("\n") + 1


def _within_hover_media(position: int, spans: list[tuple[int, int]], text: str) -> bool:
    """Steht die Regel innerhalb eines `@media (hover: hover)`-Blocks?

    Klammern werden ab dem Medienblock gezählt statt geschachtelt geparst — für die
    flache Verschachtelung, die in echtem CSS vorkommt, reicht das.
    """
    for start, _ in spans:
        if position < start:
            continue
        depth = 0
        for index in range(start, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    if start < position < index:
                        return True
                    break
    return False


def _has_touch_equivalent(selector: str, text: str) -> bool:
    """Gibt es für dasselbe Ziel eine Focus-/Zustands-Regel? Verglichen wird der
    Selektor ohne seinen `:hover`-Teil — `.menu:hover .submenu` und
    `.menu:focus-within .submenu` beschreiben dasselbe Ziel."""
    target = selector.split(":hover")[-1].strip()
    for other_selector, body, _ in _rules(text):
        if ":hover" in other_selector.lower() or not TOUCH_EQUIVALENT_RE.search(other_selector):
            continue
        if target and target in other_selector:
            return True
        if not target and body:
            return True
    return False


# --- Lauf ------------------------------------------------------------------------


def iter_source_files(repo: Path, config: dict):
    extensions = tuple(config["scan_extensions"])
    skip = set(config["skip_dirs"])
    for path in sorted(Path(repo).rglob("*")):
        if not path.is_file() or path.suffix.lower() not in extensions:
            continue
        if any(part in skip for part in path.relative_to(repo).parts[:-1]):
            continue
        yield path


def run_static(repo: Path, config: dict) -> list[dict]:
    repo = Path(repo)
    findings: list[dict] = []
    for path in iter_source_files(repo, config):
        relpath = path.relative_to(repo).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        findings += check_viewport_units(text, relpath)
        findings += check_input_font_size(text, relpath, config["input_font_min_px"])
        findings += check_zoom_lock(text, relpath)
        findings += check_hover_only(text, relpath)
    return findings


def build_report(repo: Path, findings: list[dict]) -> dict:
    return {
        "_meta": {
            "skill": "mobile-audit",
            "schema": SCHEMA_VERSION,
            "generated": "python <skill-dir>/scripts/audit_static.py",
        },
        "stage_1": {
            "status": "sauber" if not findings else "Befunde",
            "checks": ["viewport-units", "input-font-size", "zoom-lock", "hover-only"],
            "finding_count": len(findings),
        },
        # Stufe 1 spricht nie für Stufe 2. Overflow, echte Hit-Areas und Safe-Areas
        # entstehen erst im Layout und brauchen die Geräte-Matrix.
        "stage_2": {
            "status": "ungeprüft",
            "reason": "Geräte-Matrix nicht gelaufen — audit_devices.py separat aufrufen",
            "checks": ["horizontal-overflow", "tap-target-size", "safe-area"],
        },
        "findings": findings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="mobile-audit Stufe 1 — Quelltext-Checks ohne Browser")
    parser.add_argument("--repo", type=Path, default=Path("."))
    args = parser.parse_args(argv)

    try:
        config = load_config(args.repo)
        findings = run_static(args.repo, config)
    except AuditError as exc:
        print(f"audit_static: {exc}", file=sys.stderr)
        return 2

    report = build_report(args.repo, findings)
    target = args.repo / CACHE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    for finding in findings:
        print(f"[{finding['check']}] {finding['file']}:{finding['line']} — "
              f"{finding['measured']} (Grenzwert {finding['threshold']})")
    print(f"Stufe 1: {len(findings)} Befund(e). Stufe 2 (Geräte-Matrix): ungeprüft.")
    print(f"-> {CACHE_PATH}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
