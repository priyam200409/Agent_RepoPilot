from backend.app.graph import analysis_graph


def test_analysis_graph_loads_repository(monkeypatch):
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

    assert result["status"] == "repository_loaded"
    assert result["snapshot"].owner == "test-owner"
    assert result["snapshot"].repository == "test-repo"
    assert len(result["snapshot"].files) == 1