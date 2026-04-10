---
name: hume-voice
description: "Hume AI Octave TTS patterns for DungeonMasterONE — voice creation, WebSocket streaming, narrator prose craft"
---

## When to use

Invoke this skill when:
- Building `dm1/providers/tts/hume.py` (Hume Octave integration)
- Building the voice narration pipeline
- Writing or reviewing Narrator agent prompts (prose craft for single-voice TTS)
- Creating DM voice personas
- Debugging TTS streaming, latency, or audio quality issues

**Note:** Voice/TTS is deferred from Phase 1 but informs how the Narrator writes prose NOW.

## Current API Shape (Hume SDK, Octave 2 preview)

### Installation
```bash
pip install hume python-dotenv
```

### Client Init
```python
from hume import AsyncHumeClient
hume = AsyncHumeClient(api_key=settings.HUME_API_KEY)
```

### HTTP Streaming TTS
```python
from hume.tts import PostedUtterance, PostedUtteranceVoiceWithName
import base64

utterance = PostedUtterance(
    text="The innkeeper leans across the bar, his voice dropping to a whisper.",
    voice=PostedUtteranceVoiceWithName(name='DM Narrator', provider='CUSTOM_VOICE')
)
stream = hume.tts.synthesize_json_streaming(utterances=[utterance], strip_headers=True)
async for chunk in stream:
    audio = base64.b64decode(chunk.audio)
    # Forward to client WebSocket
```

### WebSocket Streaming (Bidirectional — lowest latency)
```python
import websockets
ws = await websockets.connect(
    f"wss://api.hume.ai/v0/tts/stream/input?api_key={key}&instant_mode=true&strip_headers=true"
)
await ws.send(json.dumps({"text": "sentence..."}))
msg = await ws.recv()
audio = base64.b64decode(json.loads(msg)["audio"])
```

### Voice Creation
```python
result = await hume.tts.synthesize_json(
    utterances=[PostedUtterance(
        description="Deep storyteller voice, warm and deliberate",
        text="In the age before ages..."
    )],
    num_generations=3
)
await hume.tts.voices.create(name='campfire-dm', generation_id=selected_id)
```

## DM1 Integration Pattern

### Narrator Prose Craft Rules (Phase 1 — applies NOW)
Even without TTS active, write narrator output for eventual single-voice performance:

1. **Attribution tags:** "growls", "whispers", "declares" — NOT "says"
2. **Em-dashes for pauses:** "The door creaks open — and then silence."
3. **Short sentences = tension:** "You hear a sound. Metal on stone. Close."
4. **No explicit stage directions:** No `[angry]` or `[whispering]` — Octave infers from prose
5. **NPC differentiation via speech pattern:** Gruff innkeeper uses short sentences. Elven sage uses formal, flowing prose. Both performed by the same voice.

### Voice Pipeline (Future Phase)
```
Narrator sentence complete → Hume WebSocket → audio chunks → client WebSocket → browser playback
```
Target: first audio chunk within 500ms of sentence completion.

### Fallback Chain
```
Hume Octave → [unavailable/cost cap] → Gemini Flash TTS → [unavailable] → text-only
```

## Common Pitfalls

1. **5,000 char limit per utterance** — split long narrations into sentences before sending
2. **Instant mode requires predefined voice** — can't use voice design + instant mode together
3. **Voice design is English-only** in Octave 2 preview
4. **WebSocket SDK support pending** — currently need raw websockets library for bidirectional streaming
5. **Audio format:** returns base64-encoded audio, decode before forwarding
