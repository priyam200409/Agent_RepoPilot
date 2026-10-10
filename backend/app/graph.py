
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from backend.app.evidence_analyzer import analyze_repository_evidence
from backend.app.github_loader import (
    RepositorySnapshot,
    build_repository_snapshot,
)
from backend.app.reviewer import review_engineering, review_recruiter
from backend.app.schemas import (
    AnalysisReport,
    EvidenceReference,
    Priority,
    ReviewResult,
    ReviewScores,
    ScoreComponent,
)


class RepositoryLoadError(Exception):
    """Raised when a GitHub repository cannot be loaded."""


class AnalysisState(TypedDict):
    repository_url: str
    snapshot: RepositorySnapshot | None
    evidence: list[dict]
    engineering_review: dict | None
    recruiter_review: dict | None
    findings: list[dict]
    recruiter_findings: list[dict]
    scores: dict
    recommendations: list[dict]
    report: dict | None
    status: str


def initialize_analysis(state: AnalysisState) -> dict:
    return {
        "status": "initializing",
        "snapshot": None,
        "evidence": [],
        "engineering_review": None,
        "recruiter_review": None,
        "findings": [],
        "recruiter_findings": [],
        "scores": {},
        "recommendations": [],
        "report": None,
    }


def load_repository(state: AnalysisState) -> dict:
    try:
        snapshot = build_repository_snapshot(state["repository_url"])
    except ValueError as exc:
        raise RepositoryLoadError(str(exc)) from exc

    return {"snapshot": snapshot, "status": "repository_loaded"}


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
        "engineering_review": review.model_dump(mode="json"),
        "findings": [
            finding.model_dump(mode="json")
            for finding in review.findings
        ],
        "status": "engineering_review_completed",
    }


def recruiter_review(state: AnalysisState) -> dict:
    review = review_recruiter(state["evidence"])
    return {
        "recruiter_review": review.model_dump(mode="json"),
        "recruiter_findings": [
            finding.model_dump(mode="json")
            for finding in review.findings
        ],
        "status": "recruiter_review_completed",
    }


def _has_metric(evidence: list[dict], category: str, metric: str) -> bool:
    return any(
        item.get("category") == category and item.get("metric") == metric
        for item in evidence
    )


def _has_documentation(evidence: list[dict], filename: str) -> bool:
    return any(
        item.get("category") == "documentation"
        and item.get("metric") == "documentation_file"
        and item.get("value") == filename
        for item in evidence
    )


def _build_review_scores(
    criteria: dict[str, tuple[int, bool, str, str]],
) -> ReviewScores:
    components = {}
    for name, (weight, met, positive_reason, missing_reason) in criteria.items():
        points = weight if met else 0
        reason = positive_reason if met else missing_reason
        components[name] = ScoreComponent(
            score=points,
            rationale=f"{reason} Earned {points} of {weight} possible points.",
        )

    return ReviewScores(
        overall=sum(component.score for component in components.values()),
        components=components,
    )


def calculate_repository_scores(evidence: list[dict]) -> dict[str, ReviewScores]:
    """Calculate reproducible scores from repository evidence."""
    file_count = next(
        (
            item.get("value", 0)
            for item in evidence
            if item.get("category") == "repository"
            and item.get("metric") == "analyzable_file_count"
        ),
        0,
    )

    has_tests = _has_metric(evidence, "testing", "test_file")
    has_ci = _has_metric(evidence, "ci_cd", "configuration_file")
    has_dependencies = _has_metric(evidence, "dependencies", "dependency_file")
    has_container = _has_metric(
        evidence, "containerization", "configuration_file"
    )
    has_readme = _has_documentation(evidence, "README.md")
    has_additional_docs = (
        _has_documentation(evidence, "CONTRIBUTING.md")
        or _has_documentation(evidence, "CHANGELOG.md")
    )
    has_organized_repository = (
        isinstance(file_count, int)
        and not isinstance(file_count, bool)
        and file_count >= 5
    )

    engineering = _build_review_scores({
        "testing": (
            30, has_tests, "Test files were detected.",
            "No test files were detected.",
        ),
        "ci_cd": (
            25, has_ci, "CI/CD configuration was detected.",
            "No supported CI/CD configuration was detected.",
        ),
        "dependency_management": (
            20, has_dependencies, "A recognized dependency manifest was detected.",
            "No recognized dependency manifest was detected.",
        ),
        "containerization": (
            15, has_container, "Container configuration was detected.",
            "No supported container configuration was detected.",
        ),
        "repository_organization": (
            10, has_organized_repository,
            "At least five analyzable files were detected.",
            "Fewer than five analyzable files were detected.",
        ),
    })

    recruiter = _build_review_scores({
        "readme": (
            35, has_readme, "README.md was detected.",
            "README.md was not detected.",
        ),
        "additional_documentation": (
            15, has_additional_docs, "Additional project documentation was detected.",
            "No CONTRIBUTING.md or CHANGELOG.md was detected.",
        ),
        "dependency_manifest": (
            15, has_dependencies, "A recognized dependency manifest was detected.",
            "No recognized dependency manifest was detected.",
        ),
        "testing_visibility": (
            15, has_tests, "Test files were detected.",
            "No test files were detected.",
        ),
        "ci_cd_visibility": (
            10, has_ci, "CI/CD configuration was detected.",
            "No supported CI/CD configuration was detected.",
        ),
        "repository_organization": (
            10, has_organized_repository,
            "At least five analyzable files were detected.",
            "Fewer than five analyzable files were detected.",
        ),
    })

    return {"engineering": engineering, "recruiter": recruiter}


