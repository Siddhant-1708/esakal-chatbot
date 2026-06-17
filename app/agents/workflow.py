from langgraph.graph import StateGraph, END
from app.agents.state import GraphState
from app.agents.nodes import (
    plan_query, retrieve, check_context, rewrite_query,
    answer, limited_answer, out_of_scope, ask_clarification,
    route_after_plan, route_after_check,
)


def build_graph():
    graph = StateGraph(GraphState)

    graph.add_node("plan_query", plan_query)
    graph.add_node("retrieve", retrieve)
    graph.add_node("check_context", check_context)
    graph.add_node("rewrite_query", rewrite_query)
    graph.add_node("answer", answer)
    graph.add_node("limited_answer", limited_answer)
    graph.add_node("out_of_scope", out_of_scope)
    graph.add_node("ask_clarification", ask_clarification)

    graph.set_entry_point("plan_query")

    graph.add_conditional_edges(
        "plan_query",
        route_after_plan,
        {
            "retrieve": "retrieve",
            "out_of_scope": "out_of_scope",
            "ask_clarification": "ask_clarification",
        },
    )

    graph.add_edge("retrieve", "check_context")

    graph.add_conditional_edges(
        "check_context",
        route_after_check,
        {
            "answer": "answer",
            "rewrite_query": "rewrite_query",
            "limited_answer": "limited_answer",
        },
    )

    graph.add_edge("rewrite_query", "retrieve")
    graph.add_edge("answer", END)
    graph.add_edge("limited_answer", END)
    graph.add_edge("out_of_scope", END)
    graph.add_edge("ask_clarification", END)

    return graph.compile()


graph = build_graph()
