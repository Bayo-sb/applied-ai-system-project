"""LLM component for PawPal+.

One small job: send a system prompt and a user message to a language model and
return the text. It knows nothing about pets, retrieval or scheduling. The agent
calls it through the `LLM` interface. There is no fake model in this project: model
behaviour is measured only against the real model (see evaluate.py).

The API key is read from the ANTHROPIC_API_KEY environment variable. For local
use it is loaded from an ignored `.env` file in the project folder. It is never
printed, logged or stored in a result.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

# Named settings, so they are easy to change in one place.
DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_MAX_TOKENS = 4096
ENV_FILE = Path(__file__).resolve().parent / ".env"


class LLMError(Exception):
    """The model call failed or returned something the system cannot use."""


class MissingDependencyError(LLMError):
    """A required package is not installed in this Python environment."""


class MissingAPIKeyError(LLMError):
    """No ANTHROPIC_API_KEY was found in the environment or the .env file."""


class LLMRefusalError(LLMError):
    """The model declined the request (stop_reason == "refusal")."""


@dataclass(frozen=True)
class LLMResponse:
    """What the rest of the system gets back. Contains no secrets."""

    text: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    request_id: str | None = None


class LLM(Protocol):
    """The only thing the agent needs to know about a language model."""

    def complete(self, system: str, user: str) -> LLMResponse: ...


def load_api_key(env_file: Path = ENV_FILE) -> str:
    """Return the API key, loading `env_file` first if it exists.

    A key already set in the real environment wins over the file.
    Raises MissingAPIKeyError without ever including a key in the message.
    """
    if env_file.exists():
        try:
            from dotenv import load_dotenv
        except ImportError:
            raise MissingDependencyError(
                "The 'python-dotenv' package is not installed in this environment. "
                "Run: pip install -r requirements.txt"
            ) from None
        load_dotenv(env_file, override=False)
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise MissingAPIKeyError(
            "ANTHROPIC_API_KEY is not set. Put it in a .env file in the project "
            "folder (see .env.example) or export it in your shell."
        )
    return key


def check_stop_reason(stop_reason: str | None, category: str | None = None) -> None:
    """Raise if the model's reply cannot be used: it declined, or it was cut off."""
    if stop_reason == "refusal":
        raise LLMRefusalError(f"The model declined the request (category: {category}).")
    if stop_reason == "max_tokens":
        raise LLMError(
            "The reply was cut off at max_tokens, so it may be incomplete. "
            "Raise max_tokens or shorten the request."
        )


def join_text_blocks(blocks) -> str:
    """Join the text of the reply's text blocks, ignoring other block types (such as thinking)."""
    return "".join(b.text for b in blocks if b.type == "text")


class AnthropicLLM:
    """Calls Claude through the official Anthropic SDK."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        client: Any = None,
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        if client is None:
            key = load_api_key()
            try:
                import anthropic
            except ImportError:
                raise MissingDependencyError(
                    "The 'anthropic' package is not installed in this environment. "
                    "Run: pip install -r requirements.txt"
                ) from None
            client = anthropic.Anthropic(api_key=key)
        self._client = client

    def complete(self, system: str, user: str) -> LLMResponse:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )

        # Check why the model stopped before trusting the content.
        details = getattr(response, "stop_details", None)
        check_stop_reason(response.stop_reason, getattr(details, "category", None))

        text = join_text_blocks(response.content)
        usage = getattr(response, "usage", None)
        return LLMResponse(
            text=text,
            model=self.model,
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            request_id=getattr(response, "_request_id", None),
        )
