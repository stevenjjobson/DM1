from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class ServiceCategory(str, Enum):
    LLM = "llm"
    IMAGE = "image"
    TTS = "tts"
    EMBEDDING = "embedding"


class CostRecord(BaseModel):
    campaign_id: str
    user_id: str
    service: ServiceCategory
    provider: str  # "gemini", "lm_studio", "imagen", "hume", etc.
    model: str  # "gemini-2.5-pro", "imagen-4", etc.
    input_tokens: int = 0
    output_tokens: int = 0
    units: int = 1  # For images: number of images. For TTS: character count.
    estimated_cost_usd: float = 0.0
    timestamp: datetime


class SpendingSummary(BaseModel):
    total_usd: float
    by_service: dict[str, float]  # service category -> total
    by_provider: dict[str, float]  # provider name -> total


class SpendingCap(BaseModel):
    monthly_cap_usd: float = 10.0
    notify_at_percent: list[int] = [50, 80, 100]
