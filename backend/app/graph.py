from typing import TypedDict

from langgraph.graph import END, START, StateGraph


class AnalysisState(TypedDict):
    repository_url: str
    status: str


def initialize_analysis(state: AnalysisState) -> dict:
    return {
        "status": "initialized",
    }


def build_analysis_graph():
    graph = StateGraph(AnalysisState)

    graph.add_node("initialize_analysis", initialize_analysis)

    graph.add_edge(START, "initialize_analysis")
    graph.add_edge("initialize_analysis", END)

    return graph.compile()


analysis_graph = build_analysis_graph()