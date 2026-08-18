#!/usr/bin/env python3
"""Verifikations-Harness für motion-landing. Tier 3: Playwright + Node/Lighthouse.

Baut die Regel aus Spec 00 §3 nach: ein übersprungenes Gate wird nie
stillschweigend übersprungen. Fehlt die Toolchain, trägt das Ergebnis sichtbar
„ungeprüft (Playwright/Lighthouse nicht verfügbar)" und die Budgets aus
SKILL.md werden als Checkliste abgearbeitet — genau das prüft Eval 4.

Architektur: Die reine Logik (Szenen-Grenzen, Budget-Auswertung aus einem
gelesenen Lighthouse-JSON, Toolchain-Erkennung, Degradations-Meldung) ist von
der Playwright-/Lighthouse-Ansteuerung getrennt und ohne Browser testbar. Nur
die Funktionen `run_playwright_capture` und `run_lighthouse` importieren die
Fremd-Toolchain, und zwar lokal in der Funktion — das Modul bleibt auch ohne
installiertes Playwright importierbar und testbar.

In der Entwicklungsumgebung, in der dieses Skript entstanden ist, sind
Playwright und Lighthouse nicht installiert. Der Erfolgspfad
(`run_playwright_capture`, `run_lighthouse`, und der Teil von `main()`, der sie
aufruft) ist deshalb ungetestet geblieben — siehe docs/known-limits.md. Nur der
Degradationszweig wurde real geprüft, weil genau diese Toolchain hier fehlt.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

SCHEMA_VERSION = 1

# Budgets aus SKILL.md — der Contract, den dieses Skript durchsetzt (G2:
# meldet Verstoß, der Aufruf selbst bleibt freiwillig; siehe Spec 00 §4).
BUDGET_LCP_MS = 2500
BUDGET_CLS = 0.1
BUDGET_INP_MS = 200

# Die volle Checkliste aus SKILL.md — nicht nur die drei Zahlen-Budgets.
# degradation_report() arbeitet genau diese Liste ab, damit kein Punkt still
# unter den Tisch fällt, wenn die Toolchain fehlt.
CONTRACT_CHECKLIST = (
    "LCP < 2.5s",
    "CLS < 0.1",
    "INP < 200ms",
    "nur transform/opacity animiert",
    "Inhalte ohne JS lesbar",
    "reduced-motion-Zustand je Szene definiert",
)


class SceneError(ValueError):
    """Szenenliste verletzt den Storyboard-Contract oder ist geometrisch ungültig."""


# ---------------------------------------------------------------------------
# Szenen und Storyboard-Contract
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Scene:
    name: str
    type: str
    height_px: int
    highlight: bool = False


@dataclass(frozen=True)
class SceneBoundary:
    name: str
    start_px: int
    end_px: int
    start_pct: float
    end_pct: float


def validate_single_highlight(scenes: Sequence[Scene]) -> None:
    """Storyboard-Contract aus SKILL.md: genau ein Höhepunkt pro Seite."""
    if not scenes:
        raise SceneError("Szenenliste ist leer")
    highlighted = [s.name for s in scenes if s.highlight]
    if len(highlighted) != 1:
        raise SceneError(
            f"Storyboard-Contract verlangt genau einen Höhepunkt, gefunden: "
            f"{len(highlighted)} ({', '.join(highlighted) or 'keiner'})"
        )


def compute_scene_boundaries(scenes: Sequence[Scene]) -> tuple[SceneBoundary, ...]:
    """Pixel- und Prozent-Scrollgrenzen je Szene — die Ziele für Screenshots.

    Setzt den Storyboard-Contract voraus (validate_single_highlight): eine
    Szenenliste ohne genau einen Höhepunkt wird gar nicht erst vermessen.
    """
    validate_single_highlight(scenes)
    for s in scenes:
        if s.height_px <= 0:
            raise SceneError(f"Szene {s.name!r}: height_px muss positiv sein, war {s.height_px}")

    total = sum(s.height_px for s in scenes)
    boundaries: list[SceneBoundary] = []
    cursor = 0
    for s in scenes:
        start, end = cursor, cursor + s.height_px
        boundaries.append(SceneBoundary(
            name=s.name,
            start_px=start,
            end_px=end,
            start_pct=round(start / total * 100, 2),
            end_pct=round(end / total * 100, 2),
        ))
        cursor = end
    return tuple(boundaries)


def load_scenes(path: Path) -> tuple[Scene, ...]:
    """Lädt eine scenes.json: {"scenes": [{"name", "type", "height_px", "highlight"?}, ...]}."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    raw_scenes = payload.get("scenes") if isinstance(payload, dict) else None
    if not isinstance(raw_scenes, list):
        raise SceneError(f"{path}: erwartet ein Objekt mit der Liste 'scenes'")

    scenes: list[Scene] = []
    for index, raw in enumerate(raw_scenes):
        where = f"scenes[{index}]"
        if not isinstance(raw, dict):
            raise SceneError(f"{where}: muss ein Objekt sein")
        name = raw.get("name")
        if not isinstance(name, str) or not name:
            raise SceneError(f"{where}: 'name' fehlt oder ist leer")
        scene_type = raw.get("type")
        if not isinstance(scene_type, str) or not scene_type:
            raise SceneError(f"{where}: 'type' fehlt oder ist leer")
        height_px = raw.get("height_px")
        if not isinstance(height_px, int) or isinstance(height_px, bool) or height_px <= 0:
            raise SceneError(f"{where}: 'height_px' muss eine positive Ganzzahl sein, war {height_px!r}")
        scenes.append(Scene(name=name, type=scene_type, height_px=height_px, highlight=bool(raw.get("highlight", False))))
    return tuple(scenes)


