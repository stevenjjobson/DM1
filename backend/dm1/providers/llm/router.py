"""
LLM provider router for DungeonMasterONE.

Implements the three-step fallback chain:
1. Check cost cap → if reached, skip cloud
2. Try cloud (Gemini) → if unavailable, fallback
3. Try LM Studio → if unavailable, raise NoProviderAvailable

Also logs every LLM call for cost tracking.
"""

import logging
from typing import AsyncIterator

from pydantic import BaseModel

from dm1.providers.llm.base import LLMMessage, LLMProvider, LLMResponse, LLMStreamChunk, ModelRole
from dm1.providers.llm.gemini import GeminiProvider
from dm1.providers.llm.lm_studio import LMStudioProvider

logger = logging.getLogger(__name__)


class NoProviderAvailable(Exception):
    """Raised when both cloud and local providers are unavailable."""
    pass


class LLMRouter:
    """Routes LLM calls to the best available provider based on cost cap and availability."""

    def __init__(self):
        self._gemini = GeminiProvider()
        self._lm_studio = LMStudioProvider()
        self._cost_cap_reached = False  # Set by cost management middleware

    @property
    def active_provider(self) -> str:
        """Returns the name of the provider that would be used for the next call."""
        if self._cost_cap_reached:
            return "lm_studio"
        return "gemini"

    def set_cost_cap_reached(self, reached: bool):
        self._cost_cap_reached = reached

    async def _select_provider(self, allow_cloud: bool = True) -> LLMProvider:
        """Select the best available provider."""
        # 1. Check cost cap
        if allow_cloud and not self._cost_cap_reached:
            if await self._gemini.is_available():
                return self._gemini
            logger.warning("Gemini unavailable, falling back to LM Studio")

        # 2. Try LM Studio
        if await self._lm_studio.is_available():
            return self._lm_studio

        # 3. No provider available
        raise NoProviderAvailable(
            "Both cloud (Gemini) and local (LM Studio) providers are unavailable. "
            "Check your Gemini API key and ensure LM Studio is running with a model loaded."
        )

    async def generate(
        self,
        messages: list[LLMMessage],
        model_role: str = ModelRole.AGENT,
        temperature: float = 0.8,
        max_tokens: int = 2000,
        response_schema: type[BaseModel] | None = None,
    ) -> LLMResponse:
        """Generate a complete response using the best available provider."""
        provider = await self._select_provider()
        model = model_role if provider.provider_name == "gemini" else None

        response = await provider.generate(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_schema=response_schema,
        )

        logger.info(
            f"LLM call: provider={response.provider} model={response.model} "
            f"in={response.input_tokens} out={response.output_tokens}"
        )

        return response

    async def generate_stream(
        self,
        messages: list[LLMMessage],
        model_role: str = ModelRole.NARRATIVE,
        temperature: float = 0.8,
        max_tokens: int = 2000,
    ) -> AsyncIterator[LLMStreamChunk]:
        """Generate a streaming response using the best available provider."""
        provider = await self._select_provider()
        model = model_role if provider.provider_name == "gemini" else None

        async for chunk in provider.generate_stream(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            if chunk.done:
                logger.info(
                    f"LLM stream complete: provider={chunk.provider} model={chunk.model} "
                    f"in={chunk.input_tokens} out={chunk.output_tokens}"
                )
            yield chunk

    async def get_status(self) -> dict:
        """Get the current status of all providers."""
        gemini_available = await self._gemini.is_available()
        lm_studio_available = await self._lm_studio.is_available()
        lm_studio_model = await self._lm_studio.get_loaded_model_info() if lm_studio_available else None

        return {
            "active_provider": self.active_provider,
            "cost_cap_reached": self._cost_cap_reached,
            "gemini": {"available": gemini_available},
            "lm_studio": {
                "available": lm_studio_available,
                "model": lm_studio_model,
            },
        }


# Singleton router instance
_router: LLMRouter | None = None


def get_llm_router() -> LLMRouter:
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router
