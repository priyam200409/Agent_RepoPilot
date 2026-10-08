from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from backend.app.evidence_analyzer import analyze_repository_evidence
from backend.app.github_loader import (
    RepositorySnapshot,
    build_repository_snapshot,
)


class AnalysisState(TypedDict):
    repository_url: str
    snapshot: RepositorySnapshot | None
    evidence: list[dict]
    findings: list[dict]
    scores: dict
    recommendations: list[str]
    status: str


def initialize_analysis(state: AnalysisState) -> dict:
    return {
        "status": "initializing",
        "evidence": [],
        "findings": [],
        "scores": {},
        "recommendations": [],
    }


def load_repository(state: AnalysisState) -> dict:
    snapshot = build_repository_snapshot(state["repository_url"])

    return {
        "snapshot": snapshot,
        "status": "repository_loaded",
    }


def analyze_evidence(state: AnalysisState) -> dict:
    snapshot = state["snapshot"]

    if snapshot is None:
        raise ValueError("Repository snapshot is required")

    evidence = analyze_repository_evidence(snapshot)

    return {
        "evidence": evidence,
        "status": "evidence_analyzed",
    }


def build_analysis_graph():
    graph = StateGraph(AnalysisState)

    graph.add_node("initialize_analysis", initialize_analysis)
    graph.add_node("load_repository", load_repository)
    graph.add_node("analyze_evidence", analyze_evidence)

    graph.add_edge(START, "initialize_analysis")
    graph.add_edge("initialize_analysis", "load_repository")
    graph.add_edge("load_repository", "analyze_evidence")
    graph.add_edge("analyze_evidence", END)

    return graph.compile()


analysis_graph = build_analysis_graph()