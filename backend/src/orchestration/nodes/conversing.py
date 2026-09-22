from langchain_core.runnables import RunnableConfig

from llm.client import LLMClient
from orchestration.state import SessionState

_PLACEHOLDER_USER_TURN = "Hello!"
_MAX_PLACEHOLDER_TURNS = 2


def _build_prompt(transcript: list[dict[str, str]], user_turn: str) -> str:
    history = "\n".join(f'{entry["role"]}: {entry["content"]}' for entry in transcript)
    return f"{history}\nuser: {user_turn}\nassistant:"


async def conversing_node(
    state: SessionState, config: RunnableConfig
) -> dict[str, object]:
    llm_client: LLMClient = config["configurable"]["conversing_llm"]
    prompt = _build_prompt(state["transcript"], _PLACEHOLDER_USER_TURN)
    assistant_reply = await llm_client.generate(prompt)

    turn_count = state["turn_count"] + 1
    return {
        "transcript": [
            {"role": "user", "content": _PLACEHOLDER_USER_TURN},
            {"role": "assistant", "content": assistant_reply},
        ],
        "turn_count": turn_count,
        "should_exit": turn_count >= _MAX_PLACEHOLDER_TURNS,
    }
