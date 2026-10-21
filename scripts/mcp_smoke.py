"""End-to-end MCP smoke test WITHOUT any AI client installed.

Speaks raw newline-delimited JSON-RPC over the server's stdio, exactly like
the MCP spec, to prove the server grades 'works outside the editor':
  1. initialize   -> protocol handshake
  2. tools/list   -> the 5 tools are exposed with descriptions
  3. tools/call   -> heal_report + registry_status actually execute

Run:  python scripts/mcp_smoke.py     (needs: pip install -e ".[mcp]")
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def send(proc, payload: dict) -> None:
    proc.stdin.write(json.dumps(payload) + "\n")
    proc.stdin.flush()


def recv(proc) -> dict:
    line = proc.stdout.readline()
    if not line:
        raise RuntimeError("server closed the stream (crash?)")
    return json.loads(line)


def main() -> int:
    proc = subprocess.Popen(
        [sys.executable, "-m", "src.mcp_server.server"],
        cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        text=True, encoding="utf-8",
    )
    try:
        # 1) initialize
        send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "smoke-test", "version": "0.1"},
        }})
        init = recv(proc)
        version = init["result"]["protocolVersion"]
        print(f"[1] initialize OK  protocol={version}")

        # 2) notifications/initialized + tools/list
        send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = recv(proc)
        names = [t["name"] for t in tools["result"]["tools"]]
        print(f"[2] tools/list OK  -> {names}")
        assert set(names) == {
            "run_tests", "heal_report", "registry_status",
            "rollback_locator", "run_heal_demo",
        }, f"tool set drifted: {names}"

        # 3) actually call two read-only tools
        send(proc, {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
            "name": "heal_report", "arguments": {}}})
        rep = recv(proc)
        text = rep["result"]["content"][0]["text"]
        print(f"[3] heal_report OK -> {text.splitlines()[0] if text else '(empty)'}")

        send(proc, {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {
            "name": "registry_status", "arguments": {}}})
        reg = recv(proc)
        text = reg["result"]["content"][0]["text"]
        print(f"[4] registry_status OK -> {text.splitlines()[0]}")

        print("\nMCP SMOKE: ALL GREEN — server is spec-compliant and functional")
        return 0
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        proc.terminate()
        proc.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
