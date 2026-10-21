# Locator Registry

- `bootstrap.json` — one LocatorEntry per element we interact with.
- Loaded by `src/locators/registry.py`.

```json
{
  "login_btn": {
    "primary": "text=Login",
    "strategy": "text",
    "intent": "Login button",
    "healed": null,
    "history": []
  }
}
```

- `primary` — selector Playwright tries first.
- `strategy` — css | text | xpath | role (Playwright engines).
- `healed` — set when LLM resolver replaces `primary`.
- `history` — audit trail of past selectors (rollback possible).
