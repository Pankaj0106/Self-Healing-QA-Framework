"""Config loader: YAML + env overrides. No secrets in git."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    base_url: str
    browser: str
    headless: bool
    timeout_ms: int
    heal_enabled: bool
    max_heal_calls: int
    llm_provider: str
    llm_model: str


def _as_bool(v: str | bool) -> bool:
    if isinstance(v, bool):
        return v
    return v.lower() in ("1", "true", "yes")


def load_settings(env: str | None = None) -> Settings:
    env = env or os.getenv("ENV", "dev")
    path = ROOT / "config" / f"{env}.yaml"
    data = yaml.safe_load(path.read_text())

    # Env overrides (CI secrets safe)
    data["base_url"] = os.getenv("BASE_URL", data["base_url"])
    data["browser"] = os.getenv("BROWSER", data["browser"])   # CI matrix override
    data["llm_provider"] = os.getenv("LLM_PROVIDER", data["llm_provider"])
    data["llm_model"] = os.getenv("LLM_MODEL", data["llm_model"])
    if os.getenv("HEADLESS") is not None:
        data["headless"] = _as_bool(os.getenv("HEADLESS", "true"))
    if os.getenv("MAX_HEAL_CALLS_PER_RUN") is not None:
        data["max_heal_calls"] = int(os.getenv("MAX_HEAL_CALLS_PER_RUN", "20"))

    return Settings(**{k: data[k] for k in Settings.__dataclass_fields__})
