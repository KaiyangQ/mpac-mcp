"""Minimal Anthropic Messages API client for the local MPAC demo."""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .local_config import load_local_config


class AnthropicConfigError(RuntimeError):
    """Raised when the Anthropic client is not correctly configured."""


@dataclass
class AnthropicClient:
    api_key: str | None = None
    model: str | None = None
    max_tokens: int = 900
    timeout_sec: int = 60

    def __post_init__(self) -> None:
        config = load_local_config()
        anthropic = config.get("anthropic", {}) if isinstance(config, dict) else {}
        self.api_key = self.api_key or anthropic.get("api_key") or os.environ.get("ANTHROPIC_API_KEY")
        self.model = self.model or anthropic.get("model") or os.environ.get("ANTHROPIC_MODEL") or "claude-sonnet-4-20250514"
        if not self.api_key:
            raise AnthropicConfigError("Anthropic API key is not set. Add it to local_config.json, the playground form, or ANTHROPIC_API_KEY.")

    def complete_json(self, *, system: str, prompt: str, temperature: float = 0.2) -> dict[str, Any]:
        body = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }
        request = urllib.request.Request(
            url="https://api.anthropic.com/v1/messages",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "content-type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        context = ssl.create_default_context()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_sec, context=context) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Anthropic API request failed with {exc.code}: {details}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Anthropic API request failed: {exc.reason}") from exc

        text = self._collect_text(payload)
        return self._extract_json(text)

    def _collect_text(self, payload: dict[str, Any]) -> str:
        blocks = payload.get("content", [])
        text_parts = [block.get("text", "") for block in blocks if block.get("type") == "text"]
        text = "\n".join(part for part in text_parts if part).strip()
        if not text:
            raise RuntimeError("Anthropic API returned no text content.")
        return text

    def _extract_json(self, text: str) -> dict[str, Any]:
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        start = text.find("{")
        while start != -1:
            depth = 0
            for index in range(start, len(text)):
                char = text[index]
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = text[start : index + 1]
                        try:
                            parsed = json.loads(candidate)
                        except json.JSONDecodeError:
                            break
                        if isinstance(parsed, dict):
                            return parsed
            start = text.find("{", start + 1)
        raise RuntimeError("Anthropic API response did not contain a valid JSON object.")
