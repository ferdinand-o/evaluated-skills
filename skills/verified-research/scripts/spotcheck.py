#!/usr/bin/env python3
"""Verifikations-Pass für verified-research: Stichprobe ziehen (Claim -> Quelle ->
Verifikationsauftrag). Tier 1: nur Stdlib. G2 — dieses Skript fällt das Urteil über
die Stichprobenauswahl, der Aufruf bleibt freiwillig; findet es null Claims im
erwarteten Format, meldet es das statt still 0 zurückzugeben.

Claim-Format, das dieses Skript aus einem Bericht liest (siehe SKILL.md Contract):
eine Markdown-Listenzeile, die auf ein Tag der Form

    [Tier <1-3>, kritisch, Quelle: <adresse>]   (kritisch optional)

endet. Beispiel:

    - Der Marktanteil liegt bei 42 %. [Tier 3, kritisch, Quelle: sources/blog.md]
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import sys
from dataclasses import dataclass
from pathlib import Path

SCHEMA_VERSION = 1
OUT_PATH = Path(".skills") / "cache" / "verified-research-spotcheck.json"

# Benannte Konstanten statt verstreuter Zahlen (R9). Kritische Claims werden zu 100 %
# geprüft (das ist keine Konstante, sondern "alle"); vom Rest wird SPOTCHECK_REST_QUOTA
# gezogen, mindestens aber SPOTCHECK_MIN_SAMPLE Claim insgesamt, falls überhaupt welche
# vorliegen. "Ein Drittel, abgerundet" ergibt für ein oder zwei unkritische Claims 0
# (math.floor(1 * (1/3)) == math.floor(2 * (1/3)) == 0) — ohne SPOTCHECK_MIN_SAMPLE
# würde bei genau ein oder zwei übrig gebliebenen, unkritischen Claims nichts geprüft.
# (Bei genau drei rundet 3 * (1/3) in IEEE-754-double exakt auf 1.0, dort greift die
# Regel nicht — der Grenzfall liegt bei ein/zwei, nicht bei drei Claims.)
SPOTCHECK_REST_QUOTA = 1 / 3
SPOTCHECK_MIN_SAMPLE = 1
SPOTCHECK_SEED = 20260815  # fest, damit dieselbe Eingabe reproduzierbar dieselbe Stichprobe zieht

CLAIM_RE = re.compile(
    r"^[-*]\s+(?P<text>.+?)\s*"
    r"\[Tier\s*(?P<tier>[1-3])\s*(?P<crit>,\s*kritisch)?\s*,\s*Quelle:\s*(?P<source>\S+)\]\s*$",
    re.MULTILINE,
)


class SpotcheckError(RuntimeError):
    """Der Bericht konnte nicht gelesen oder nicht geparst werden."""


@dataclass(frozen=True)
class Claim:
    text: str
    tier: int
    critical: bool
    source: str
    line_no: int


def parse_claims(text: str) -> list[Claim]:
    claims: list[Claim] = []
    for match in CLAIM_RE.finditer(text):
        line_no = text.count("\n", 0, match.start()) + 1
        claims.append(Claim(
            text=match.group("text").strip(),
            tier=int(match.group("tier")),
            critical=bool(match.group("crit")),
            source=match.group("source"),
            line_no=line_no,
        ))
    return claims


def select_sample(claims: list[Claim], *, seed: int = SPOTCHECK_SEED) -> list[Claim]:
    """Kritische Claims zu 100 %, vom Rest SPOTCHECK_REST_QUOTA, mindestens ein Claim
    insgesamt, sofern überhaupt Claims vorliegen (R9)."""
    if not claims:
        return []

    critical = [c for c in claims if c.critical]
    rest = [c for c in claims if not c.critical]

    rest_quota = math.floor(len(rest) * SPOTCHECK_REST_QUOTA)
    rest_quota = min(rest_quota, len(rest))
    chosen_rest = random.Random(seed).sample(rest, rest_quota) if rest_quota > 0 else []

    sample = list(critical) + list(chosen_rest)

    if len(sample) < SPOTCHECK_MIN_SAMPLE:
        # Minimum-Regel: die Rundung darf nicht dazu führen, dass bei vorhandenen
        # Claims gar keiner geprüft wird (siehe Modulkommentar zu SPOTCHECK_REST_QUOTA).
        fallback = rest[0] if rest else claims[0]
        if fallback not in sample:
            sample.append(fallback)

    return sample


def verification_task(claim: Claim) -> str:
    return (
        f"Öffne {claim.source} und prüfe: Steht \"{claim.text}\" dort wirklich, "
        f"in diesem Kontext, mit diesem Wert? Abweichung -> Claim im Bericht als "
        f"'VERWORFEN nach Spotcheck' markieren statt still zu lassen."
    )


def build_report(claims: list[Claim], sample: list[Claim], *, source_report: str) -> dict:
    return {
        "_meta": {
            "skill": "verified-research",
            "schema": SCHEMA_VERSION,
            "generated": f"python skills/verified-research/scripts/spotcheck.py --report {source_report}",
        },
        "source_report": source_report,
        "claims_total": len(claims),
        "critical_total": sum(1 for c in claims if c.critical),
        "sample_size": len(sample),
        "sample": [
            {
                "text": c.text,
                "tier": c.tier,
                "critical": c.critical,
                "source": c.source,
                "line": c.line_no,
                "verification_task": verification_task(c),
            }
            for c in sample
        ],
    }


def write_sample(payload: dict, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Spotcheck-Stichprobe für verified-research ziehen")
    parser.add_argument("--report", required=True, type=Path, help="Pfad zum Recherche-Bericht (Markdown)")
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--seed", type=int, default=SPOTCHECK_SEED)
    args = parser.parse_args(argv)

    report_path = args.repo / args.report if not args.report.is_absolute() else args.report
    if not report_path.is_file():
        print(f"Bericht nicht gefunden: {report_path}", file=sys.stderr)
        return 2

    text = report_path.read_text(encoding="utf-8", errors="replace")
    claims = parse_claims(text)

    if not claims:
        print(
            f"Keine Claims im erwarteten Format ([Tier N, ..., Quelle: ...]) in "
            f"{report_path} gefunden — spotcheck kann nichts prüfen. Das ist kein "
            f"stiller Erfolg, sondern ein Formatproblem im Bericht.",
            file=sys.stderr,
        )
        return 3

    sample = select_sample(claims, seed=args.seed)
    payload = build_report(claims, sample, source_report=str(args.report))

    out_path = args.repo / OUT_PATH
    write_sample(payload, out_path)

    print(f"{len(claims)} Claims gefunden, {len(sample)} in der Stichprobe -> {out_path}")
    for entry in payload["sample"]:
        marker = "kritisch" if entry["critical"] else "Stichprobe"
        print(f"- [{marker}, Tier {entry['tier']}] {entry['text']}")
        print(f"  {entry['verification_task']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
