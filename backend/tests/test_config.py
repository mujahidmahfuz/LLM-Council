"""Unit tests for environment-driven settings."""

from __future__ import annotations

import pytest

from council.config import (
    DEFAULT_CHAIRMAN_MODEL,
    DEFAULT_COUNCIL_MODELS,
    PLACEHOLDER_API_KEY,
    ConfigError,
    load_settings,
)


def test_defaults_when_environment_is_empty() -> None:
    settings = load_settings({})
    assert settings.api_key is None
    assert not settings.is_configured
    assert settings.council_models == DEFAULT_COUNCIL_MODELS
    assert settings.chairman_model == DEFAULT_CHAIRMAN_MODEL
    assert settings.max_concurrency == 3


def test_reads_both_api_key_variable_names() -> None:
    assert load_settings({"OPENROUTER_API_KEY": " abc "}).api_key == "abc"
    assert load_settings({"OPEN_ROUTER_KEY": "legacy"}).api_key == "legacy"


def test_preferred_key_name_wins() -> None:
    env = {"OPENROUTER_API_KEY": "new", "OPEN_ROUTER_KEY": "old"}
    assert load_settings(env).api_key == "new"


def test_example_placeholder_is_not_a_key() -> None:
    assert not load_settings({"OPENROUTER_API_KEY": PLACEHOLDER_API_KEY}).is_configured


def test_placeholder_does_not_shadow_a_real_key_in_another_variable() -> None:
    env = {"OPENROUTER_API_KEY": PLACEHOLDER_API_KEY, "OPEN_ROUTER_KEY": "real"}
    assert load_settings(env).api_key == "real"


def test_blank_key_counts_as_missing() -> None:
    assert not load_settings({"OPENROUTER_API_KEY": "   "}).is_configured


def test_council_models_are_trimmed_and_deduplicated() -> None:
    settings = load_settings({"COUNCIL_MODELS": " a/one , b/two,a/one,, "})
    assert settings.council_models == ("a/one", "b/two")


def test_empty_model_list_falls_back_to_defaults() -> None:
    assert load_settings({"COUNCIL_MODELS": " , "}).council_models == DEFAULT_COUNCIL_MODELS


def test_too_many_members_is_rejected() -> None:
    models = ",".join(f"v/m{i}" for i in range(27))
    with pytest.raises(ConfigError, match="limit"):
        load_settings({"COUNCIL_MODELS": models})


def test_numbers_are_validated() -> None:
    assert load_settings({"MAX_CONCURRENT_REQUESTS": "5"}).max_concurrency == 5
    with pytest.raises(ConfigError, match="must be a number"):
        load_settings({"REQUEST_TIMEOUT_SECONDS": "soon"})
    with pytest.raises(ConfigError, match=">= 1"):
        load_settings({"MAX_CONCURRENT_REQUESTS": "0"})


def test_zero_retries_is_allowed() -> None:
    assert load_settings({"MAX_RETRIES": "0"}).max_retries == 0


def test_chairman_and_origins_are_configurable() -> None:
    settings = load_settings({"CHAIRMAN_MODEL": "x/chair", "CORS_ORIGINS": "https://app.example"})
    assert settings.chairman_model == "x/chair"
    assert settings.allowed_origins == ("https://app.example",)
