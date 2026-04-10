---
name: gemini-integration
description: "Google Gemini API patterns for DungeonMasterONE — text generation, streaming, structured output, embeddings, image generation"
---

## When to use

Invoke this skill when:
- Building or modifying `dm1/providers/llm/gemini.py` (LLM provider)
- Building or modifying `dm1/providers/embedding/gemini_embed.py` (embedding provider)
- Building or modifying `dm1/providers/image/imagen.py` (image generation)
- Implementing structured output for genesis prompts or entity extraction
- Working on streaming narrative output
- Debugging Gemini API errors, rate limits, or safety filter issues

## Current API Shape (google-genai SDK)

### Installation
```bash
pip install google-genai
```

### Client Init
```python
from google import genai
client = genai.Client(api_key=settings.GEMINI_API_KEY)
# Async operations: client.aio.models.*
```

### Text Generation (Async Streaming — primary DM1 pattern)
```python
async for chunk in await client.aio.models.generate_content_stream(
    model='gemini-2.5-pro',
    contents=prompt,
    config=types.GenerateContentConfig(
        system_instruction='You are a D&D Dungeon Master...',
        temperature=0.8, max_output_tokens=2000,
    )
):
    yield chunk.text  # Pipe to WebSocket
```

### Structured Output (JSON Mode with Pydantic)
```python
from pydantic import BaseModel
from google.genai import types

class GenesisOutput(BaseModel):
    locations: list[dict]
    npcs: list[dict]
    quest_hooks: list[str]

response = await client.aio.models.generate_content(
    model='gemini-2.5-pro',
    contents='Generate a world...',
    config=types.GenerateContentConfig(
        response_mime_type='application/json',
        response_schema=GenesisOutput,
    )
)
world = GenesisOutput.model_validate_json(response.text)
```

### Function Calling
```python
def search_graph(query: str) -> str:
    """Search knowledge graph."""
    ...

response = await client.aio.models.generate_content(
    model='gemini-2.5-flash',
    contents='What do we know about Theron?',
    config=types.GenerateContentConfig(tools=[search_graph])
)
```

### Embeddings (Gemini Embedding 2)
```python
response = client.models.embed_content(
    model='gemini-embedding-2',
    contents='text to embed',
    config=types.EmbedContentConfig(output_dimensionality=768)  # or 3072
)
vector = response.embeddings[0].values
# NOTE: 768d vectors need manual normalization before cosine similarity!
```

### Image Generation (Imagen)
```python
response = client.models.generate_images(
    model='imagen-3.0-generate-002',
    prompt='A medieval tavern, warm candlelight, fantasy realism',
    config=types.GenerateImagesConfig(number_of_images=1, output_mime_type='image/jpeg')
)
image_data = response.generated_images[0].image
```

### Token Counting (for cost tracking)
```python
response = client.models.count_tokens(model='gemini-2.5-flash', contents=prompt)
# response.total_tokens → feed to cost metering middleware
```

## DM1 Integration Pattern

### Model Routing
| DM1 Task | Model | Why |
|---|---|---|
| Narrator (story text) | `gemini-2.5-pro` | Quality matters for immersion |
| Orchestrator (routing) | `gemini-2.5-flash` | Speed matters, simple classification |
| Archivist (entity extraction) | `gemini-2.5-flash` | Structured output, cost-efficient |
| NPC Agent (dialogue) | `gemini-2.5-flash` | Fast, personality sim |
| Genesis (world creation) | `gemini-2.5-pro` | Complex generation, structured output |
| Embeddings | `gemini-embedding-2` | Multimodal, 768d for runtime |
| Images | Imagen 4 (when available) | Tiered by scene importance |

### Cost Tracking
After every generation call, extract token counts from `response.usage_metadata`:
- `prompt_token_count` + `candidates_token_count` → total tokens
- Multiply by per-model pricing → add to campaign cost meter

## Common Pitfalls

1. **Normalize 768d embeddings** — only 3072d is pre-normalized. Before cosine similarity: `vector / np.linalg.norm(vector)`

2. **Streaming + structured output** — streamed JSON chunks are partial strings. Only parse after concatenating all chunks.

3. **Safety filters** — Gemini may block fantasy violence content. Configure safety settings: `types.SafetySetting(category='HARM_CATEGORY_DANGEROUS_CONTENT', threshold='BLOCK_ONLY_HIGH')`

4. **Rate limits** — Gemini has per-minute request limits. The provider router should implement exponential backoff.

5. **Async is mandatory** — DM1's FastAPI backend is async. Always use `client.aio.models.*` methods, never sync versions.

6. **`response.text` can be None** — if the model was blocked by safety filters. Always check `response.candidates[0].finish_reason` before accessing `.text`.
