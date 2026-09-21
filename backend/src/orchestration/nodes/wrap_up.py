from orchestration.state import SessionState

_CLOSING_LINE = "Thanks for practising today — great work in there."


async def wrap_up_node(state: SessionState) -> dict[str, object]:
    transcript = state["transcript"] + [{"role": "assistant", "content": _CLOSING_LINE}]
    return {"transcript": transcript}
