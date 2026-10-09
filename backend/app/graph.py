
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from backend.app.evidence_analyzer import analyze_repository_evidence
from backend.app.github_loader import (
    RepositorySnapshot,
    build_repository_snapshot,
)
from backend.app.reviewer import review_engineering, review_recruiter


class AnalysisState(TypedDict):
    repository_url: str
    snapshot: RepositorySnapshot | None
    evidence: list[dict]
    findings: list[dict]
    recruiter_findings: list[dict]
    scores: dict
    recommendations: list[str]
    status: str


def initialize_analysis(state: AnalysisState) -> dict:
    return {
        "status": "initializing",
        "evidence": [],
        "findings": [],
        "recruiter_findings": [],
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

    return {
        "evidence": analyze_repository_evidence(snapshot),
        "status": "evidence_analyzed",
    }


def engineering_review(state: AnalysisState) -> dict:
    review = review_engineering(state["evidence"])
    return {
        "findings": [
            finding.model_dump(mode="json")
            for finding in review.findings
        ],
        "status": "engineering_review_completed",
    }


def recruiter_review(state: AnalysisState) -> dict:
    review = review_recruiter(state["evidence"])
    return {
        "recruiter_findings": [
            finding.model_dump(mode="json")
            for finding in review.findings
        ],
        "status": "recruiter_review_completed",
    }


def build_analysis_graph():
    graph = StateGraph(AnalysisState)

    graph.add_node("initialize_analysis", initialize_analysis)
    graph.add_node("load_repository", load_repository)
    graph.add_node("analyze_evidence", analyze_evidence)
    graph.add_node("engineering_review", engineering_review)
    graph.add_node("recruiter_review", recruiter_review)

    graph.add_edge(START, "initialize_analysis")
    graph.add_edge("initialize_analysis", "load_repository")
    graph.add_edge("load_repository", "analyze_evidence")
    graph.add_edge("analyze_evidence", "engineering_review")
    graph.add_edge("engineering_review", "recruiter_review")
    graph.add_edge("recruiter_review", END)

    return graph.compile()


analysis_graph = build_analysis_graph()
