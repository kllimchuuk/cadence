from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from orchestration.nodes.briefing import briefing_node
from orchestration.nodes.conversing import conversing_node
from orchestration.state import SessionState


def build_session_graph() -> CompiledStateGraph:
    graph = StateGraph(SessionState)
    graph.add_node("briefing", briefing_node)
    graph.add_node("conversing", conversing_node)

    graph.add_edge(START, "briefing")
    graph.add_edge("briefing", "conversing")
    graph.add_edge("conversing", END)

    return graph.compile()
