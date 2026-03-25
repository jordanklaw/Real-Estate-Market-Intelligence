"""LLM client with Ollama primary and Anthropic API fallback."""

import os
import httpx
from sales_prospector_mcp.config import (
    LLM_PROVIDER,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    ANTHROPIC_MODEL,
)


class LLMClient:
    """Unified LLM client. Tries Ollama first, falls back to Anthropic."""

    def __init__(self):
        self._provider = None
        self._anthropic_client = None
        self._detect_provider()

    def _detect_provider(self):
        """Detect available LLM provider."""
        provider_env = os.environ.get("LLM_PROVIDER", LLM_PROVIDER)

        if provider_env in ("ollama", "anthropic"):
            self._provider = provider_env
            return

        # Auto-detect: try Ollama first
        try:
            resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2.0)
            if resp.status_code == 200:
                self._provider = "ollama"
                return
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPError):
            pass

        # Fall back to Anthropic
        if os.environ.get("ANTHROPIC_API_KEY"):
            self._provider = "anthropic"
        else:
            self._provider = "anthropic"  # Will fail at call time if no key

    @property
    def provider(self) -> str:
        return self._provider

    async def generate(self, prompt: str, system: str = "") -> str:
        """Generate text from the configured LLM provider."""
        if self._provider == "ollama":
            return await self._generate_ollama(prompt, system)
        else:
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
            try:
                resp = await client.post(
                    f"{OLLAMA_BASE_URL}/api/generate",
                    json=payload,
                )
                resp.raise_for_status()
                return resp.json().get("response", "")
            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPError):
                # Fall back to Anthropic on Ollama failure
                return await self._generate_anthropic(prompt, system)

    async def _generate_anthropic(self, prompt: str, system: str = "") -> str:
        """Generate using Anthropic API."""
        try:
            import anthropic
        except ImportError:
            return self._fallback_response(prompt)

        if self._anthropic_client is None:
            self._anthropic_client = anthropic.AsyncAnthropic()

        messages = [{"role": "user", "content": prompt}]
        kwargs = {
            "model": ANTHROPIC_MODEL,
            "max_tokens": 2048,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        try:
            response = await self._anthropic_client.messages.create(**kwargs)
            return response.content[0].text
        except Exception:
            return self._fallback_response(prompt)

    def _fallback_response(self, prompt: str) -> str:
        """Provide a basic response when no LLM is available."""
        return (
            "LLM unavailable. Please configure either Ollama (localhost:11434) "
            "or set ANTHROPIC_API_KEY environment variable.\n\n"
            f"Original prompt summary: {prompt[:200]}..."
        )
