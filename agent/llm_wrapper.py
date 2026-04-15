"""
OpsPilot AI — Modular LLM Wrapper
Supports OpenAI and Anthropic (Claude) with a unified interface.
"""

import json
import logging
from typing import Optional
from rich.logging import RichHandler

logger = logging.getLogger("opspilot.llm")


class LLMWrapper:
    """
    Unified wrapper for LLM providers.
    Supports 'openai' and 'anthropic' backends.
    """

    def __init__(self, provider: str = "openai", api_key: str = "", model: str = ""):
        self.provider = provider.lower()
        self.api_key = api_key
        self.client = None

        if self.provider == "openai":
            import openai
            self.model = model or "gpt-4o-mini"
            self.client = openai.OpenAI(api_key=api_key)
            logger.info(f"LLM initialized: OpenAI ({self.model})")

        elif self.provider == "anthropic":
            import anthropic
            self.model = model or "claude-sonnet-4-20250514"
            self.client = anthropic.Anthropic(api_key=api_key)
            logger.info(f"LLM initialized: Anthropic ({self.model})")

        else:
            raise ValueError(f"Unsupported LLM provider: '{provider}'. Use 'openai' or 'anthropic'.")

    def chat(self, messages: list[dict], temperature: float = 0.2, max_tokens: int = 1024) -> str:
        """
        Send a chat completion request and return the response text.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            temperature: Sampling temperature (0-1).
            max_tokens: Maximum tokens in response.

        Returns:
            The assistant's response as a string.
        """
        try:
            if self.provider == "openai":
                return self._chat_openai(messages, temperature, max_tokens)
            elif self.provider == "anthropic":
                return self._chat_anthropic(messages, temperature, max_tokens)
        except Exception as e:
            logger.error(f"LLM API error: {e}")
            raise

    def _chat_openai(self, messages: list[dict], temperature: float, max_tokens: int) -> str:
        """OpenAI chat completion."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()

    def _chat_anthropic(self, messages: list[dict], temperature: float, max_tokens: int) -> str:
        """Anthropic chat completion."""
        # Anthropic uses a separate 'system' parameter
        system_msg = ""
        filtered_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                filtered_messages.append(msg)

        kwargs = {
            "model": self.model,
            "messages": filtered_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system_msg:
            kwargs["system"] = system_msg

        response = self.client.messages.create(**kwargs)
        return response.content[0].text.strip()

    def chat_json(self, messages: list[dict], temperature: float = 0.1, max_tokens: int = 1024) -> dict:
        """
        Send a chat request and parse the response as JSON.
        Handles markdown code fences around JSON.
        """
        response = self.chat(messages, temperature, max_tokens)
        return self._parse_json(response)

    @staticmethod
    def _parse_json(text: str) -> dict:
        """Parse JSON from LLM response, handling code fences."""
        # Strip markdown code fences
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first and last lines (fences)
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON from LLM response: {e}")
            logger.debug(f"Raw response: {text}")
            # Try to extract JSON from the response
            import re
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            raise ValueError(f"Could not parse JSON from LLM response: {text[:200]}")
