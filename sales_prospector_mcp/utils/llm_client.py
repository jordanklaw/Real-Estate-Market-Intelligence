"""LLM client with Ollama as default. Multi-provider pattern for portfolio demo."""

import os
import httpx
from sales_prospector_mcp.config import (
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
)

# Only used when LLM_PROVIDER is explicitly set to "anthropic"
_ANTHROPIC_MODEL = "claude-sonnet-4-20250514"


class LLMClient:
    """Unified LLM client. Default path is Ollama-only. Anthropic requires
    explicit opt-in via LLM_PROVIDER=anthropic and ANTHROPIC_API_KEY env vars."""

    def __init__(self):
        self._provider = None
        self._anthropic_client = None
        self._detect_provider()

    def _detect_provider(self):
        """Detect available LLM provider."""
        provider = os.environ.get("LLM_PROVIDER")

        if provider is None or provider == "ollama":
            # Default path: try Ollama
            try:
                resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2.0)
                if resp.status_code == 200:
                    self._provider = "ollama"
                    return
            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPError):
                pass
            raise RuntimeError(
                "No LLM available. Start Ollama with 'ollama serve' "
                "or configure a remote provider via LLM_PROVIDER env var."
            )

        elif provider == "anthropic":
            if os.environ.get("ANTHROPIC_API_KEY"):
                self._provider = "anthropic"
            else:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY not set. Install the anthropic package "
                    "and set the env var to enable remote LLM."
                )
        else:
            raise RuntimeError(
                f"Unknown LLM_PROVIDER: '{provider}'. "
                "Valid values: 'ollama', 'anthropic'."
            )

    @property
    def provider(self) -> str:
        return self._provider

    async def generate(self, prompt: str, system: str = "") -> str:
        """Generate text from the configured LLM provider."""
        if self._provider == "ollama":
            return await self._generate_ollama(prompt, system)
        elif self._provider == "anthropic":
            return await self._generate_anthropic(prompt, system)

    async def _generate_ollama(self, prompt: str, system: str = "") -> str:
        """Generate using Ollama API."""
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            payload["system"] = system

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json=payload,
            )
            resp.raise_for_status()
            return resp.json().get("response", "")

    async def _generate_anthropic(self, prompt: str, system: str = "") -> str:
        """Generate using Anthropic API. Only reached when explicitly configured."""
        try:
            import anthropic
        except ImportError:
            raise RuntimeError(
                "anthropic package not installed. "
                "Run 'pip install anthropic' to enable remote LLM."
            )

        if self._anthropic_client is None:
            self._anthropic_client = anthropic.AsyncAnthropic()

        messages = [{"role": "user", "content": prompt}]
        kwargs = {
            "model": _ANTHROPIC_MODEL,
            "max_tokens": 2048,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        response = await self._anthropic_client.messages.create(**kwargs)
        return response.content[0].text
