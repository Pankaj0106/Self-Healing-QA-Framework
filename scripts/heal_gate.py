"""Heal-rate gate (FR-10): CI fails if healing quality drops.

Rules (fail-fast, cost-aware):
- no heal_metrics.json                        -> pass (no healing needed)
- 0 attempts                                  -> pass (happy path)
- attempts exist but heal_rate below --min    -> FAIL with a human-readable reason

This turns "the AI felt fine" into a measurable release gate.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

METRICS = Path(__file__).resolve().parents[1] / "heal_metrics.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=float, default=0.70, help="minimum required heal_rate")
    args = ap.parse_args()

    if not METRICS.exists():
        print(f"[gate] {METRICS.name} not found -> no healing ran -> pass")
        return 0

    metrics = json.loads(METRICS.read_text(encoding="utf-8"))
    totals = metrics.get("totals", {})
    attempts = totals.get("attempts", 0)

    if attempts == 0:
        print("[gate] no heal attempts -> pass")
        return 0

    rate = totals.get("heal_rate")
    healed, unhealable = totals.get("healed", 0), totals.get("unhealable", 0)
    print(f"[gate] attempts={attempts} healed={healed} unhealable={unhealable} "
          f"rate={rate} min={args.min}")

    if rate is None:
        print("[gate] heal_rate unknown despite attempts -> FAIL")
        return 1
    if rate < args.min:
        print(f"[gate] heal_rate {rate} < required {args.min} -> FAIL "
              "(locators drifting badly; check heal_metrics.json)")
        return 1

    print("[gate] heal_rate OK -> pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
