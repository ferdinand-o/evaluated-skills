#!/usr/bin/env python3
"""mobile-audit Stufe 2: Geräte-Matrix. Tier 3 — Playwright.

Geprüft wird hier, was erst im Layout entsteht und deshalb im Quelltext nicht steht:
horizontales Overflow, echte Hit-Area-Größen, Safe-Area-Verletzungen und die
Tastatur-Geometrie.

**Aufbau, damit die Logik ohne Browser prüfbar bleibt.** `evaluate()` bekommt fertige
Messwerte und gibt Befunde zurück — sie ist reine Rechnung und wird mit synthetischen
Daten getestet. Nur `collect_measurement()` und `run_matrix()` fassen Playwright an.
Das ist das Muster aus `motion-landing/scripts/verify.py`; anders als dort ist der
Erfolgspfad hier real durchgelaufen (siehe tests/test_mobile_audit_devices_e2e.py).

**Der Keyboard-Check ist modelliert, nicht emuliert.** Der Spike zu Spec 15 hat
gemessen, dass `Emulation.setDeviceMetricsOverride` Layout und visuellen Viewport
gemeinsam schrumpft — ein `position: fixed; bottom: 0` wandert dann mit und die
kaputte Seite sähe heil aus — und dass `Emulation.setVisibleSize` folgenlos bleibt.
Stattdessen gilt: Eine Tastatur verdeckt die unteren K Pixel des Geräteprofils.
Gemeldet wird ein Bedienelement, das in einem `fixed`/`sticky` verankerten Vorfahren
liegt und unter diese Linie ragt. Elemente im normalen Fluss bleiben außen vor, weil
der Browser das fokussierte Feld hineinscrollt. K ist ein deklariertes Modell, kein
Messwert — die Befunde heißen deshalb `modelliert`.

G2 nach Spec 00 §4: meldet Verstöße, blockiert nichts.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA_VERSION = 1
SKILL_DIR = Path(__file__).resolve().parent.parent
CACHE_PATH = Path(".skills") / "cache" / "mobile-audit-devices.json"

FIX_HINT = {
    "horizontal-overflow": "Das überbreite Element in einen eigenen Scroll-Container mit "
                           "`overflow-x: auto` legen — nie den Seitenkörper seitwärts scrollen lassen "
                           "(references/fixes.md#horizontal-overflow)",
    "tap-target-size": "Hit-Area über Padding vergrößern, nicht die Glyphe — ein kleines Icon mit "
                       "großzügiger unsichtbarer Trefferfläche ist das richtige Muster "
                       "(references/fixes.md#tap-target-size)",
    "safe-area": "`env(safe-area-inset-*)` in Padding oder Position einrechnen, statt am "
                 "Viewport-Rand zu kleben (references/fixes.md#safe-area)",
    "keyboard-overlay": "Die fixierte Leiste beim Fokus mitführen (VisualViewport) oder in den "
                        "normalen Fluss legen, damit der Browser sie hineinscrollen kann "
                        "(references/fixes.md#keyboard-overlay)",
}

# Ein einziger evaluate-Aufruf je Gerät: Rohdaten rein, Bewertung in Python.
COLLECT_JS = """() => {
    const interactiveSel = 'a[href],button,input,select,textarea,[role=button],[role=link],[onclick]';
    const anchorOf = (el) => {
        let node = el;
        while (node && node !== document.body) {
            const pos = getComputedStyle(node).position;
            if (pos === 'fixed' || pos === 'sticky') return pos;
            node = node.parentElement;
        }
        return null;
    };
    const describe = (el) => {
        if (el.id) return el.tagName.toLowerCase() + '#' + el.id;
        const cls = (el.className && typeof el.className === 'string')
            ? '.' + el.className.trim().split(/\\s+/).slice(0, 2).join('.') : '';
        return el.tagName.toLowerCase() + cls;
    };
    const elements = [...document.querySelectorAll(interactiveSel)].map((el) => {
        const r = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        return {
            selector: describe(el),
            top: Math.round(r.top), bottom: Math.round(r.bottom),
            left: Math.round(r.left), right: Math.round(r.right),
            width: Math.round(r.width), height: Math.round(r.height),
            fixed_ancestor: anchorOf(el),
            visible: r.width > 0 && r.height > 0 && style.visibility !== 'hidden' && style.display !== 'none',
            disabled: !!el.disabled,
        };
    });
    // Nicht window.innerWidth: Chromium schaltet bei is_mobile in Shrink-to-fit und
    // dehnt den Layout-Viewport auf die Breite des ueberbreiten Inhalts (gemessen:
    // innerWidth 700 bei 360px Geraet). Der Vergleich waere dann immer 700 > 700 —
    // der Check waere genau im mobilen Modus blind. visualViewport ist das, was der
    // Mensch sieht.
    const visibleWidth = Math.round(window.visualViewport.width);
    const overflowing = [...document.querySelectorAll('body *')]
        .map((el) => ({el, r: el.getBoundingClientRect()}))
        .filter(({r}) => r.right > visibleWidth + 1 && r.width > 0)
        .slice(0, 10)
        .map(({el, r}) => ({selector: describe(el), right: Math.round(r.right)}));
    return {
        viewport: {width: visibleWidth, height: Math.round(window.visualViewport.height)},
        layout_viewport: {width: window.innerWidth, height: window.innerHeight},
        document_scroll_width: Math.round(document.documentElement.scrollWidth),
        has_input: !!document.querySelector('input, select, textarea'),
        elements, overflowing,
    };
}"""


@dataclass(frozen=True)
class ToolchainStatus:
    playwright_available: bool
    details: tuple[str, ...] = field(default_factory=tuple)


def detect_toolchain(find_spec=importlib.util.find_spec) -> ToolchainStatus:
    """`find_spec` ist injizierbar, damit die Erkennung ohne echte Installation testbar ist."""
    available = find_spec("playwright") is not None
    return ToolchainStatus(available, () if available else ("playwright (Python-Paket) fehlt",))


# --- Bewertung: reine Rechnung, ohne Browser -------------------------------------


def _finding(check, device, selector, measured, threshold, detail, evidence="gemessen") -> dict:
    return {"check": check, "device": device, "selector": selector, "measured": measured,
            "threshold": threshold, "detail": detail, "evidence": evidence, "fix": FIX_HINT[check]}


def evaluate(measurement: dict, config: dict, profile: dict) -> list[dict]:
    device = profile["name"]
    width = measurement["viewport"]["width"]
    height = measurement["viewport"]["height"]
    findings: list[dict] = []

    scroll_width = measurement["document_scroll_width"]
    if scroll_width > width:
        offenders = measurement.get("overflowing") or []
        selector = offenders[0]["selector"] if offenders else "document"
        findings.append(_finding(
            "horizontal-overflow", device, selector, f"{scroll_width}px", f"{width}px",
            "das Dokument ist breiter als der Viewport — die Seite scrollt seitwärts"))

    floor = config["tap_target_min_px"]
    keyboard_line = height - profile["keyboard_px"]
    safe_top, safe_bottom = profile["safe_area_top"], profile["safe_area_bottom"]

    for el in measurement.get("elements") or []:
        if not el["visible"] or el["disabled"]:
            continue

        if el["width"] < floor or el["height"] < floor:
            findings.append(_finding(
                "tap-target-size", device, el["selector"],
                f"{el['width']}×{el['height']}px", f"{floor}×{floor}px",
                "Trefferfläche unter dem Boden aus WCAG 2.2 AA"))

        if el["fixed_ancestor"]:
            if safe_top and el["top"] < safe_top:
                findings.append(_finding(
                    "safe-area", device, el["selector"], f"top={el['top']}px",
                    f"≥ {safe_top}px (safe-area-inset-top)",
                    "fixiertes Bedienelement ragt unter die Notch"))
            elif safe_bottom and el["bottom"] > height - safe_bottom:
                findings.append(_finding(
                    "safe-area", device, el["selector"], f"bottom={el['bottom']}px",
                    f"≤ {height - safe_bottom}px (safe-area-inset-bottom)",
                    "fixiertes Bedienelement liegt im Bereich der Home-Anzeige"))

            if measurement.get("has_input") and el["bottom"] > keyboard_line:
                findings.append(_finding(
                    "keyboard-overlay", device, el["selector"], f"bottom={el['bottom']}px",
                    f"≤ {keyboard_line}px (Viewport {height} − Tastatur {profile['keyboard_px']})",
                    "fixiertes Bedienelement liegt im Bereich, den die Tastatur verdeckt",
                    evidence="modelliert"))

    return findings


def build_report(status: ToolchainStatus, results: list[dict]) -> dict:
    meta = {"_meta": {"skill": "mobile-audit", "schema": SCHEMA_VERSION,
                      "generated": "python <skill-dir>/scripts/audit_devices.py"}}
    if not status.playwright_available:
        return meta | {"stage_2": {
            "status": "ungeprüft",
            "reason": "ungeprüft (Playwright nicht verfügbar): " + ", ".join(status.details),
            "missing_tools": list(status.details),
            "devices": [],
            "checks": ["horizontal-overflow", "tap-target-size", "safe-area", "keyboard-overlay"],
        }}
    return meta | {"stage_2": {
        "status": "geprüft",
        "devices": [r["device"] for r in results],
        "finding_count": sum(len(r["findings"]) for r in results),
        "findings": [f for r in results for f in r["findings"]],
    }}


# --- Erfolgspfad: fasst Playwright an --------------------------------------------


def collect_measurement(page, profile: dict) -> dict:
    return page.evaluate(COLLECT_JS)


def run_matrix(url: str, config: dict) -> list[dict]:
    from playwright.sync_api import sync_playwright  # noqa: PLC0415 — bewusst lokal

    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            for profile in config["devices"]:
                ctx = browser.new_context(
                    viewport={"width": profile["width"], "height": profile["height"]},
                    device_scale_factor=profile["device_scale_factor"],
                    is_mobile=True, has_touch=True)
                page = ctx.new_page()
                page.goto(url, wait_until="load")
                measurement = collect_measurement(page, profile)
                results.append({"device": profile["name"],
                                "findings": evaluate(measurement, config, profile)})
                ctx.close()
        finally:
            browser.close()
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="mobile-audit Stufe 2 — Geräte-Matrix")
    parser.add_argument("--url", required=True, help="URL oder file:// der zu prüfenden Seite")
    parser.add_argument("--repo", type=Path, default=Path("."))
    args = parser.parse_args(argv)

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from audit_static import load_config  # noqa: PLC0415 — teilt sich das Preset mit Stufe 1

    config = load_config(args.repo)
    status = detect_toolchain()
    results = run_matrix(args.url, config) if status.playwright_available else []
    report = build_report(status, results)

    target = args.repo / CACHE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if not status.playwright_available:
        print(report["stage_2"]["reason"])
        print(f"-> {CACHE_PATH}")
        return 0

    for finding in report["stage_2"]["findings"]:
        print(f"[{finding['check']}] {finding['device']} {finding['selector']} — "
              f"{finding['measured']} (Grenzwert {finding['threshold']}, {finding['evidence']})")
    print(f"Stufe 2: {report['stage_2']['finding_count']} Befund(e) über "
          f"{len(report['stage_2']['devices'])} Geräte.")
    print(f"-> {CACHE_PATH}")
    return 1 if report["stage_2"]["finding_count"] else 0


if __name__ == "__main__":
    sys.exit(main())
