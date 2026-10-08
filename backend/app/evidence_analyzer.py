from pathlib import PurePosixPath

from backend.app.github_loader import RepositorySnapshot


DEPENDENCY_FILES = {
    "requirements.txt",
    "pyproject.toml",
    "package.json",
    "pom.xml",
    "build.gradle",
    "go.mod",
    "Cargo.toml",
}

TEST_MARKERS = {
    "test",
    "tests",
    "__tests__",
}

CI_PATH_MARKERS = {
    ".github/workflows",
    ".gitlab-ci.yml",
    ".circleci",
}

DOCUMENTATION_FILES = {
    "README.md",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
}

CONTAINER_FILES = {
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
}


def analyze_repository_evidence(
    snapshot: RepositorySnapshot,
) -> list[dict]:
    paths = [PurePosixPath(file.path) for file in snapshot.files]

    evidence = [
        {
            "category": "repository",
            "metric": "analyzable_file_count",
            "value": len(paths),
        },
        {
            "category": "repository",
            "metric": "default_branch",
            "value": snapshot.default_branch,
        },
    ]

    evidence.extend(_documentation_evidence(paths))
    evidence.extend(_dependency_evidence(paths))
    evidence.extend(_testing_evidence(paths))
    evidence.extend(_ci_evidence(paths))
    evidence.extend(_container_evidence(paths))
    evidence.extend(_language_evidence(paths))

    return evidence


def _documentation_evidence(paths: list[PurePosixPath]) -> list[dict]:
    names = {path.name for path in paths}

    return [
        {
            "category": "documentation",
            "metric": "documentation_file",
            "value": name,
        }
        for name in sorted(names & DOCUMENTATION_FILES)
    ]


def _dependency_evidence(paths: list[PurePosixPath]) -> list[dict]:
    names = {path.name for path in paths}

    return [
        {
            "category": "dependencies",
            "metric": "dependency_file",
            "value": name,
        }
        for name in sorted(names & DEPENDENCY_FILES)
    ]


def _testing_evidence(paths: list[PurePosixPath]) -> list[dict]:
    test_paths = [
        path.as_posix()
        for path in paths
        if any(marker in path.parts for marker in TEST_MARKERS)
        or path.name.startswith("test_")
        or path.name.endswith("_test.py")
    ]

    return [
        {
            "category": "testing",
            "metric": "test_file",
            "value": path,
        }
        for path in sorted(test_paths)
    ]


def _ci_evidence(paths: list[PurePosixPath]) -> list[dict]:
    path_strings = {path.as_posix() for path in paths}

    found = [
        path
        for path in path_strings
        if path.startswith(".github/workflows/")
        or path in {".gitlab-ci.yml"}
        or path.startswith(".circleci/")
    ]

    return [
        {
            "category": "ci_cd",
            "metric": "configuration_file",
            "value": path,
        }
        for path in sorted(found)
    ]


def _container_evidence(paths: list[PurePosixPath]) -> list[dict]:
    names = {path.name for path in paths}

    return [
        {
            "category": "containerization",
            "metric": "configuration_file",
            "value": name,
        }
        for name in sorted(names & CONTAINER_FILES)
    ]


def _language_evidence(paths: list[PurePosixPath]) -> list[dict]:
    extensions: dict[str, int] = {}

    for path in paths:
        suffix = path.suffix.lower()

        if suffix:
            extensions[suffix] = extensions.get(suffix, 0) + 1

    return [
        {
            "category": "language",
            "metric": "file_extension_count",
            "value": {
                "extension": extension,
                "count": count,
            },
        }
        for extension, count in sorted(extensions.items())
    ]