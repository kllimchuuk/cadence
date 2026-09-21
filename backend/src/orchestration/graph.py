from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from orchestration.nodes.briefing import briefing_node
from orchestration.nodes.conversing import conversing_node
from orchestration.nodes.wrap_up import wrap_up_node
from orchestration.state import SessionState


def decide_exit(state: SessionState) -> str:
    return "exit" if state["should_exit"] else "continue"


def build_session_graph() -> CompiledStateGraph:
    graph = StateGraph(SessionState)
    graph.add_node("briefing", briefing_node)
    graph.add_node("conversing", conversing_node)
    graph.add_node("wrap_up", wrap_up_node)

    graph.add_edge(START, "briefing")
    graph.add_edge("briefing", "conversing")
    graph.add_conditional_edges(
        "conversing", decide_exit, {"continue": "conversing", "exit": "wrap_up"}
    )
    graph.add_edge("wrap_up", END)

    return graph.compile()
