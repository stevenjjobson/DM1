"""
Base LLM provider interface for DungeonMasterONE.

All LLM providers (Gemini, LM Studio) implement this interface.
The router selects a provider per-call based on cost caps and availability.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator

from pydantic import BaseModel


@dataclass
class LLMMessage:
    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    finish_reason: str = "stop"


@dataclass
class LLMStreamChunk:
    content: str
    done: bool = False
    model: str = ""
    provider: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique provider identifier (e.g., 'gemini', 'lm_studio')."""
        ...

    @abstractmethod
    async def generate(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.8,
        max_tokens: int = 2000,
        response_schema: type[BaseModel] | None = None,
    ) -> LLMResponse:
        """Generate a complete response (non-streaming)."""
        ...

    @abstractmethod
    async def generate_stream(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.8,
        max_tokens: int = 2000,
    ) -> AsyncIterator[LLMStreamChunk]:
        """Generate a streaming response (token by token)."""
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if this provider is currently reachable and ready."""
        ...


# Model role mapping — callers use role names, router maps to specific models
class ModelRole:
    NARRATIVE = "narrative"    # Gemini 2.5 Pro — story text
    AGENT = "agent"            # Gemini 2.5 Flash — routing, extraction, NPC
    GENESIS = "genesis"        # Gemini 2.5 Pro — world generation (structured output)