def calculate_scores(state: AnalysisState) -> dict:
    scores = calculate_repository_scores(state["evidence"])
    return {
        "scores": {
            name: score.model_dump(mode="json")
            for name, score in scores.items()
        },
        "status": "scoring_completed",
    }


def generate_recommendations(
    engineering_findings: list[dict],
    recruiter_findings: list[dict],
) -> list[dict]:
    priority_by_severity = {
        "critical": Priority.HIGH,
        "high": Priority.HIGH,
        "medium": Priority.MEDIUM,
        "low": Priority.LOW,
        "info": Priority.LOW,
    }
    recommendations = []

    for index, finding in enumerate(
        [*engineering_findings, *recruiter_findings], start=1
    ):
        severity = str(finding["severity"]).lower()
        if severity not in priority_by_severity:
            raise ValueError(f"Unsupported finding severity: {severity}")

        recommendations.append({
            "id": f"REC-{index:03d}",
            "priority": priority_by_severity[severity].value,
            "title": finding["title"],
            "action": finding["recommendation"],
            "rationale": finding["explanation"],
            "finding_ids": [finding["id"]],
        })

    priority_rank = {"high": 0, "medium": 1, "low": 2}
    return sorted(
        recommendations,
        key=lambda item: priority_rank[item["priority"]],
    )


def build_recommendations(state: AnalysisState) -> dict:
    return {
        "recommendations": generate_recommendations(
            state["findings"], state["recruiter_findings"]
        ),
        "status": "recommendations_generated",
    }


def build_analysis_report(state: AnalysisState) -> dict:
    snapshot = state["snapshot"]
    if snapshot is None:
        raise ValueError("Repository snapshot is required")

    scores = state["scores"]
    engineering_scores = ReviewScores.model_validate(scores["engineering"])
    recruiter_scores = ReviewScores.model_validate(scores["recruiter"])

    report = AnalysisReport(
        repository_url=state["repository_url"],
        repository_name=snapshot.repository,
        engineering_review=ReviewResult.model_validate(
            state["engineering_review"]
        ),
        recruiter_review=ReviewResult.model_validate(
            state["recruiter_review"]
        ),
        engineering_scores=engineering_scores,
        recruiter_scores=recruiter_scores,
        overall_score=(
            engineering_scores.overall + recruiter_scores.overall + 1
        ) // 2,
        recommendations=state["recommendations"],
        evidence=[
            EvidenceReference.model_validate(item)
            for item in state["evidence"]
        ],
        status="completed",
    )
    return {
        "report": report.model_dump(mode="json"),
        "status": "completed",
    }


def build_analysis_graph():
    graph = StateGraph(AnalysisState)
    graph.add_node("initialize_analysis", initialize_analysis)
    graph.add_node("load_repository", load_repository)
    graph.add_node("analyze_evidence", analyze_evidence)
    graph.add_node("engineering_review", engineering_review)
    graph.add_node("recruiter_review", recruiter_review)
    graph.add_node("calculate_scores", calculate_scores)
    graph.add_node("build_recommendations", build_recommendations)
    graph.add_node("build_analysis_report", build_analysis_report)

    graph.add_edge(START, "initialize_analysis")
    graph.add_edge("initialize_analysis", "load_repository")
    graph.add_edge("load_repository", "analyze_evidence")
    graph.add_edge("analyze_evidence", "engineering_review")
    graph.add_edge("engineering_review", "recruiter_review")
    graph.add_edge("recruiter_review", "calculate_scores")
    graph.add_edge("calculate_scores", "build_recommendations")
    graph.add_edge("build_recommendations", "build_analysis_report")
    graph.add_edge("build_analysis_report", END)

    return graph.compile()


analysis_graph = build_analysis_graph()
