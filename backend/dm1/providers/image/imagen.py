"""
Image generation provider for DungeonMasterONE.

Supports two generation paths:
- Imagen 4 (via generate_images): standalone scenes, environments
- Nano Banana 2 (via generate_content): character-consistent portraits with reference images

Images are stored locally in Phase 1 (cloud storage in production).
"""

import logging
import uuid as uuid_mod
from pathlib import Path

from google import genai
from google.genai import types

from dm1.config.settings import settings

logger = logging.getLogger(__name__)

# Local asset storage for Phase 1
ASSETS_DIR = Path(__file__).parent.parent.parent.parent.parent / "assets" / "campaigns"

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


async def generate_scene_image(
    prompt: str,
    campaign_id: str,
    tier: str = "standard",
) -> dict | None:
    """Generate a scene image using Imagen 4.

    tier: "standard" ($0.04) or "ultra" ($0.06)
    Returns: {"path": str, "filename": str} or None on failure
    """
    client = _get_client()
    model = "imagen-4-ultra" if tier == "ultra" else "imagen-4"

    try:
        response = client.models.generate_images(
            model=model,
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                output_mime_type="image/jpeg",
            ),
        )

        if not response.generated_images:
            logger.warning("Imagen returned no images")
            return None

        # Save to local filesystem
        campaign_dir = ASSETS_DIR / campaign_id
        campaign_dir.mkdir(parents=True, exist_ok=True)
        filename = f"scene_{uuid_mod.uuid4().hex[:8]}.jpg"
        filepath = campaign_dir / filename

        response.generated_images[0].image.save(str(filepath))
        logger.info(f"Scene image saved: {filepath}")

        return {"path": str(filepath), "filename": filename}

    except Exception as e:
        logger.error(f"Image generation failed: {e}")
        return None


async def generate_character_portrait(
    prompt: str,
    campaign_id: str,
    reference_image_path: str | None = None,
) -> dict | None:
    """Generate a character portrait using Nano Banana 2.

    If reference_image_path is provided, it's used for character consistency.
    Returns: {"path": str, "filename": str} or None on failure
    """
    client = _get_client()

    try:
        contents = [prompt]

        # Add reference image for consistency if available
        if reference_image_path:
            from PIL import Image
            ref_image = Image.open(reference_image_path)
            contents = [prompt, ref_image]

        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",  # Nano Banana model
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(
                    aspect_ratio="3:4",
                ),
            ),
        )

        # Extract image from response parts
        for part in response.parts:
            if part.inline_data is not None:
                campaign_dir = ASSETS_DIR / campaign_id
                campaign_dir.mkdir(parents=True, exist_ok=True)
                filename = f"portrait_{uuid_mod.uuid4().hex[:8]}.png"
                filepath = campaign_dir / filename

                image = part.as_image()
                image.save(str(filepath))
                logger.info(f"Portrait saved: {filepath}")

                return {"path": str(filepath), "filename": filename}

        logger.warning("Nano Banana returned no image parts")
        return None

    except Exception as e:
        logger.error(f"Portrait generation failed: {e}")
        return None
