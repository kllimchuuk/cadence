from typing import Protocol

from langchain_core.runnables import RunnableConfig

from orchestration.state import SessionState

_MAX_PLACEHOLDER_TURNS = 2


class Responder(Protocol):
    def __call__(self) -> tuple[str, str]: ...


async def conversing_node(
    state: SessionState, config: RunnableConfig
) -> dict[str, object]:
    responder: Responder = config["configurable"]["responder"]
    user_turn, assistant_reply = responder()

    turn_count = state["turn_count"] + 1
    return {
        "transcript": [
            {"role": "user", "content": user_turn},
            {"role": "assistant", "content": assistant_reply},
        ],
        "turn_count": turn_count,
        "should_exit": turn_count >= _MAX_PLACEHOLDER_TURNS,
    }
