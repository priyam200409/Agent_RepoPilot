
from backend.app.evidence_analyzer import analyze_repository_evidence
from backend.app.github_loader import RepositoryFile, RepositorySnapshot


def make_snapshot(files):
    return RepositorySnapshot(
        owner="test-owner",
        repository="test-repo",
        default_branch="main",
        files=[
            RepositoryFile(path=path, size=len(content), content=content)
            for path, content in files
        ],
    )


def get_evidence(snapshot):
    return analyze_repository_evidence(snapshot)


def test_analyze_repository_evidence():
    snapshot = make_snapshot([
        ("README.md", "# Demo\nInstallation and usage"),
        ("requirements.txt", "pytest"),
        ("tests/test_app.py", "def test_app(): pass"),
        (".github/workflows/ci.yml", "name: CI"),
    ])

    evidence = get_evidence(snapshot)
    metrics = {item["metric"] for item in evidence}

    assert "analyzable_file_count" in metrics
    assert "default_branch" in metrics
    assert "readme_nonempty" in metrics
    assert "dependency_file" in metrics
    assert "test_file" in metrics
    assert "configuration_file" in metrics


def test_readme_section_markers():
    snapshot = make_snapshot([
        ("README.md", "# Demo\nInstallation\nUsage\nFeatures\nTesting"),
    ])

    evidence = get_evidence(snapshot)
    markers = {
        item["value"]["section"]: item["value"]["detected"]
        for item in evidence
        if item["metric"] == "readme_section_marker"
    }

    assert markers == {
        "installation": True,
        "usage": True,
        "features": True,
        "testing": True,
    }


def test_common_javascript_test_patterns():
    paths = [
        "src/app.test.js",
        "src/app.test.jsx",
        "src/app.test.ts",
        "src/app.test.tsx",
        "src/app.spec.js",
        "src/app.spec.jsx",
        "src/app.spec.ts",
        "src/app.spec.tsx",
    ]

    snapshot = make_snapshot([(path, "") for path in paths])
    evidence = get_evidence(snapshot)

    detected = {
        item["value"]
        for item in evidence
        if item["metric"] == "test_file"
    }

    assert set(paths).issubset(detected)


def test_python_test_patterns():
    paths = [
        "test_app.py",
        "app_test.py",
        "tests/test_service.py",
    ]

    snapshot = make_snapshot([(path, "") for path in paths])
    evidence = get_evidence(snapshot)

    detected = {
        item["value"]
        for item in evidence
        if item["metric"] == "test_file"
    }

    assert set(paths).issubset(detected)


def test_nested_readme_does_not_count_as_root_readme():
    snapshot = make_snapshot([
        ("docs/README.md", "# Documentation"),
    ])

    evidence = get_evidence(snapshot)

    assert not any(
        item["metric"] == "readme_nonempty"
        for item in evidence
    )


def test_empty_readme_is_detected_as_empty():
    snapshot = make_snapshot([
        ("README.md", "   \n  "),
    ])

    evidence = get_evidence(snapshot)
    metrics = {
        item["metric"]: item["value"]
        for item in evidence
        if item["metric"] in {
            "readme_nonempty",
            "readme_content_characters",
            "readme_has_heading",
        }
    }

    assert metrics["readme_nonempty"] is False
    assert metrics["readme_content_characters"] == 6
    assert metrics["readme_has_heading"] is False


def test_readme_heading_is_detected():
    snapshot = make_snapshot([
        ("README.md", "Introduction\n## Features\nProject details"),
    ])

    evidence = get_evidence(snapshot)

    assert any(
        item["metric"] == "readme_has_heading"
        and item["value"] is True
        for item in evidence
    )


def test_readme_content_is_bounded():
    from backend.app.evidence_analyzer import MAX_README_CHARS

    snapshot = make_snapshot([
        ("README.md", "A" * (MAX_README_CHARS + 100)),
    ])

    evidence = get_evidence(snapshot)

    character_count = next(
        item["value"]
        for item in evidence
        if item["metric"] == "readme_content_characters"
    )

    assert character_count == MAX_README_CHARS


def test_missing_readme_produces_no_readme_metrics():
    snapshot = make_snapshot([
        ("src/app.py", "print('hello')"),
    ])

    evidence = get_evidence(snapshot)

    assert not any(
        item["metric"].startswith("readme_")
        for item in evidence
    )


def test_default_branch_is_preserved():
    snapshot = RepositorySnapshot(
        owner="test-owner",
        repository="test-repo",
        default_branch="develop",
        files=[],
    )

    evidence = get_evidence(snapshot)

    assert {
        item["metric"]: item["value"]
        for item in evidence
        if item["metric"] == "default_branch"
    }["default_branch"] == "develop"


def test_documentation_filename_preserves_canonical_case():
    snapshot = make_snapshot([
        ("README.md", "# Demo"),
        ("contributing.md", "Contribution guide"),
    ])

    evidence = get_evidence(snapshot)

    documentation_files = {
        item["value"]
        for item in evidence
        if item["metric"] == "documentation_file"
    }

    assert "README.md" in documentation_files
    assert "CONTRIBUTING.md" in documentation_files


def test_dependency_manifest_is_detected_case_insensitively():
    snapshot = make_snapshot([
        ("PACKAGE.JSON", "{}"),
    ])

    evidence = get_evidence(snapshot)

    assert any(
        item["metric"] == "dependency_file"
        and item["value"] == "package.json"
        for item in evidence
    )


def test_language_extension_counts():
    snapshot = make_snapshot([
        ("src/app.py", "print('hello')"),
        ("src/service.py", "pass"),
        ("src/index.ts", "export {};"),
    ])

    evidence = get_evidence(snapshot)
    counts = {
        item["value"]["extension"]: item["value"]["count"]
        for item in evidence
        if item["metric"] == "file_extension_count"
    }

    assert counts[".py"] == 2
    assert counts[".ts"] == 1
