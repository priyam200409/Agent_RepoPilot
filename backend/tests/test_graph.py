
from unittest.mock import patch

import pytest

from backend.app.graph import (
    analysis_graph,
    calculate_repository_scores,
    generate_recommendations,
)
from backend.app.schemas import ReviewResult


def test_analysis_graph_runs_both_reviewers_and_scores(monkeypatch):
    class FakeFile:
        path = "README.md"
        size = 100
        content = "# Test Repository"

    class FakeSnapshot:
        owner = "test-owner"
        repository = "test-repo"
        default_branch = "main"
        files = [FakeFile()]

    def mock_build_snapshot(url):
        assert url == "https://github.com/test-owner/test-repo"
        return FakeSnapshot()

    engineering_review_result = ReviewResult(
        summary="Engineering review completed.",
        findings=[],
    )
    recruiter_review_result = ReviewResult(
        summary="Recruiter review completed.",
        findings=[],
    )

    monkeypatch.setattr(
        "backend.app.graph.build_repository_snapshot",
        mock_build_snapshot,
    )

    with (
        patch(
            "backend.app.graph.review_engineering",
            return_value=engineering_review_result,
        ) as mock_engineering,
        patch(
            "backend.app.graph.review_recruiter",
            return_value=recruiter_review_result,
        ) as mock_recruiter,
    ):
        result = analysis_graph.invoke(
            {
                "repository_url": "https://github.com/test-owner/test-repo",
                "snapshot": None,
                "evidence": [],
                "findings": [],
                "recruiter_findings": [],
                "scores": {},
                "recommendations": [],
                "status": "",
            }
        )

    assert result["status"] == "completed"
    assert result["report"]["status"] == "completed"
    assert result["report"]["repository_name"] == "test-repo"
    assert result["snapshot"].repository == "test-repo"
    assert result["evidence"]
    assert result["findings"] == []
    assert result["recruiter_findings"] == []
    assert result["recommendations"] == []

    mock_engineering.assert_called_once_with(result["evidence"])
    mock_recruiter.assert_called_once_with(result["evidence"])

    scores = result["scores"]
    assert scores["engineering"]["overall"] == 0
    assert scores["recruiter"]["overall"] == 35
    assert scores["recruiter"]["components"]["readme"]["score"] == 35


def test_repository_scores_award_all_available_points():
    evidence = [
        {
            "category": "repository",
            "metric": "analyzable_file_count",
            "value": 10,
        },
        {
            "category": "documentation",
            "metric": "documentation_file",
            "value": "README.md",
        },
        {
            "category": "documentation",
            "metric": "documentation_file",
            "value": "CONTRIBUTING.md",
        },
        {
            "category": "dependencies",
            "metric": "dependency_file",
            "value": "requirements.txt",
        },
        {
            "category": "testing",
            "metric": "test_file",
            "value": "tests/test_app.py",
        },
        {
            "category": "ci_cd",
            "metric": "configuration_file",
            "value": ".github/workflows/tests.yml",
        },
        {
            "category": "containerization",
            "metric": "configuration_file",
            "value": "Dockerfile",
        },
    ]

    scores = calculate_repository_scores(evidence)

    assert scores["engineering"].overall == 100
    assert scores["recruiter"].overall == 100

    for review_score in scores.values():
        assert review_score.overall == sum(
            component.score
            for component in review_score.components.values()
        )


def test_repository_scores_are_zero_without_evidence():
    scores = calculate_repository_scores([])

    assert scores["engineering"].overall == 0
    assert scores["recruiter"].overall == 0

    for review_score in scores.values():
        assert all(
            component.score == 0
            for component in review_score.components.values()
        )


def test_repository_scores_award_only_supported_criteria():
    evidence = [
        {
            "category": "repository",
            "metric": "analyzable_file_count",
            "value": 5,
        },
        {
            "category": "documentation",
            "metric": "documentation_file",
            "value": "README.md",
        },
    ]

    scores = calculate_repository_scores(evidence)

    assert scores["engineering"].overall == 10
    assert scores["recruiter"].overall == 45
    assert (
        scores["engineering"]
        .components["repository_organization"]
        .score
        == 10
    )
    assert scores["recruiter"].components["readme"].score == 35


def test_recommendations_prioritize_high_severity_findings():
    engineering_findings = [
        {
            "id": "ENG-001",
            "severity": "medium",
            "title": "Add automated tests",
            "recommendation": "Add tests for critical application paths.",
            "explanation": "No test files were detected.",
        },
    ]
    recruiter_findings = [
        {
            "id": "REC-FIND-001",
            "severity": "high",
            "title": "Improve project documentation",
            "recommendation": "Document setup and usage.",
            "explanation": "The repository needs clearer setup guidance.",
        },
    ]

    recommendations = generate_recommendations(
        engineering_findings,
        recruiter_findings,
    )

    assert recommendations[0]["priority"] == "high"
    assert recommendations[0]["finding_ids"] == ["REC-FIND-001"]
    assert recommendations[1]["priority"] == "medium"
    assert recommendations[1]["finding_ids"] == ["ENG-001"]


def test_recommendations_are_empty_without_findings():
    assert generate_recommendations([], []) == []


def test_recommendations_reject_unknown_severity():
    findings = [
        {
            "id": "ENG-001",
            "severity": "urgent",
            "title": "Review configuration",
            "recommendation": "Inspect the configuration.",
            "explanation": "A review is required.",
        },
    ]

    with pytest.raises(ValueError, match="Unsupported finding severity"):
        generate_recommendations(findings, [])
