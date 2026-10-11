
from pathlib import PurePosixPath

from backend.app.github_loader import RepositorySnapshot


DEPENDENCY_FILES = {
    "requirements.txt",
    "pyproject.toml",
    "package.json",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "go.mod",
    "Cargo.toml",
}

TEST_MARKERS = {
    "test",
    "tests",
    "__tests__",
}

TEST_FILE_SUFFIXES = (
    ".test.js",
    ".test.jsx",
    ".test.ts",
    ".test.tsx",
    ".spec.js",
    ".spec.jsx",
    ".spec.ts",
    ".spec.tsx",
)

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

MAX_README_CHARS = 20_000

README_MARKERS = {
    "installation": (
        "installation",
        "install",
        "getting started",
        "setup",
        "set up",
    ),
    "usage": (
        "usage",
        "how to use",
        "example",
        "examples",
        "quick start",
        "quickstart",
    ),
    "features": (
        "features",
        "key features",
        "functionality",
    ),
    "testing": (
        "testing",
        "run tests",
        "running tests",
        "test suite",
    ),
}


def analyze_repository_evidence(
    snapshot: RepositorySnapshot,
) -> list[dict]:
    """Extract deterministic, observable facts from a repository snapshot."""
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
    evidence.extend(_readme_evidence(snapshot))
    evidence.extend(_dependency_evidence(paths))
    evidence.extend(_testing_evidence(paths))
    evidence.extend(_ci_evidence(paths))
    evidence.extend(_container_evidence(paths))
    evidence.extend(_language_evidence(paths))

    return evidence


def _documentation_evidence(
    paths: list[PurePosixPath],
) -> list[dict]:
    """Detect documentation filenames case-insensitively."""
    names = {path.name.lower() for path in paths}

    return [
        {
            "category": "documentation",
            "metric": "documentation_file",
            "value": filename,
        }
        for filename in sorted(DOCUMENTATION_FILES)
        if filename.lower() in names
    ]


def _readme_evidence(snapshot: RepositorySnapshot) -> list[dict]:
    """Extract bounded README markers without judging documentation quality."""
    readme = next(
        (
            file
            for file in snapshot.files
            if PurePosixPath(file.path).as_posix().lower() == "readme.md"
        ),
        None,
    )

    if readme is None:
        return []

    content = readme.content[:MAX_README_CHARS]
    normalized = content.lower()

    evidence = [
        {
            "category": "documentation",
            "metric": "readme_content_characters",
            "value": len(content),
        },
        {
            "category": "documentation",
            "metric": "readme_nonempty",
            "value": bool(content.strip()),
        },
        {
            "category": "documentation",
            "metric": "readme_has_heading",
            "value": any(
                line.lstrip().startswith("#")
                for line in content.splitlines()
                if line.strip()
            ),
        },
    ]

    for section, phrases in README_MARKERS.items():
        evidence.append(
            {
                "category": "documentation",
                "metric": "readme_section_marker",
                "value": {
                    "section": section,
                    "detected": any(
                        phrase in normalized for phrase in phrases
                    ),
                },
            }
        )

    return evidence


def _dependency_evidence(
    paths: list[PurePosixPath],
) -> list[dict]:
    names = {path.name.lower() for path in paths}

    return [
        {
            "category": "dependencies",
            "metric": "dependency_file",
            "value": filename.lower(),
        }
        for filename in sorted(DEPENDENCY_FILES)
        if filename.lower() in names
    ]


def _is_test_file(path: PurePosixPath) -> bool:
    """Recognize common Python, JavaScript, and TypeScript test patterns."""
    if any(
        part.lower() in TEST_MARKERS
        for part in path.parts[:-1]
    ):
        return True

    filename = path.name.lower()

    return (
        filename.startswith("test_")
        or filename.endswith("_test.py")
        or filename.endswith(TEST_FILE_SUFFIXES)
    )


def _testing_evidence(
    paths: list[PurePosixPath],
) -> list[dict]:
    test_paths = [
        path.as_posix()
        for path in paths
        if _is_test_file(path)
    ]

    return [
        {
            "category": "testing",
            "metric": "test_file",
            "value": path,
        }
        for path in sorted(test_paths)
    ]


def _ci_evidence(
    paths: list[PurePosixPath],
) -> list[dict]:
    path_strings = {path.as_posix() for path in paths}

    found = [
        path
        for path in path_strings
        if path.startswith(".github/workflows/")
        or path == ".gitlab-ci.yml"
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


def _container_evidence(
    paths: list[PurePosixPath],
) -> list[dict]:
    names = {path.name.lower() for path in paths}

    return [
        {
            "category": "containerization",
            "metric": "configuration_file",
            "value": filename.lower(),
        }
        for filename in sorted(CONTAINER_FILES)
        if filename.lower() in names
    ]


def _language_evidence(
    paths: list[PurePosixPath],
) -> list[dict]:
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
