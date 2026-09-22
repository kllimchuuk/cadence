from langchain_core.runnables import RunnableConfig

from llm.client import LLMClient
from orchestration.state import SessionState

_OPENING_PROMPT = (
    "You are a friendly practice-conversation coach starting a session. "
    "Greet the user and invite them to begin whenever they're ready."
)


async def briefing_node(
    _state: SessionState, config: RunnableConfig
) -> dict[str, object]:
    llm_client: LLMClient = config["configurable"]["briefing_llm"]
    opening_line = await llm_client.generate(_OPENING_PROMPT)
    return {"transcript": [{"role": "assistant", "content": opening_line}]}
