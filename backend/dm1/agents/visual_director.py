"""
Visual Director Agent for DungeonMasterONE.

Decides when and what to illustrate, constructs prompts, and manages
the async image generation pipeline. Images are generated lazily —
they don't block the gameplay turn. When an image completes, it's
sent to the client via WebSocket as a non-blocking update.

Design principle: fire-and-forget image generation that enriches
the experience without interrupting gameplay flow.
"""

import asyncio
import logging
from typing import Callable, Awaitable

from dm1.providers.embedding.gemini_embed import embed_text
from dm1.providers.embedding.vector_db import (
    create_campaign_collection,
    search_similar,
    store_embedding,
)
from dm1.providers.image.imagen import generate_scene_image
from dm1.providers.llm.base import LLMMessage, ModelRole
from dm1.providers.llm.router import get_llm_router

logger = logging.getLogger(__name__)


async def evaluate_scene(narrative_text: str, action_type: str) -> dict:
    """Evaluate whether a narrative beat warrants image generation.

    Returns: {
        "should_generate": bool,
        "tier": "standard" | "ultra",
        "prompt_hint": str,
        "reason": str,
    }
    """
    # Simple heuristic-based evaluation for Phase 1
    # LLM-based evaluation can replace this later

    text_lower = narrative_text.lower()

    # Hero moments → ultra tier
    hero_keywords = ["boss", "dragon", "final", "climactic", "enormous", "ancient", "legendary"]
    if any(kw in text_lower for kw in hero_keywords):
        return {
            "should_generate": True,
            "tier": "ultra",
            "prompt_hint": "dramatic, hero moment",
            "reason": "Hero moment detected",
        }

    # Scene transitions → standard tier
    transition_keywords = [
        "you enter", "you arrive", "you step into", "before you lies",
        "the door opens", "you emerge", "you descend", "a vast",
        "you find yourself", "spreading out before you",
    ]
    if any(kw in text_lower for kw in transition_keywords):
        return {
            "should_generate": True,
            "tier": "standard",
            "prompt_hint": "scene transition, new environment",
            "reason": "Scene transition detected",
        }

    # Most turns don't warrant an image (dialogue, minor actions)
    return {
        "should_generate": False,
        "tier": "standard",
        "prompt_hint": "",
        "reason": "Routine narrative — no image needed",
    }


async def construct_image_prompt(
    narrative_text: str,
    scene_hint: str = "",
    campaign_tone: str = "epic_fantasy",
) -> str:
    """Construct an image generation prompt from narrative text.

    Uses a fast LLM call to distill the narrative into a visual description.
    """
    router = get_llm_router()

    tone_styles = {
        "epic_fantasy": "fantasy art, vibrant colors, dramatic lighting, painterly style",
        "dark_gritty": "dark fantasy, muted tones, harsh shadows, grim atmosphere",
        "lighthearted": "whimsical fantasy art, bright colors, soft lighting, storybook style",
        "horror": "dark horror fantasy, deep shadows, unsettling atmosphere, desaturated",
        "mystery": "noir-inspired fantasy, fog, dramatic contrast, moody atmosphere",
    }
    style = tone_styles.get(campaign_tone, "fantasy art style")

    response = await router.generate(
        messages=[
            LLMMessage(
                role="system",
                content="You are an art director. Given a D&D narrative scene, write a concise "
                "image generation prompt (1-2 sentences). Focus on the visual composition: "
                "setting, lighting, key elements, mood. Do NOT include character names or "
                "dialogue — describe what the scene LOOKS like.",
            ),
            LLMMessage(
                role="user",
                content=f"Scene: {narrative_text[:500]}\nHint: {scene_hint}\nStyle: {style}",
            ),
        ],
        model_role=ModelRole.AGENT,
        temperature=0.7,
        max_tokens=150,
    )

    return f"{response.content.strip()}, {style}"


async def generate_scene_async(
    narrative_text: str,
    campaign_id: str,
    campaign_tone: str = "epic_fantasy",
    on_image_ready: Callable[[str, str], Awaitable[None]] | None = None,
) -> None:
    """Async image generation pipeline — fire and forget.

    1. Evaluate if the scene warrants an image
    2. Check Qdrant for similar existing images (skip if duplicate)
    3. Construct prompt and generate image
    4. Embed and store in Qdrant
    5. Call on_image_ready callback to notify the client

    This runs as a background task — it doesn't block the gameplay turn.
    """
    try:
        # 1. Evaluate
        evaluation = await evaluate_scene(narrative_text, "narrative")
        if not evaluation["should_generate"]:
            return

        # 2. Ensure collection exists
        await create_campaign_collection(campaign_id)

        # 3. Check for similar existing images (pre-generation dedup)
        scene_embedding = await embed_text(narrative_text[:500])
        similar = await search_similar(
            campaign_id,
            scene_embedding,
            asset_type="scene_image",
            threshold=0.92,
            limit=1,
        )
        if similar:
            logger.info(f"Similar image exists (score={similar[0]['score']:.3f}), skipping generation")
            # Could still notify client of the existing image
            if on_image_ready and similar[0]["payload"].get("filename"):
                await on_image_ready(campaign_id, similar[0]["payload"]["filename"])
            return

        # 4. Construct prompt
        prompt = await construct_image_prompt(
            narrative_text,
            scene_hint=evaluation["prompt_hint"],
            campaign_tone=campaign_tone,
        )

        # 5. Generate image
        result = await generate_scene_image(
            prompt=prompt,
            campaign_id=campaign_id,
            tier=evaluation["tier"],
        )

        if not result:
            return

        # 6. Embed and store in Qdrant
        await store_embedding(
            campaign_id=campaign_id,
            vector_768=scene_embedding,
            metadata={
                "asset_type": "scene_image",
                "filename": result["filename"],
                "prompt": prompt,
                "tier": evaluation["tier"],
            },
        )

        # 7. Notify client
        if on_image_ready:
            await on_image_ready(campaign_id, result["filename"])

        logger.info(f"Scene image generated and stored: {result['filename']}")

    except Exception as e:
        logger.error(f"Async scene generation failed: {e}")
