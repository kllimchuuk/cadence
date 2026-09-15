from orchestration.state import SessionState

_PLACEHOLDER_USER_TURN = "Hello!"
_PLACEHOLDER_REPLY = "That's a great start — tell me more."


async def conversing_node(state: SessionState) -> dict[str, object]:
    transcript = state["transcript"] + [
        {"role": "user", "content": _PLACEHOLDER_USER_TURN},
        {"role": "assistant", "content": _PLACEHOLDER_REPLY},
    ]
    return {"transcript": transcript, "turn_count": state["turn_count"] + 1}
