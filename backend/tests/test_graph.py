from unittest.mock import patch

from backend.app.graph import analysis_graph
from backend.app.schemas import ReviewResult


def test_analysis_graph_runs_engineering_review(monkeypatch):
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

    review = ReviewResult(
        summary="Review based on supplied evidence.",
        findings=[],
    )

    monkeypatch.setattr(
        "backend.app.graph.build_repository_snapshot",
        mock_build_snapshot,
    )

    with patch(
        "backend.app.graph.review_engineering",
        return_value=review,
    ) as mock_review:
        result = analysis_graph.invoke(
            {
                "repository_url": "https://github.com/test-owner/test-repo",
                "snapshot": None,
                "evidence": [],
                "findings": [],
                "scores": {},
                "recommendations": [],
                "status": "",
            }
        )

    assert result["status"] == "engineering_review_completed"
    assert result["snapshot"].repository == "test-repo"
    assert result["evidence"]
    assert result["findings"] == []
    mock_review.assert_called_once_with(result["evidence"])