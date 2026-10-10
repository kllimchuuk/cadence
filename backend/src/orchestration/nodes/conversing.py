from langgraph.runtime import Runtime
from langgraph.types import interrupt

from orchestration.context import SessionRuntimeContext
from orchestration.prompts import conversation_messages
from orchestration.state import SessionState

MAX_CONVERSATION_TURNS = 12
END_SESSION_REQUEST = {"type": "end_session"}


async def conversing_node(
    state: SessionState, *, runtime: Runtime[SessionRuntimeContext]
) -> dict[str, object]:
    user_turn = interrupt({"awaiting": "user_turn"})
    if user_turn == END_SESSION_REQUEST:
        return {"should_exit": True}

    assistant_reply = await runtime.context.conversing_llm.generate(
        state["system_prompt"], conversation_messages(state["transcript"], user_turn)
    )

    turn_count = state["turn_count"] + 1
    return {
        "transcript": [
            {"role": "user", "content": user_turn},
            {"role": "assistant", "content": assistant_reply},
        ],
        "turn_count": turn_count,
        "should_exit": turn_count >= MAX_CONVERSATION_TURNS,
    }
