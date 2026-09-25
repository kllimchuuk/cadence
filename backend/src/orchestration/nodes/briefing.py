from langgraph.runtime import Runtime

from orchestration.context import SessionRuntimeContext
from orchestration.state import SessionState

_OPENING_PROMPT = (
    "You are a friendly practice-conversation coach starting a session. "
    "Greet the user and invite them to begin whenever they're ready."
)


async def briefing_node(
    _state: SessionState, *, runtime: Runtime[SessionRuntimeContext]
) -> dict[str, object]:
    opening_line = await runtime.context.briefing_llm.generate(_OPENING_PROMPT)
    return {"transcript": [{"role": "assistant", "content": opening_line}]}