# ---------------------------------------------------------------------------
# Toolchain-Erkennung — Sichtbarkeits-Regel aus Spec 00 §3
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ToolchainStatus:
    playwright_available: bool
    node_available: bool
    lighthouse_available: bool
    details: tuple[str, ...] = field(default_factory=tuple)

    @property
    def fully_available(self) -> bool:
        return self.playwright_available and self.node_available and self.lighthouse_available


def detect_toolchain(
    *,
    find_spec: Callable[[str], object | None] = importlib.util.find_spec,
    which: Callable[[str], str | None] = shutil.which,
) -> ToolchainStatus:
    """Prüft die Tier-3-Abhängigkeiten, ohne sie zu benutzen.

    `find_spec`/`which` sind injizierbar, damit die Erkennung ohne echte
    Systemabfrage testbar ist; `main()` ruft mit den Stdlib-Defaults auf.
    """
    playwright_available = find_spec("playwright") is not None
    node_available = which("node") is not None
    lighthouse_available = which("lighthouse") is not None

    details: list[str] = []
    if not playwright_available:
        details.append("playwright (Python-Paket) fehlt")
    if not node_available:
        details.append("node fehlt")
    if not lighthouse_available:
        details.append("lighthouse (CLI) fehlt")

    return ToolchainStatus(playwright_available, node_available, lighthouse_available, tuple(details))


def degradation_report(status: ToolchainStatus) -> dict:
    """Der Degradations-Befund: sichtbar 'ungeprüft', jeder Contract-Punkt als
    eigener Checklisten-Eintrag — nie ein stillschweigend übersprungenes Gate."""
    message = (
        "ungeprüft (Playwright/Lighthouse nicht verfügbar): " + ", ".join(status.details)
    )
    return {
        "status": "ungeprüft",
        "message": message,
        "missing_tools": list(status.details),
        "budgets_checklist": [
            {"metric": metric, "status": "ungeprüft (Werkzeug fehlt)"} for metric in CONTRACT_CHECKLIST
        ],
    }


# ---------------------------------------------------------------------------
# Budget-Auswertung aus einem eingelesenen Lighthouse-JSON
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BudgetCheck:
    metric: str
    value: float | None
    threshold: float
    status: str  # "pass" | "fail" | "missing"
    note: str = ""


@dataclass(frozen=True)
class BudgetReport:
    checks: tuple[BudgetCheck, ...]

    @property
    def all_pass(self) -> bool:
        return all(c.status == "pass" for c in self.checks)


def _audit_numeric(audits: dict, audit_id: str) -> float | None:
    audit = audits.get(audit_id)
    if not isinstance(audit, dict):
        return None
    value = audit.get("numericValue")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _budget_status(value: float | None, threshold: float) -> str:
    if value is None:
        return "missing"
    return "pass" if value < threshold else "fail"


def evaluate_budgets(lighthouse_result: dict) -> BudgetReport:
    """Liest ein Lighthouse-Ergebnis (dict, wie `lighthouse --output json`
    liefert) und vergleicht LCP/CLS/INP gegen die Budgets. Ein fehlendes Audit
    wird als 'missing' gemeldet, nie stillschweigend als 'pass' gewertet.
    """
    audits = lighthouse_result.get("audits", {}) if isinstance(lighthouse_result, dict) else {}
    checks: list[BudgetCheck] = []

    lcp = _audit_numeric(audits, "largest-contentful-paint")
    checks.append(BudgetCheck("LCP", lcp, BUDGET_LCP_MS, _budget_status(lcp, BUDGET_LCP_MS)))

    cls = _audit_numeric(audits, "cumulative-layout-shift")
    checks.append(BudgetCheck("CLS", cls, BUDGET_CLS, _budget_status(cls, BUDGET_CLS)))

    inp = _audit_numeric(audits, "interaction-to-next-paint")
    note = ""
    if inp is None:
        tbt = _audit_numeric(audits, "total-blocking-time")
        if tbt is not None:
            inp = tbt
            note = (
                "kein echtes INP-Audit gefunden — Total Blocking Time als "
                "dokumentierter Näherungswert verwendet, nicht gleichwertig "
                "(Lighthouse misst INP ohne echte Interaktion nicht)"
            )
    checks.append(BudgetCheck("INP", inp, BUDGET_INP_MS, _budget_status(inp, BUDGET_INP_MS), note=note))

    return BudgetReport(tuple(checks))


