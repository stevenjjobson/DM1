from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class CampaignTone(str, Enum):
    EPIC_FANTASY = "epic_fantasy"
    DARK_GRITTY = "dark_gritty"
    LIGHTHEARTED = "lighthearted"
    HORROR = "horror"
    MYSTERY = "mystery"
    CUSTOM = "custom"


class CampaignLength(str, Enum):
    ONE_SHOT = "one_shot"
    SHORT = "short"  # 3-5 sessions
    LONG = "long"  # 10+


class CampaignStatus(str, Enum):
    CREATING = "creating"  # In wizard, not yet playable
    ACTIVE = "active"
    ARCHIVED = "archived"


class LevelingMode(str, Enum):
    XP = "xp"
    MILESTONE = "milestone"


class CampaignSettings(BaseModel):
    tone: CampaignTone = CampaignTone.EPIC_FANTASY
    length: CampaignLength = CampaignLength.LONG
    leveling_mode: LevelingMode = LevelingMode.XP
    combat_emphasis: float = Field(default=0.5, ge=0.0, le=1.0)  # 0=roleplay, 1=combat
    mature_themes: bool = False
    world_setting: str = "surprise_me"


class CampaignCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    settings: CampaignSettings = CampaignSettings()


class CampaignUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    status: Optional[CampaignStatus] = None


class CampaignInDB(BaseModel):
    id: str
    user_id: str
    name: str
    status: CampaignStatus
    settings: CampaignSettings
    current_turn: int = 0
    character_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    last_played_at: Optional[datetime] = None


class CampaignResponse(BaseModel):
    id: str
    name: str
    status: CampaignStatus
    settings: CampaignSettings
    current_turn: int
    character_id: Optional[str] = None
    portrait_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    last_played_at: Optional[datetime] = None


class CampaignListResponse(BaseModel):
    campaigns: list[CampaignResponse]
    total: int
