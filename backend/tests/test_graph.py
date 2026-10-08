from backend.app.graph import analysis_graph


def test_analysis_graph_analyzes_evidence(monkeypatch):
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

    monkeypatch.setattr(
        "backend.app.graph.build_repository_snapshot",
        mock_build_snapshot,
    )

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

    assert result["status"] == "evidence_analyzed"
    assert result["snapshot"].repository == "test-repo"
    assert result["evidence"]

    assert {
        "category": "repository",
        "metric": "analyzable_file_count",
        "value": 1,
    } in result["evidence"]