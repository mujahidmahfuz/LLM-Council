"""Runtime configuration, read from environment variables."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from .ranking import MAX_COUNCIL_SIZE

BACKEND_DIR = Path(__file__).resolve().parent.parent

# Free OpenRouter models from different vendors, so the council has diverse views.
# The free catalogue changes often: override with COUNCIL_MODELS if one disappears.
DEFAULT_COUNCIL_MODELS: tuple[str, ...] = (
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "dots-studio/dots-3-note-preview:free",
    "apodex/apodex-1.1-mini:free",
    "liquid/lfm-2.5-2.6b:free",
)
DEFAULT_CHAIRMAN_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"
DEFAULT_ALLOWED_ORIGINS: tuple[str, ...] = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
API_KEY_VARIABLES = ("OPENROUTER_API_KEY", "OPEN_ROUTER_KEY")


class ConfigError(ValueError):
    """Raised when an environment variable holds an unusable value."""


@dataclass(frozen=True)
class Settings:
    api_key: str | None
    council_models: tuple[str, ...]
    chairman_model: str
    max_concurrency: int
    request_timeout: float
    max_retries: int
    allowed_origins: tuple[str, ...]
    max_prompt_chars: int
    base_url: str = OPENROUTER_BASE_URL

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)


def load_env_files() -> None:
    """Load `.env` / `key.env` next to the backend, whatever the working directory."""
    for name in (".env", "key.env"):
        load_dotenv(dotenv_path=BACKEND_DIR / name, override=False)


def _split_list(raw: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    if raw is None or not raw.strip():
        return default
    items = tuple(dict.fromkeys(part.strip() for part in raw.split(",") if part.strip()))
    return items or default


def _read_number(env: Mapping[str, str], name: str, default: float, *, minimum: float) -> float:
    raw = env.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from exc
    if value < minimum:
        raise ConfigError(f"{name} must be >= {minimum}, got {value}")
    return value


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Build immutable settings from `env` (defaults to the process environment)."""
    source = os.environ if env is None else env
    api_key = next((source[n].strip() for n in API_KEY_VARIABLES if source.get(n, "").strip()), None)
    council_models = _split_list(source.get("COUNCIL_MODELS"), DEFAULT_COUNCIL_MODELS)
    if len(council_models) > MAX_COUNCIL_SIZE:
        raise ConfigError(
            f"COUNCIL_MODELS has {len(council_models)} entries; the limit is {MAX_COUNCIL_SIZE}"
        )
    return Settings(
        api_key=api_key,
        council_models=council_models,
        chairman_model=source.get("CHAIRMAN_MODEL", "").strip() or DEFAULT_CHAIRMAN_MODEL,
        max_concurrency=int(_read_number(source, "MAX_CONCURRENT_REQUESTS", 3, minimum=1)),
        request_timeout=_read_number(source, "REQUEST_TIMEOUT_SECONDS", 90, minimum=1),
        max_retries=int(_read_number(source, "MAX_RETRIES", 3, minimum=0)),
        allowed_origins=_split_list(source.get("CORS_ORIGINS"), DEFAULT_ALLOWED_ORIGINS),
        max_prompt_chars=int(_read_number(source, "MAX_PROMPT_CHARS", 8000, minimum=1)),
    )
