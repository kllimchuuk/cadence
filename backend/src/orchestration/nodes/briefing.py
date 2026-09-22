from orchestration.state import SessionState

_OPENING_LINE = "Hi, thanks for joining — let's get started whenever you're ready."


async def briefing_node(_state: SessionState) -> dict[str, object]:
    return {"transcript": [{"role": "assistant", "content": _OPENING_LINE}]}
