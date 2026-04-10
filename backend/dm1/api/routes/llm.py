from fastapi import APIRouter, Depends

from dm1.api.middleware.auth import get_current_user_id
from dm1.providers.llm.base import LLMMessage, ModelRole
from dm1.providers.llm.router import get_llm_router

router = APIRouter(prefix="/llm", tags=["llm"])


@router.get("/status")
async def llm_status(user_id: str = Depends(get_current_user_id)):
    """Check availability of all LLM providers."""
    router = get_llm_router()
    return await router.get_status()


@router.post("/test")
async def test_llm(user_id: str = Depends(get_current_user_id)):
    """Test the LLM with a simple prompt to verify connectivity."""
    router = get_llm_router()
    response = await router.generate(
        messages=[
            LLMMessage(role="system", content="You are a D&D Dungeon Master. Respond in one sentence."),
            LLMMessage(role="user", content="Describe a mysterious tavern."),
        ],
        model_role=ModelRole.AGENT,
        max_tokens=100,
    )
    return {
        "text": response.content,
        "provider": response.provider,
        "model": response.model,
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
    }
