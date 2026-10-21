"""MCP (Model Context Protocol) server for the self-healing QA framework.

What this buys you: Claude Desktop / Cursor can now CALL the framework as
tools instead of you copy-pasting terminal output:

    run_tests("smoke")      -> green/red + last lines of pytest
    heal_report()           -> heal rate, spend, per-attempt table
    registry_status()       -> which locators are original/healed/rolled back
    rollback_locator("k")   -> restore the original selector for one element
    run_heal_demo(keep)     -> the break-and-heal demo, on demand

Run (one-time setup):
    python -m pip install -e ".[mcp]"
    python -m src.mcp_server.server        # sessions on stdio

Register in an AI client (Claude Desktop / Cursor) — see docs/MCP_SETUP.md.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

ROOT = Path(__file__).resolve().parents[2]
METRICS = ROOT / "heal_metrics.json"
REGISTRY_JSON = ROOT / "locators" / "registry" / "bootstrap.json"

SCOPES: dict[str, list[str]] = {
    "smoke": ["tests/ui", "-m", "smoke"],
    "unit": ["tests/unit"],
    "eval": ["tests/eval"],
    "all": ["tests"],
}

mcp = FastMCP("self-healing-qa")


@mcp.tool()
def run_tests(scope: str = "smoke") -> str:
    """Run the framework's pytest suite.

    scope: 'smoke' (fast UI, ~20s) | 'unit' (offline brain checks, ~3s) |
    'eval' (offline heal benchmark, ~30s) | 'all'.
    Returns exit code + the last lines of pytest output.
    """
    args = SCOPES.get(scope.lower())
    if args is None:
        return f"unknown scope {scope!r} — use smoke | unit | eval | all"

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", *args, "-q", "--no-header",
             "-p", "no:cacheprovider"],
            cwd=ROOT, capture_output=True, text=True, timeout=900,
        )
    except subprocess.TimeoutExpired:
        return "timeout after 15 min — suite gave up; check for hangs"

    tail = [ln for ln in (proc.stdout or "").strip().splitlines()][-12:]
    summary = "\n".join(tail or ["(no pytest output)"])
    verdict = "PASS" if proc.returncode == 0 else "FAIL"
    return f"run_tests({scope!r}) -> {verdict} (exit={proc.returncode})\n{summary}"


@mcp.tool()
def heal_report() -> str:
    """Read heal_metrics.json: heal rate, LLM calls, tokens, per-attempt log."""
    if not METRICS.exists():
        return "no heal_metrics.json yet — healing hasn't run in this workspace"

    d = json.loads(METRICS.read_text(encoding="utf-8"))
    t = d.get("totals", {})
    lines = [
        f"model/provider : {t.get('model')}",
        f"attempts total : {t.get('attempts')}",
        f"healed         : {t.get('healed')}",
        f"unhealable     : {t.get('unhealable')}",
        f"budget skips   : {t.get('budget_skips')}",
        f"cache hits     : {t.get('cache_hits')}",
        f"llm calls used : {t.get('llm_calls')} (budget capped per run)",
        f"tokens billed  : {t.get('tokens')}",
        f"heal rate      : {t.get('heal_rate')}",
        "",
        "per-attempt:",
    ]
    for a in d.get("attempts", []):
        lines.append(
            f"  {a['locator_key']:24s} {a['outcome']:16s} "
            f"{a['chosen_selector'] or '-':36s} conf={a['confidence']}"
        )
    return "\n".join(lines)


@mcp.tool()
def registry_status() -> str:
    """Dump locator registry: original selector vs healed, with history counts."""
    if not REGISTRY_JSON.exists():
        return "registry file missing"

    data = json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
    lines = [f"{len(data)} locators in bootstrap.json:"]
    for key, entry in data.items():
        healed = entry.get("healed")
        state = f"HEALED -> {healed}" if healed else "original"
        history = entry.get("history") or []
        lines.append(
            f"  {key:24s} {state}\n"
            f"    primary: {entry.get('primary')}   history entries: {len(history)}"
        )
    return "\n".join(lines)


@mcp.tool()
def rollback_locator(key: str) -> str:
    """Restore the ORIGINAL selector for one registry key (undo a heal)."""
    from src.locators.registry import LocatorRegistry

    if key not in LocatorRegistry().keys():
        entries = ", ".join(LocatorRegistry().keys())
        return f"unknown key {key!r} — valid keys: {entries}"
    LocatorRegistry().rollback(key)
    return f"rolled back {key!r}: healed value removed, original restored."


@mcp.tool()
def run_heal_demo(keep: bool = False) -> str:
    """Break 2 locators on purpose and watch the framework self-heal.

    keep=True leaves the healed registry on disk for inspection;
    default restores the original registry and keeps the metrics evidence.
    """
    cmd = [sys.executable, str(ROOT / "scripts" / "demo_heal.py")]
    if keep:
        cmd.append("--keep")
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=900)
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    tail = out.splitlines()[-20:]
    return f"exit={proc.returncode}\n" + "\n".join(tail)


if __name__ == "__main__":
    mcp.run()   # stdio transport: one JSON-RPC session on stdin/stdout
