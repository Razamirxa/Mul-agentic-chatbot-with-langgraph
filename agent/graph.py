"""LangGraph graph definition for the MUL chatbot.

Builds a StateGraph with conditional routing:
  START → route_query → (mul_related → web_search → generate) | (off_topic → guardrail) → END
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from agent.state import AgentState
from agent.nodes import route_query, web_search, generate, guardrail


def _decide_route(state: AgentState) -> str:
    """Conditional edge function: routes based on classification result."""
    if state.get("route") == "mul_related":
        return "web_search"
    elif state.get("route") == "conversational":
        return "generate"
    return "guardrail"


def build_graph():
    """Build and compile the MUL chatbot agent graph.
    
    Graph structure:
        route_query ──┬── (mul_related) ──→ web_search ──→ generate ──→ END
                      ├── (conversational) ──────────────→ generate ──→ END
                      └── (off_topic)  ──→ guardrail ──────────────────→ END
    
    Returns:
        Compiled LangGraph application with MemorySaver checkpointer.
    """
    # Create the state graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("route_query", route_query)
    workflow.add_node("web_search", web_search)
    workflow.add_node("generate", generate)
    workflow.add_node("guardrail", guardrail)

    # Set entry point
    workflow.set_entry_point("route_query")

    # Add conditional edges from router
    workflow.add_conditional_edges(
        "route_query",
        _decide_route,
        {
            "web_search": "web_search",
            "generate": "generate",
            "guardrail": "guardrail",
        },
    )

    # Linear edges
    workflow.add_edge("web_search", "generate")
    workflow.add_edge("generate", END)
    workflow.add_edge("guardrail", END)

    # Compile with memory checkpointer for conversation persistence
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)

    return app


# Singleton graph instance
graph = build_graph()
