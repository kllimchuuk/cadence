from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from orchestration.nodes.briefing import briefing_node
from orchestration.nodes.conversing import conversing_node
from orchestration.nodes.session_analysis import session_analysis_node
from orchestration.nodes.weakness_state_update import weakness_state_update_node
from orchestration.nodes.wrap_up import wrap_up_node
from orchestration.state import SessionState


def decide_exit(state: SessionState) -> str:
    return "exit" if state["should_exit"] else "continue"


def build_session_graph(
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    graph = StateGraph(SessionState)
    graph.add_node("briefing", briefing_node)
    graph.add_node("conversing", conversing_node)
    graph.add_node("wrap_up", wrap_up_node)
    graph.add_node("session_analysis", session_analysis_node)
    graph.add_node("weakness_state_update", weakness_state_update_node)

    graph.add_edge(START, "briefing")
    graph.add_edge("briefing", "conversing")
    graph.add_conditional_edges(
        "conversing", decide_exit, {"continue": "conversing", "exit": "wrap_up"}
    )
    graph.add_edge("wrap_up", "session_analysis")
    graph.add_edge("session_analysis", "weakness_state_update")
    graph.add_edge("weakness_state_update", END)

    return graph.compile(checkpointer=checkpointer)
