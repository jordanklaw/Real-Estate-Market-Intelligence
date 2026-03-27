import os
import unittest
from unittest.mock import Mock, patch

import httpx

from sales_prospector_mcp.utils.llm_client import LLMClient


class LLMClientProviderSelectionTests(unittest.TestCase):
    def test_default_provider_errors_when_ollama_unavailable(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("sales_prospector_mcp.utils.llm_client.httpx.get", side_effect=httpx.ConnectError("down")):
                with self.assertRaises(RuntimeError) as err:
                    LLMClient()

        self.assertIn("No LLM available", str(err.exception))

    def test_anthropic_selected_only_with_explicit_provider_and_api_key(self):
        with patch.dict(
            os.environ,
            {"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "test-key"},
            clear=True,
        ):
            client = LLMClient()

        self.assertEqual(client.provider, "anthropic")

    def test_ollama_selected_when_reachable_and_provider_unset(self):
        mock_resp = Mock(status_code=200)
        with patch.dict(os.environ, {}, clear=True):
            with patch("sales_prospector_mcp.utils.llm_client.httpx.get", return_value=mock_resp):
                client = LLMClient()

        self.assertEqual(client.provider, "ollama")


if __name__ == "__main__":
    unittest.main()
