---
name: imagen-pipeline
description: "Image generation pipeline for DungeonMasterONE — Imagen 4 scenes, Nano Banana 2 character-consistent portraits, reference images"
---

## When to use

Invoke this skill when:
- Building or modifying `dm1/providers/image/` (imagen.py, nano_banana.py, pipeline.py)
- Building the Visual Director agent
- Working on character portrait generation or consistency
- Implementing the campaign style fingerprint
- Debugging image generation quality, consistency, or cost issues

## Current API Shape

### Two Image Generation Systems

| System | Model ID | Method | Best For |
|---|---|---|---|
| **Imagen 4** | `imagen-4` / `imagen-4-ultra` | `client.models.generate_images()` | Standalone scenes, environments |
| **Nano Banana 2** | `gemini-3.1-flash-image-preview` | `client.models.generate_content()` | Character portraits, consistency via reference images |
| **Nano Banana Pro** | `gemini-3-pro-image-preview` | `client.models.generate_content()` | Highest quality portraits |

### Imagen 4 (Scene Illustrations)
```python
response = client.models.generate_images(
    model='imagen-4',  # $0.04/image (Standard) or 'imagen-4-ultra' $0.06/image
    prompt='A dark medieval tavern interior, warm candlelight, fantasy realism',
    config=types.GenerateImagesConfig(number_of_images=1, output_mime_type='image/jpeg')
)
image = response.generated_images[0].image
image.save('scene.jpg')
```

### Nano Banana 2 (Character Portraits with Consistency)
```python
# Initial portrait generation
response = client.models.generate_content(
    model="gemini-3.1-flash-image-preview",
    contents="A half-elf ranger, silver hair, amber eyes, worn blue leather armor, fantasy portrait",
    config=types.GenerateContentConfig(
        response_modalities=['IMAGE'],
        image_config=types.ImageConfig(aspect_ratio="3:4", image_size="2K")
    )
)
for part in response.parts:
    if part.inline_data:
        part.as_image().save("canonical_portrait.png")
```

### Character Consistency via Reference Images
```python
from PIL import Image

canonical = Image.open("canonical_portrait.png")
response = client.models.generate_content(
    model="gemini-3.1-flash-image-preview",
    contents=[
        "The same character fighting a goblin in a torch-lit cave",
        canonical,  # Reference image — model maintains character appearance
    ],
    config=types.GenerateContentConfig(
        response_modalities=['IMAGE'],
        image_config=types.ImageConfig(aspect_ratio="16:9", image_size="2K")
    )
)
```

**Limits:** Up to 4 character refs + 10 object refs per request (Nano Banana 2).

## DM1 Integration Pattern

### Revised Visual Pipeline (5 steps)

```
1. Pre-generation check (Qdrant) — skip if similar image exists (cosine ≥ 0.85)
2. Select model + tier:
   ├── Character portrait → Nano Banana 2 + reference image
   ├── Scene with character → Nano Banana 2 + reference image
   ├── Standalone scene → Imagen 4 Standard
   └── Hero moment → Imagen 4 Ultra or Nano Banana Pro
3. Construct prompt (scene description + Binding Contract text + style fingerprint)
4. Generate → embed via Gemini Embedding 2 → store in Qdrant + filesystem
5. Deliver via WebSocket (base64 PNG/JPEG)
```

### Key Insight: Reference Images > Binding Contract Alone

The Binding Contract JSON still exists as a text supplement to the prompt, but **passing the canonical portrait as a reference image** provides much stronger visual consistency than text description alone. This is Nano Banana 2's killer feature for DM1.

### Canonical Portrait Lifecycle
1. Generated during character creation (Step 5 of wizard)
2. Stored in campaign asset directory
3. Passed as reference image for ALL subsequent images containing this character
4. Embedded in Qdrant for cross-modal search
5. NPC portraits follow the same pattern — generated on first appearance, reused thereafter

## Common Pitfalls

1. **Different API methods** — Imagen 4 uses `generate_images()`, Nano Banana uses `generate_content()`. Don't mix them up.

2. **Response format differs** — Imagen 4 returns `response.generated_images[0].image`, Nano Banana returns image data in `response.parts` (check `part.inline_data`).

3. **SynthID watermark** — All generated images have invisible watermarks. Cannot be removed. Not a problem for DM1 but worth knowing.

4. **Aspect ratio matters** — Use 3:4 for portraits, 16:9 for scenes, 1:1 for thumbnails. Mismatched aspect ratios produce awkward crops.

5. **Cost awareness** — At $0.04-0.06/image, a session generating 20 images costs $0.80-1.20. The Visual Director must be selective. The pre-generation check in Qdrant amortizes cost over a campaign's lifetime.

6. **Nano Banana returns PNG** — even if you want JPEG. Convert in post-processing if storage size matters.

7. **Thinking mode for complex scenes** — Enable `thinking_level="High"` for multi-character compositions. Adds latency but dramatically improves composition quality.
