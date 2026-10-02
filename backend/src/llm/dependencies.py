from fastapi import Request

from llm.factory import LLMClientFactory


def get_llm_client_factory(request: Request) -> LLMClientFactory:
    return request.app.state.llm_client_factory
