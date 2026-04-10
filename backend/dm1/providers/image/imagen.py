"""
Image generation provider for DungeonMasterONE.

Supports two generation paths:
- Imagen 4 (via generate_images): standalone scenes, environments
- Nano Banana 2 (via generate_content): character-consistent portraits with reference images

Images are stored locally in Phase 1 (cloud storage in production).
"""

import asyncio
import logging
import uuid as uuid_mod
from pathlib import Path

from google import genai
from google.genai import types

from dm1.config.settings import settings

logger = logging.getLogger(__name__)

# Local asset storage — /app/assets in Docker, ./assets locally
_docker_path = Path("/app/assets/campaigns")
_local_path = Path(__file__).parent.parent.parent.parent.parent / "assets" / "campaigns"
ASSETS_DIR = _docker_path if _docker_path.parent.exists() else _local_path

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

    def _sync_generate():
        resp = client.models.generate_images(
            model=model,
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                output_mime_type="image/jpeg",
            ),
        )
        if not resp.generated_images:
            return None

        campaign_dir = ASSETS_DIR / campaign_id
        campaign_dir.mkdir(parents=True, exist_ok=True)
        filename = f"scene_{uuid_mod.uuid4().hex[:8]}.jpg"
        filepath = campaign_dir / filename
        resp.generated_images[0].image.save(str(filepath))
        return {"path": str(filepath), "filename": filename}

    try:
        result = await asyncio.to_thread(_sync_generate)
        if result:
            logger.info(f"Scene image saved: {result['path']}")
        else:
            logger.warning("Imagen returned no images")
        return result

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

    def _sync_generate():
        contents = [prompt]
        if reference_image_path:
            from PIL import Image
            ref_image = Image.open(reference_image_path)
            contents = [prompt, ref_image]

        resp = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(aspect_ratio="3:4"),
            ),
        )
        for part in resp.parts:
            if part.inline_data is not None:
                campaign_dir = ASSETS_DIR / campaign_id
                campaign_dir.mkdir(parents=True, exist_ok=True)
                filename = f"portrait_{uuid_mod.uuid4().hex[:8]}.png"
                filepath = campaign_dir / filename
                image = part.as_image()
                image.save(str(filepath))
                return {"path": str(filepath), "filename": filename}
        return None

    try:
        result = await asyncio.to_thread(_sync_generate)
        if result:
            logger.info(f"Portrait saved: {result['path']}")
        else:
            logger.warning("Nano Banana returned no image parts")
        return result

    except Exception as e:
        logger.error(f"Portrait generation failed: {e}")
        return None
