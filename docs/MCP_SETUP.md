# Connecting Claude / Cursor to your framework (MCP)

Your framework is now an **MCP server** with 5 tools. Any MCP-capable AI
client can call them like a colleague with terminal access.

## The 5 exposed tools

| Tool | What the AI can ask for |
|---|---|
| `run_tests(scope)` | run smoke / unit / eval / all — returns PASS/FAIL + pytest tail |
| `heal_report()` | heal rate, calls, tokens, per-attempt evidence |
| `registry_status()` | every locator: original / healed / history |
| `rollback_locator(key)` | undo one healed selector |
| `run_heal_demo(keep)` | the break-and-heal demo on demand |

Smoke-proof (no client needed): `python scripts/mcp_smoke.py`
→ performs the raw JSON-RPC handshake + real tool calls.

## Claude Desktop

File: `%APPDATA%\Claude\claude_desktop_config.json` (Windows)

```json
{
  "mcpServers": {
    "self-healing-qa": {
      "command": "C:\\Users\\panka\\AppData\\Local\\Programs\\Python\\Python312\\python.exe",
      "args": ["-m", "src.mcp_server.server"],
      "cwd": "\\\\wsl.localhost\\Ubuntu\\home\\pankaj\\self_healing_qa_framework",
      "env": { "LLM_PROVIDER": "mock" }
    }
  }
}
```

Restart Claude Desktop → hammer icon → the 5 tools appear.
Now you can literally prompt: *"Run the smoke tests and tell me the heal
report"* → Claude calls both tools and narrates the results.

## Cursor

`.cursor/mcp.json` in the repo:

```json
{
  "mcpServers": {
    "self-healing-qa": {
      "command": "C:\\Users\\panka\\AppData\\Local\\Programs\\Python\\Python312\\python.exe",
      "args": ["-m", "src.mcp_server.server"],
      "cwd": "\\\\wsl.localhost\\Ubuntu\\home\\pankaj\\self_healing_qa_framework",
      "env": { "LLM_PROVIDER": "mock" }
    }
  }
}
```

Then in Cursor composer: tools appear under MCP — call them inline.

## Claude Code (CLI)

```bash
claude mcp add self-healing-qa -- python -m src.mcp_server.server
```

(run from the project root so `cwd` is right; envs via `--`-prefix commands.)

## Notes

- `python -m src.mcp_server.server` must run from the project root (imports `src.*`).
- Read-only tools are safe; `rollback_locator` mutates `bootstrap.json`
  (undo-able via `history`), `run_heal_demo` restores it by default (keep=False).
- `LLM_PROVIDER=mock` keeps assistant-triggered healing $0 and deterministic;
  set `ollama` per ADR-001 for real local brains.
