from orchestration.state import SessionState

_PLACEHOLDER_USER_TURN = "Hello!"
_PLACEHOLDER_REPLY = "That's a great start — tell me more."
_MAX_PLACEHOLDER_TURNS = 2


async def conversing_node(state: SessionState) -> dict[str, object]:
    transcript = state["transcript"] + [
        {"role": "user", "content": _PLACEHOLDER_USER_TURN},
        {"role": "assistant", "content": _PLACEHOLDER_REPLY},
    ]
    turn_count = state["turn_count"] + 1
    return {
        "transcript": transcript,
        "turn_count": turn_count,
        "should_exit": turn_count >= _MAX_PLACEHOLDER_TURNS,
    }
