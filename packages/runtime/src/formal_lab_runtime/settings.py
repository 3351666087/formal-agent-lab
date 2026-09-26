"""Deployment settings read from the environment (and an optional .env file for local development)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


def _find_dotenv() -> Path | None:
    explicit = os.environ.get("FAL_ENV_FILE")
    if explicit:
        return Path(explicit)
    for parent in [Path.cwd(), *Path.cwd().parents]:
        candidate = parent / ".env"
        if candidate.is_file() and (parent / "pyproject.toml").is_file():
            return candidate
    return None


@lru_cache(maxsize=1)
def _dotenv() -> dict[str, str]:
    path = _find_dotenv()
    values: dict[str, str] = {}
    if path is None or not path.is_file():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def get_setting(key: str, default: str | None = None) -> str | None:
    """Process environment wins over .env; .env is only a local-development convenience."""
    if key in os.environ:
        return os.environ[key]
    return _dotenv().get(key, default)


def llm_configured() -> bool:
    return bool(get_setting("FAL_LLM_API_KEY"))
