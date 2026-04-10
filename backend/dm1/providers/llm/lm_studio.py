"""
LM Studio LLM provider for DungeonMasterONE.

Connects to LM Studio's OpenAI-compatible API at localhost:1234.
Used as a cost-free offline fallback when Gemini is unavailable or
the player's spending cap is reached.
"""

import json
import logging
from typing import AsyncIterator

import httpx
from pydantic import BaseModel

from dm1.config.settings import settings
from dm1.providers.llm.base import LLMMessage, LLMProvider, LLMResponse, LLMStreamChunk

logger = logging.getLogger(__name__)


class LMStudioProvider(LLMProvider):
    def __init__(self):
        self._base_url = settings.lm_studio_url.rstrip("/")
        self._timeout = 120.0  # Local models are slower — generous timeout

    @property
    def provider_name(self) -> str:
        return "lm_studio"

    def _build_messages(self, messages: list[LLMMessage]) -> list[dict]:
        return [{"role": m.role, "content": m.content} for m in messages]

    async def generate(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.8,
        max_tokens: int = 2000,
        response_schema: type[BaseModel] | None = None,
    ) -> LLMResponse:
        body: dict = {
            "messages": self._build_messages(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if model:
            body["model"] = model

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/chat/completions",
                json=body,
                headers={"Authorization": "Bearer lm-studio"},
            )
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        usage = data.get("usage", {})

        return LLMResponse(
            content=choice["message"]["content"],
            model=data.get("model", "unknown"),
            provider=self.provider_name,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            finish_reason=choice.get("finish_reason", "stop"),
        )

    async def generate_stream(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.8,
        max_tokens: int = 2000,
    ) -> AsyncIterator[LLMStreamChunk]:
        body: dict = {
            "messages": self._build_messages(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if model:
            body["model"] = model

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/chat/completions",
                json=body,
                headers={"Authorization": "Bearer lm-studio"},
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload == "[DONE]":
                        yield LLMStreamChunk(content="", done=True, provider=self.provider_name)
                        break

                    try:
                        chunk_data = json.loads(payload)
                        delta = chunk_data["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield LLMStreamChunk(
                                content=content,
                                done=False,
                                model=chunk_data.get("model", "unknown"),
                                provider=self.provider_name,
                            )
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

    async def is_available(self) -> bool:
        """Check if LM Studio is running with a model loaded."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{self._base_url}/models")
                if resp.status_code == 200:
                    data = resp.json()
                    models = data.get("data", [])
                    return any(m.get("state") == "loaded" for m in models)
            return False
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    async def get_loaded_model_info(self) -> dict | None:
        """Get info about the currently loaded model in LM Studio."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{self._base_url}/models")
                if resp.status_code == 200:
                    data = resp.json()
                    for model in data.get("data", []):
                        if model.get("state") == "loaded":
                            return {
                                "id": model.get("id", "unknown"),
                                "type": model.get("type", "llm"),
                                "max_context_length": model.get("max_context_length", 0),
                            }
            return None
        except (httpx.ConnectError, httpx.TimeoutException):
            return None
