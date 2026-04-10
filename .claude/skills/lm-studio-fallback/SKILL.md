---
name: lm-studio-fallback
description: "LM Studio local AI fallback patterns for DungeonMasterONE — OpenAI-compatible API, streaming, connection detection, model recommendations"
---

## When to use

Invoke this skill when:
- Building or modifying `dm1/providers/llm/lm_studio.py` (LM Studio provider)
- Building or modifying `dm1/providers/llm/router.py` (fallback routing logic)
- Implementing connection detection / health checks
- Debugging local model quality or latency issues
- Working on the Settings screen AI Provider section

## Current API Shape (LM Studio OpenAI-compat)

### Base URL
`http://localhost:1234/v1` (port configurable by user)

### Authentication
Any non-empty string works. Convention: `api_key="lm-studio"`

### Endpoints
| Endpoint | Method | Purpose |
|---|---|---|
| `/v1/models` | GET | List models (includes `state: loaded/not-loaded`, `max_context_length`) |
| `/v1/chat/completions` | POST | Chat completions (primary) |
| `/v1/embeddings` | POST | Text embeddings |

### Chat Completion (identical to OpenAI)
```python
import httpx

async with httpx.AsyncClient(base_url="http://localhost:1234/v1") as client:
    response = await client.post("/chat/completions", json={
        "model": "any",  # Ignored if only one model loaded
        "messages": [
            {"role": "system", "content": "You are a D&D Dungeon Master..."},
            {"role": "user", "content": "I open the creaking door."}
        ],
        "temperature": 0.8,
        "max_tokens": 2000,
        "stream": True
    }, headers={"Authorization": "Bearer lm-studio"})
```

### Streaming (SSE — identical format to OpenAI)
```python
async with httpx.AsyncClient() as client:
    async with client.stream("POST", f"{base_url}/chat/completions", json={...}) as resp:
        async for line in resp.aiter_lines():
            if line.startswith("data: ") and line != "data: [DONE]":
                chunk = json.loads(line[6:])
                content = chunk["choices"][0]["delta"].get("content", "")
                if content:
                    yield content
```

### Connection Detection
```python
async def check_lmstudio(base_url: str = "http://localhost:1234/v1") -> bool:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{base_url}/models")
            if resp.status_code == 200:
                data = resp.json()
                return any(m.get("state") == "loaded" for m in data.get("data", []))
        return False
    except (httpx.ConnectError, httpx.TimeoutException):
        return False
```

### Function Calling
Supported via `tools` parameter (same format as OpenAI). Quality varies by model:
- **Native support:** Qwen2.5, Llama 3.1/3.2, Mistral — reliable
- **Prompted fallback:** Other models — unreliable, may hallucinate function names

## DM1 Integration Pattern

### Fallback Router Logic
```python
async def route_llm_call(messages, model_type, settings):
    # 1. Check cost cap
    if cost_cap_reached(settings):
        return await try_lmstudio(messages)
    
    # 2. Try cloud (Gemini)
    try:
        return await gemini_generate(messages, model_type)
    except (APIError, TimeoutError):
        pass
    
    # 3. Fallback to LM Studio
    return await try_lmstudio(messages)

async def try_lmstudio(messages):
    if not await check_lmstudio():
        raise NoProviderAvailable("Both cloud and local AI unavailable")
    return await lmstudio_generate(messages)
```

### Model Recommendations for D&D Narration
| Model | Size | VRAM | Quality |
|---|---|---|---|
| Llama 3.1 70B Q4 | 70B | ~40GB | Best narrative quality |
| Qwen2.5 32B Q4 | 32B | ~20GB | Strong structured output + narration |
| Llama 3.1 8B Q4 | 8B | ~6GB | Good baseline, runs on most GPUs |

## Common Pitfalls

1. **Don't double `/v1/`** — if base_url is `http://localhost:1234/v1`, the endpoint is `/chat/completions`, not `/v1/chat/completions`
2. **Model field is advisory** — with one model loaded, it's ignored. Don't rely on it for routing.
3. **First-token latency is 5-30s** — much slower than cloud. Set appropriate timeouts (120s+).
4. **Structured output is unreliable** — local models may not respect `response_format: json`. Always wrap JSON parsing in try/except.
5. **Port is configurable** — don't hardcode 1234. Read from settings with a default.
6. **`max_context_length` varies** — check `/v1/models` response and truncate history accordingly.
7. **No rate limits** — but limited by hardware. One request at a time on most consumer GPUs.
