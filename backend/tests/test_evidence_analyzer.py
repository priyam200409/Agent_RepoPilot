from backend.app.evidence_analyzer import analyze_repository_evidence
from backend.app.github_loader import RepositoryFile, RepositorySnapshot


def test_analyze_repository_evidence():
    snapshot = RepositorySnapshot(
        owner="test-owner",
        repository="test-repo",
        default_branch="main",
        files=[
            RepositoryFile(
                path="README.md",
                size=100,
                content="# Test",
            ),
            RepositoryFile(
                path="requirements.txt",
                size=100,
                content="fastapi",
            ),
            RepositoryFile(
                path="tests/test_api.py",
                size=100,
                content="def test_health(): pass",
            ),
            RepositoryFile(
                path=".github/workflows/ci.yml",
                size=100,
                content="name: CI",
            ),
            RepositoryFile(
                path="main.py",
                size=100,
                content="print('hello')",
            ),
        ],
    )

    evidence = analyze_repository_evidence(snapshot)

    metrics = {
        (item["category"], item["metric"])
        for item in evidence
    }

    assert ("repository", "analyzable_file_count") in metrics
    assert ("documentation", "documentation_file") in metrics
    assert ("dependencies", "dependency_file") in metrics
    assert ("testing", "test_file") in metrics
    assert ("ci_cd", "configuration_file") in metrics
    assert ("language", "file_extension_count") in metrics