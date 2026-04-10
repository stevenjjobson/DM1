---
name: qdrant-integration
description: "Qdrant vector DB patterns for DungeonMasterONE — collection lifecycle, named vectors, similarity search, embedding storage"
---

## When to use

Invoke this skill when:
- Building or modifying `dm1/providers/embedding/vector_db.py` (Qdrant abstraction)
- Working on per-campaign collection lifecycle (create/delete on campaign create/delete)
- Implementing pre-generation image duplicate detection
- Building the campaign asset library search
- Computing or using campaign style fingerprints
- Debugging vector search quality or threshold tuning

## Current API Shape (qdrant-client v1.17.1)

### Installation
```bash
pip install qdrant-client
```

### Async Client (required for DM1)
```python
from qdrant_client import AsyncQdrantClient
client = AsyncQdrantClient(url="http://localhost:6333", prefer_grpc=True)
```

### Create Collection with Named Vectors (768d + 3072d)
```python
from qdrant_client.models import VectorParams, Distance

await client.create_collection(
    collection_name=f"campaign_{campaign_id}",
    vectors_config={
        "fast": VectorParams(size=768, distance=Distance.COSINE),
        "precise": VectorParams(size=3072, distance=Distance.COSINE),
    },
)
# Create payload indexes for filtered search
await client.create_payload_index(f"campaign_{campaign_id}", "asset_type", "keyword")
```

### Upsert Points
```python
from qdrant_client.models import PointStruct

await client.upsert(collection_name=f"campaign_{campaign_id}", points=[
    PointStruct(
        id=str(uuid.uuid4()),
        vector={"fast": normalized_768d, "precise": embedding_3072d},
        payload={"asset_type": "image", "description": "...", "source_uri": "...", "created_at": "..."}
    )
])
```

### Search with Threshold
```python
from qdrant_client.models import Filter, FieldCondition, MatchValue

results = await client.query_points(
    collection_name=f"campaign_{campaign_id}",
    query=query_768d,
    using="fast",
    query_filter=Filter(must=[FieldCondition(key="asset_type", match=MatchValue(value="image"))]),
    score_threshold=0.85,
    limit=10,
)
```

### Delete Collection
```python
await client.delete_collection(f"campaign_{campaign_id}")
```

## DM1 Integration Pattern

### Named Vector Strategy
- `fast` (768d): runtime queries, duplicate detection, cross-modal search
- `precise` (3072d): style fingerprint computation, high-accuracy matching

### Collection Lifecycle
- Campaign created → `create_collection(f"campaign_{id}")`
- Campaign active → upsert/search
- Campaign deleted → `delete_collection(f"campaign_{id}")`

### Pre-Generation Duplicate Check
```python
results = await client.query_points(
    collection_name=f"campaign_{id}", query=prompt_embedding_768d,
    using="fast", query_filter=Filter(must=[FieldCondition(key="asset_type", match=MatchValue(value="image"))]),
    score_threshold=0.85, limit=1
)
if results.points:
    return results.points[0].payload["source_uri"]  # Reuse existing
# else: generate new image
```

## Docker Compose
```yaml
qdrant:
  image: qdrant/qdrant:v1.17.1
  ports: ["6333:6333", "6334:6334"]
  volumes: [qdrant_data:/qdrant/storage]
```

## Common Pitfalls

1. **Normalize 768d embeddings** — Gemini only normalizes 3072d. `vec / np.linalg.norm(vec)` before upsert.
2. **Named vector required** — must specify `using="fast"` or `NamedVector(name="fast", ...)`. No default vector.
3. **AsyncQdrantClient only** — sync client blocks FastAPI event loop.
4. **Payload indexes** — create on `asset_type` and any frequently filtered fields to avoid full scans.
5. **Collection deletion is permanent** — no undo. Guard with existence check.
6. **Dashboard** — http://localhost:6333/dashboard for visual inspection.
