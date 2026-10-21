"""Locator registry: reads/writes selector JSON files.

Why JSON, not code? When the site changes a button id, the healer updates
one JSON entry instead of editing test source code.
"""
from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path

from src.core.logger import logger

REGISTRY_DIR = Path(__file__).resolve().parents[2] / "locators" / "registry"


@dataclass
class LocatorEntry:
    key: str
    primary: str
    strategy: str
    intent: str
    healed: str | None = None
    history: list[str] = field(default_factory=list)

    @property
    def active(self) -> str:
        """Current selector to use (healed wins over original)."""
        return self.healed or self.primary


class LocatorRegistry:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or REGISTRY_DIR / "bootstrap.json"
        self._entries: dict[str, LocatorEntry] = {}
        self._load()

    def _load(self) -> None:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        for key, val in raw.items():
            self._entries[key] = LocatorEntry(
                key=key,
                primary=val["primary"],
                strategy=val["strategy"],
                intent=val.get("intent", key),
                healed=val.get("healed"),
                history=val.get("history", []),
            )

    def get(self, key: str) -> LocatorEntry:
        try:
            return self._entries[key]
        except KeyError:
            raise KeyError(f"Locator '{key}' not in {self.path}") from None

    def keys(self) -> list[str]:
        return list(self._entries)

    def apply_heal(self, key: str, new_selector: str) -> None:
        """Promote healed selector, keep original in history for rollback."""
        entry = self.get(key)
        if entry.healed:            # already healed -> push old one to history
            entry.history.append(entry.healed)
        entry.healed = new_selector
        logger.info(f"HEAL persisted | {key}: {entry.primary!r} -> {new_selector!r}")
        self._save()

    def rollback(self, key: str) -> None:
        entry = self.get(key)
        if entry.healed:
            entry.history.append(entry.healed)
            entry.healed = None
            self._save()

    def _save(self) -> None:
        data: dict[str, dict] = {}
        for key, e in self._entries.items():
            data[key] = {
                "primary": e.primary,
                "strategy": e.strategy,
                "intent": e.intent,
                "healed": e.healed,
                "history": e.history,
            }
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def export(self) -> dict:
        """Snapshot of state (used by heal_metrics.json)."""
        return {
            k: {"active": e.active, "healed": e.healed, "history": e.history}
            for k, e in self._entries.items()
        }


_registry: LocatorRegistry | None = None


def get_registry() -> LocatorRegistry:
    """Singleton: one registry instance per test process."""
    global _registry
    if _registry is None:
        _registry = LocatorRegistry()
    return _registry
