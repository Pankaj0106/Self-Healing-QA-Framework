"""Break-and-heal demo (Step 4).

Simulates a site redesign: overwrites two locators with selectors that don't
exist ("#broken-..."), runs the two affected smoke tests, and lets the
self-healing pipeline repair them live. The registry is restored afterward;
heal_metrics.json keeps the evidence.

Usage:
    python scripts/demo_heal.py            # heal, report, restore
    python scripts/demo_heal.py --keep     # keep the healed registry for inspection
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "locators" / "registry" / "bootstrap.json"
BACKUP = ROOT / "locators" / "registry" / ".demo_backup.json"
METRICS = ROOT / "heal_metrics.json"

# simulation of "the site changed these two elements"
BREAKS = {
    "login_submit": "#broken-login-button",
    "search_button": "#broken-search-button",
}
TESTS = [
    "tests/ui/test_smoke.py::test_login_invalid_password_shows_error",
    "tests/ui/test_smoke.py::test_product_search_returns_results",
]


def break_registry() -> None:
    shutil.copy(REGISTRY, BACKUP)
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    for key, broken in BREAKS.items():
        data[key]["primary"] = broken
        data[key]["healed"] = None
        data[key]["history"] = []
    REGISTRY.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print("\n[BREAK] simulating a site redesign:")
    for key, broken in BREAKS.items():
        print(f"        {key:20s} -> {broken}")


def restore_registry() -> None:
    shutil.copy(BACKUP, REGISTRY)
    BACKUP.unlink()
    print("\n[RESTORE] bootstrap.json restored to original (evidence kept in heal_metrics.json)")


def run_tests() -> int:
    env = {**os.environ, "LLM_PROVIDER": "mock"}
    cmd = [sys.executable, "-m", "pytest", *TESTS, "-q", "--no-header", "-p", "no:cacheprovider"]
    print("\n[RUN]    ", " ".join(cmd[3:]))
    return subprocess.run(cmd, cwd=ROOT, env=env).returncode


def report() -> None:
    metrics = json.loads(METRICS.read_text(encoding="utf-8"))
    t = metrics["totals"]
    print("\n" + "=" * 76)
    print("HEAL REPORT")
    print("=" * 76)
    hdr = f"{'element':22s} {'outcome':16s} {'new selector':34s} conf"
    print(hdr)
    print("-" * 76)
    for a in metrics["attempts"]:
        print(f"{a['locator_key']:22s} {a['outcome']:16s} {a['chosen_selector'] or '-':34s} {a['confidence']:.2f}")
    print("-" * 76)
    print(f"attempts={t['attempts']}  healed={t['healed']}  unhealable={t['unhealable']}  "
          f"llm_calls={t['llm_calls']}  tokens={t['tokens']}  provider={t['model']}")
    print(f"HEAL RATE: {t['heal_rate'] if t['heal_rate'] is not None else 'n/a'}")


def main() -> int:
    keep = "--keep" in sys.argv
    break_registry()
    code = run_tests()
    report()
    if not keep:
        restore_registry()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