# ---------------------------------------------------------------------------
# Erfolgspfad — braucht Playwright/Node/Lighthouse. UNGETESTET hier.
# ---------------------------------------------------------------------------

def run_playwright_capture(url: str, scenes: Sequence[Scene], out_dir: Path, *, video: bool, reduced_motion: bool) -> dict:
    """Öffnet die Seite headless, scrollt zu jeder Szenen-Grenze
    (`compute_scene_boundaries`) und macht dort einen Screenshot; bei
    `reduced_motion=True` mit `prefers-reduced-motion: reduce` emuliert.
    Video der Gesamtstrecke nur bei `video=True` (Entscheidung aus dem
    Auftrag: Screenshots immer, Video nur auf Anforderung).

    Tier 3. UNGETESTET in dieser Umgebung — Playwright ist hier nicht
    installiert (siehe docs/known-limits.md). Der Import ist absichtlich lokal,
    damit das Modul auch ohne Playwright importierbar bleibt.
    """
    from playwright.sync_api import sync_playwright  # noqa: PLC0415 — bewusst lokal, siehe Docstring

    boundaries = compute_scene_boundaries(scenes)
    screenshots: list[dict] = []
    out_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(reduced_motion="reduce" if reduced_motion else "no-preference")
        page = context.new_page()
        page.goto(url, wait_until="networkidle")

        video_path: str | None = None
        for boundary in boundaries:
            page.evaluate(f"window.scrollTo(0, {boundary.start_px})")
            suffix = "-reduced-motion" if reduced_motion else ""
            shot_path = out_dir / f"{boundary.name}{suffix}.png"
            page.screenshot(path=str(shot_path))
            screenshots.append({"scene": boundary.name, "path": str(shot_path)})

        if video and page.video is not None:
            video_path = page.video.path()

        context.close()
        browser.close()

    return {"screenshots": screenshots, "video": video_path, "reduced_motion": reduced_motion}


def run_lighthouse(url: str, out_path: Path) -> dict:
    """Ruft die Lighthouse-CLI über Node auf und liest das JSON-Ergebnis.

    Tier 3. UNGETESTET in dieser Umgebung — Lighthouse ist hier nicht
    installiert (siehe docs/known-limits.md).
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "lighthouse", url,
        "--output=json", f"--output-path={out_path}",
        "--chrome-flags=--headless=new",
        "--quiet",
    ]
    subprocess.run(cmd, check=True, timeout=180)
    return json.loads(out_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

DEFAULT_OUT = Path(".skills") / "cache" / "motion-landing"


def _write_report(out_dir: Path, report: dict, *, generated_cmd: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "_meta": {"skill": "motion-landing", "schema": SCHEMA_VERSION, "generated": generated_cmd},
        **report,
    }
    target = out_dir / "verify-report.json"
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="motion-landing Verifikations-Harness (Tier 3)")
    parser.add_argument("--scenes", type=Path, required=True, help="Pfad zu einer scenes.json")
    parser.add_argument("--url", help="URL der gebauten Seite (für den Erfolgspfad erforderlich)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Zielverzeichnis für Report/Screenshots")
    parser.add_argument("--video", action="store_true", help="Video der Gesamtstrecke zusätzlich aufnehmen")
    args = parser.parse_args(argv)

    generated_cmd = "python skills/motion-landing/scripts/verify.py --scenes " + str(args.scenes)

    try:
        scenes = load_scenes(args.scenes)
        validate_single_highlight(scenes)
    except SceneError as exc:
        print(f"Storyboard-Contract verletzt: {exc}", file=sys.stderr)
        return 3

    status = detect_toolchain()
    if not status.fully_available:
        report = degradation_report(status)
        target = _write_report(args.out, report, generated_cmd=generated_cmd)
        print(report["message"])
        for item in report["budgets_checklist"]:
            print(f"  - {item['metric']}: {item['status']}")
        print(f"Report -> {target}")
        return 2

    if not args.url:
        print("--url fehlt: der Erfolgspfad braucht die URL der gebauten Seite", file=sys.stderr)
        return 1

    capture = run_playwright_capture(args.url, scenes, args.out, video=args.video, reduced_motion=False)
    reduced_capture = run_playwright_capture(args.url, scenes, args.out, video=False, reduced_motion=True)
    lighthouse_result = run_lighthouse(args.url, args.out / "lighthouse.json")
    budgets = evaluate_budgets(lighthouse_result)

    report = {
        "status": "geprüft",
        "capture": capture,
        "reduced_motion_capture": reduced_capture,
        "budgets": [
            {"metric": c.metric, "value": c.value, "threshold": c.threshold, "status": c.status, "note": c.note}
            for c in budgets.checks
        ],
        "all_budgets_pass": budgets.all_pass,
    }
    target = _write_report(args.out, report, generated_cmd=generated_cmd)
    print(f"Verifiziert -> {target}")
    for c in budgets.checks:
        print(f"  - {c.metric}: {c.status} ({c.value})")
    return 0 if budgets.all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
