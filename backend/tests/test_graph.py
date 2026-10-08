from backend.app.graph import analysis_graph


def test_analysis_graph_initializes_state():
    result = analysis_graph.invoke(
        {
            "repository_url": "https://github.com/test-owner/test-repo",
            "status": "",
        }
    )

    assert result["repository_url"] == (
        "https://github.com/test-owner/test-repo"
    )
    assert result["status"] == "initialized"