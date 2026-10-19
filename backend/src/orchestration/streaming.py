from collections.abc import Sequence

from langgraph.types import StreamWriter

from llm.client import ChatMessage, LLMClient


async def stream_reply(
    llm: LLMClient,
    system_instruction: str,
    messages: Sequence[ChatMessage],
    write: StreamWriter,
) -> str:
    deltas = []
    async for delta in llm.stream(system_instruction, messages):
        write(delta)
        deltas.append(delta)
    return "".join(deltas)
