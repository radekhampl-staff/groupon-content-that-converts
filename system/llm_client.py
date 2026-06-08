"""
Provider-agnostic LLM client.

Supports Anthropic (Claude) and OpenAI out of the box.
Adding a new provider = implement one method.

Configuration via environment variables:
  LLM_PROVIDER   = anthropic | openai          (default: anthropic)
  ANTHROPIC_API_KEY                             (if provider=anthropic)
  OPENAI_API_KEY                                (if provider=openai)
  LLM_MODEL      = model name override          (optional)

Default models:
  anthropic  → claude-sonnet-4-6
  openai     → gpt-4o
"""

import os
from dataclasses import dataclass


@dataclass
class LLMResponse:
    content: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0


DEFAULTS = {
    "anthropic": "claude-sonnet-4-6",
    "openai":    "gpt-4o",
}


def get_client():
    """Return a configured LLMClient based on environment variables."""
    provider = os.environ.get("LLM_PROVIDER", "anthropic").lower()
    model    = os.environ.get("LLM_MODEL", DEFAULTS.get(provider, ""))

    if provider == "anthropic":
        return AnthropicClient(model)
    elif provider == "openai":
        return OpenAIClient(model)
    else:
        raise ValueError(
            f"Unsupported LLM_PROVIDER='{provider}'. "
            f"Supported: anthropic, openai"
        )


class AnthropicClient:
    def __init__(self, model: str):
        try:
            import anthropic
        except ImportError:
            raise ImportError("pip install anthropic")
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY not set")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model  = model

    def complete(self, system_prompt: str, user_message: str,
                 max_tokens: int = 1024, cache_system: bool = True) -> LLMResponse:
        system_content = [{"type": "text", "text": system_prompt}]
        if cache_system:
            system_content[0]["cache_control"] = {"type": "ephemeral"}

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_content,
            messages=[{"role": "user", "content": user_message}],
        )
        usage = response.usage
        return LLMResponse(
            content=response.content[0].text,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0),
        )


class OpenAIClient:
    def __init__(self, model: str):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("pip install openai")
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENAI_API_KEY not set")
        self.client = OpenAI(api_key=api_key)
        self.model  = model

    def complete(self, system_prompt: str, user_message: str,
                 max_tokens: int = 1024, cache_system: bool = False) -> LLMResponse:
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_message},
            ],
        )
        usage = response.usage
        return LLMResponse(
            content=response.choices[0].message.content,
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
        )
