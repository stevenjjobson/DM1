"""
Gemini LLM provider for DungeonMasterONE.

Uses the google-genai SDK. Supports both streaming and non-streaming,
structured JSON output via Pydantic models, and async operations.
"""

import logging
from typing import AsyncIterator

from google import genai
from google.genai import types
from pydantic import BaseModel

from dm1.config.settings import settings
from dm1.providers.llm.base import LLMMessage, LLMProvider, LLMResponse, LLMStreamChunk, ModelRole

logger = logging.getLogger(__name__)

# Map model roles to Gemini model IDs
ROLE_TO_MODEL = {
    ModelRole.NARRATIVE: "gemini-2.5-pro",
    ModelRole.AGENT: "gemini-2.5-flash",
    ModelRole.GENESIS: "gemini-2.5-pro",
}


class GeminiProvider(LLMProvider):
    def __init__(self):
        self._client = genai.Client(api_key=settings.gemini_api_key)

    @property
    def provider_name(self) -> str:
        return "gemini"

    def _resolve_model(self, model: str | None) -> str:
        if model and model in ROLE_TO_MODEL:
            return ROLE_TO_MODEL[model]
        return model or ROLE_TO_MODEL[ModelRole.AGENT]

    def _build_contents(self, messages: list[LLMMessage]) -> tuple[str | None, list[types.Content]]:
        """Convert messages to Gemini format, extracting system instruction."""
        system_instruction = None
        contents: list[types.Content] = []

        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
            else:
                role = "user" if msg.role == "user" else "model"
                contents.append(types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=msg.content)],
                ))

        return system_instruction, contents

    async def generate(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.8,
        max_tokens: int = 2000,
        response_schema: type[BaseModel] | None = None,
    ) -> LLMResponse:
        model_id = self._resolve_model(model)
        system_instruction, contents = self._build_contents(messages)

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        if system_instruction:
            config.system_instruction = system_instruction

        # Structured output (JSON mode)
        if response_schema:
            config.response_mime_type = "application/json"
            config.response_schema = response_schema

        response = await self._client.aio.models.generate_content(
            model=model_id,
            contents=contents,
            config=config,
        )

        input_tokens = 0
        output_tokens = 0
        if response.usage_metadata:
            input_tokens = response.usage_metadata.prompt_token_count or 0
            output_tokens = response.usage_metadata.candidates_token_count or 0

        return LLMResponse(
            content=response.text or "",
            model=model_id,
            provider=self.provider_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            finish_reason=response.candidates[0].finish_reason.name if response.candidates else "unknown",
        )

    async def generate_stream(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.8,
        max_tokens: int = 2000,
    ) -> AsyncIterator[LLMStreamChunk]:
        model_id = self._resolve_model(model)
        system_instruction, contents = self._build_contents(messages)

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        if system_instruction:
            config.system_instruction = system_instruction

        stream = await self._client.aio.models.generate_content_stream(
            model=model_id,
            contents=contents,
            config=config,
        )

        total_input = 0
        total_output = 0

        async for chunk in stream:
            text = chunk.text or ""
            if chunk.usage_metadata:
                total_input = chunk.usage_metadata.prompt_token_count or total_input
                total_output = chunk.usage_metadata.candidates_token_count or total_output

            is_done = bool(chunk.candidates and chunk.candidates[0].finish_reason)

            yield LLMStreamChunk(
                content=text,
                done=is_done,
                model=model_id,
                provider=self.provider_name,
                input_tokens=total_input if is_done else 0,
                output_tokens=total_output if is_done else 0,
            )

    async def is_available(self) -> bool:
        if not settings.gemini_api_key:
            return False
        try:
            response = await self._client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents="Say 'ok'",
                config=types.GenerateContentConfig(max_output_tokens=5),
            )
            return response.text is not None
        except Exception as e:
            logger.warning(f"Gemini availability check failed: {e}")
            return False
