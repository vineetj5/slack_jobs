from __future__ import annotations

import json
from typing import Any

import requests

from .config import AppConfig


class LLMClient:
    """Minimal optional LLM adapter.

    If no API key is configured, callers should treat this client as unavailable
    and fall back to deterministic behavior.
    """

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    @property
    def enabled(self) -> bool:
        return bool(self.config.openai_api_key)

    def complete_json(self, prompt: str) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("LLM client is disabled because OPENAI_API_KEY is not set.")

        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {self.config.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.config.openai_model,
                "input": prompt,
                "text": {"format": {"type": "json_object"}},
            },
            timeout=self.config.request_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        text = payload["output"][0]["content"][0]["text"]
        return json.loads(text)

