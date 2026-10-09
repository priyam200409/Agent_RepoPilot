
from unittest.mock import patch

from backend.app.graph import analysis_graph
from backend.app.schemas import ReviewResult


def test_analysis_graph_runs_both_reviewers(monkeypatch):
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

    assert result["status"] == "recruiter_review_completed"
    assert result["snapshot"].repository == "test-repo"
    assert result["evidence"]
    assert result["findings"] == []
    assert result["recruiter_findings"] == []

    mock_engineering.assert_called_once_with(result["evidence"])
    mock_recruiter.assert_called_once_with(result["evidence"])
