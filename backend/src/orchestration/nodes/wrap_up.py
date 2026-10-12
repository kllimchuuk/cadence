from orchestration.state import ConversationState

_CLOSING_LINE = "Thanks for practising today — great work in there."


async def wrap_up_node(_state: ConversationState) -> dict[str, object]:
    return {"transcript": [{"role": "assistant", "content": _CLOSING_LINE}]}
