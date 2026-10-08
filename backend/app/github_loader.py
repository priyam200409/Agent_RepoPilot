from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import urlparse
import base64

import httpx


MAX_FILES = 200
MAX_FILE_SIZE = 100 * 1024

TEXT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx",
    ".java", ".cpp", ".c", ".h", ".cs",
    ".go", ".rs", ".php", ".rb", ".swift", ".kt",
    ".html", ".css", ".scss",
    ".json", ".yaml", ".yml", ".toml", ".xml",
    ".md", ".txt", ".sql", ".sh",
}


@dataclass
class RepositoryFile:
    path: str
    size: int
    content: str


@dataclass
class RepositorySnapshot:
    owner: str
    repository: str
    default_branch: str
    files: list[RepositoryFile]


def parse_github_url(repository_url: str) -> tuple[str, str]:
    parsed = urlparse(repository_url)

    if parsed.scheme not in {"http", "https"} or parsed.netloc != "github.com":
        raise ValueError("URL must be a valid GitHub URL")

    parts = [part for part in parsed.path.split("/") if part]

    if len(parts) != 2:
        raise ValueError("URL must point to a GitHub repository")

    return parts[0], parts[1]


def fetch_repository_metadata(owner: str, repository: str) -> dict:
    url = f"https://api.github.com/repos/{owner}/{repository}"

    response = httpx.get(
        url,
        headers={"Accept": "application/vnd.github+json"},
        timeout=10,
    )

    if response.status_code == 404:
        raise ValueError("GitHub repository not found")

    response.raise_for_status()
    data = response.json()

    return {
        "owner": data["owner"]["login"],
        "repository": data["name"],
        "default_branch": data["default_branch"],
    }


def fetch_repository_tree(
    owner: str,
    repository: str,
    branch: str,
) -> list[dict]:
    url = (
        f"https://api.github.com/repos/{owner}/{repository}"
        f"/git/trees/{branch}?recursive=1"
    )

    response = httpx.get(
        url,
        headers={"Accept": "application/vnd.github+json"},
        timeout=15,
    )

    response.raise_for_status()
    data = response.json()

    if data.get("truncated"):
        raise ValueError("Repository tree is too large to analyze safely")

    files = [item for item in data.get("tree", []) if item.get("type") == "blob"]

    if len(files) > MAX_FILES:
        raise ValueError(f"Repository exceeds the {MAX_FILES}-file limit")

    return files


def is_text_file(file_path: str) -> bool:
    path = PurePosixPath(file_path)

    if path.name in {"Dockerfile", "Makefile"}:
        return True

    return path.suffix.lower() in TEXT_EXTENSIONS


def filter_analyzable_files(files: list[dict]) -> list[dict]:
    return [
        file for file in files
        if file.get("size", 0) <= MAX_FILE_SIZE
        and is_text_file(file.get("path", ""))
    ]


def fetch_file_content(
    owner: str,
    repository: str,
    file_path: str,
) -> str:
    url = (
        f"https://api.github.com/repos/{owner}/{repository}"
        f"/contents/{file_path}"
    )

    response = httpx.get(
        url,
        headers={"Accept": "application/vnd.github+json"},
        timeout=10,
    )

    response.raise_for_status()
    data = response.json()

    if data.get("encoding") != "base64":
        raise ValueError(f"Unsupported encoding: {file_path}")

    try:
        return base64.b64decode(data["content"]).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"File is not valid UTF-8: {file_path}") from exc


def build_repository_snapshot(repository_url: str) -> RepositorySnapshot:
    owner, repository = parse_github_url(repository_url)
    metadata = fetch_repository_metadata(owner, repository)

    tree = fetch_repository_tree(
        owner,
        repository,
        metadata["default_branch"],
    )

    files = [
        RepositoryFile(
            path=file["path"],
            size=file["size"],
            content=fetch_file_content(owner, repository, file["path"]),
        )
        for file in filter_analyzable_files(tree)
    ]

    return RepositorySnapshot(
        owner=metadata["owner"],
        repository=metadata["repository"],
        default_branch=metadata["default_branch"],
        files=files,
    )