from orchestration.state import SessionState

_OPENING_LINE = "Hi, thanks for joining — let's get started whenever you're ready."


async def briefing_node(state: SessionState) -> dict[str, object]:
    transcript = state["transcript"] + [{"role": "assistant", "content": _OPENING_LINE}]
    return {"transcript": transcript}
