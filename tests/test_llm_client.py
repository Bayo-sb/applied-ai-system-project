"""Tests for llm_client.py that need no model, no network and no fake model.

The model call itself is exercised only by the live evaluation (evaluate.py).
"""

from types import SimpleNamespace

import pytest

import llm_client
from llm_client import (
    AnthropicLLM,
    LLMError,
    LLMRefusalError,
    MissingAPIKeyError,
    MissingDependencyError,
    check_stop_reason,
    join_text_blocks,
    load_api_key,
)


def test_normal_stop_reasons_are_accepted():
    check_stop_reason("end_turn")
    check_stop_reason("stop_sequence")
    check_stop_reason(None)


def test_refusal_raises_with_its_category():
    with pytest.raises(LLMRefusalError, match="bio"):
        check_stop_reason("refusal", "bio")


def test_truncated_reply_raises():
    with pytest.raises(LLMError, match="cut off"):
        check_stop_reason("max_tokens")


def test_only_text_blocks_are_joined():
    blocks = [
        SimpleNamespace(type="thinking", thinking=""),
        SimpleNamespace(type="text", text="a"),
        SimpleNamespace(type="text", text="b"),
    ]
    assert join_text_blocks(blocks) == "ab"


def test_missing_key_raises_without_leaking(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(MissingAPIKeyError) as err:
        load_api_key(env_file=tmp_path / "does-not-exist.env")
    assert "ANTHROPIC_API_KEY" in str(err.value)


def test_key_is_read_from_env_file(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("ANTHROPIC_API_KEY=sk-test-not-real\n")
    assert load_api_key(env_file=env_file) == "sk-test-not-real"
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)  # undo load_dotenv's side effect


def test_real_environment_wins_over_env_file(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("ANTHROPIC_API_KEY=from-file\n")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-shell")
    assert load_api_key(env_file=env_file) == "from-shell"


def test_missing_packages_give_a_clear_error(monkeypatch, tmp_path):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name in ("dotenv", "anthropic"):
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    env_file = tmp_path / ".env"
    env_file.write_text("ANTHROPIC_API_KEY=sk-test-not-real\n")
    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(MissingDependencyError, match="python-dotenv"):
        load_api_key(env_file=env_file)
    monkeypatch.setattr(llm_client, "load_api_key", lambda: "sk-test-not-real")
    with pytest.raises(MissingDependencyError, match="anthropic"):
        AnthropicLLM()
