from starlette.requests import HTTPConnection

from llm.factory import LLMClientFactory


def get_llm_client_factory(conn: HTTPConnection) -> LLMClientFactory:
    return conn.app.state.llm_client_factory
