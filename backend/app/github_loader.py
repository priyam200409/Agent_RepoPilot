
import base64
import binascii
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import unquote, urlparse

import httpx


MAX_FILES = 200
MAX_FILE_SIZE = 100 * 1024
MAX_TOTAL_CONTENT_SIZE = 2 * 1024 * 1024

API_BASE_URL = "https://api.github.com"
API_HEADERS = {"Accept": "application/vnd.github+json"}

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
    """Validate a public GitHub repository URL and return owner/repository."""
    if not isinstance(repository_url, str) or not repository_url:
        raise ValueError("URL must be a valid GitHub URL")

    try:
        parsed = urlparse(repository_url)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("URL must be a valid GitHub URL") from exc

    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname != "github.com"
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("URL must be a valid GitHub URL")

    if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        raise ValueError("URL must use github.com")

    raw_path = parsed.path.strip("/")
    parts = raw_path.split("/")

    if (
        len(parts) != 2
        or not all(parts)
        or "%" in raw_path
        or "\\" in raw_path
        or any(part in {".", ".."} for part in parts)
    ):
        raise ValueError("URL must point to a GitHub repository")

    owner, repository = parts

    if repository.endswith(".git"):
        repository = repository[:-4]

    if not owner or not repository:
        raise ValueError("URL must point to a GitHub repository")

    # GitHub owner and repository names cannot contain URL separators.
    valid_chars = set(
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789-_."
    )

    if (
        not set(owner) <= valid_chars
        or not set(repository) <= valid_chars
        or owner in {".", ".."}
        or repository in {".", ".."}
    ):
        raise ValueError("URL contains an invalid repository name")

    return owner, repository


def fetch_repository_metadata(owner: str, repository: str) -> dict:
    url = f"{API_BASE_URL}/repos/{owner}/{repository}"

    response = httpx.get(
        url,
        headers=API_HEADERS,
        timeout=10,
        follow_redirects=False,
    )

    if response.status_code == 404:
        raise ValueError("GitHub repository not found")

    response.raise_for_status()
    data = response.json()

    try:
        return {
            "owner": data["owner"]["login"],
            "repository": data["name"],
            "default_branch": data["default_branch"],
        }
    except (KeyError, TypeError) as exc:
        raise ValueError("Invalid repository metadata from GitHub") from exc


def fetch_repository_tree(
    owner: str,
    repository: str,
    branch: str,
) -> list[dict]:
    # The branch is URL-encoded so special characters cannot alter the URL.
    from urllib.parse import quote

    encoded_branch = quote(branch, safe="")
    url = (
        f"{API_BASE_URL}/repos/{owner}/{repository}"
        f"/git/trees/{encoded_branch}?recursive=1"
    )

    response = httpx.get(
        url,
        headers=API_HEADERS,
        timeout=15,
        follow_redirects=False,
    )

    response.raise_for_status()
    data = response.json()

    if data.get("truncated"):
        raise ValueError("Repository tree is too large to analyze safely")

    tree = data.get("tree")

    if not isinstance(tree, list):
        raise ValueError("Invalid repository tree response from GitHub")

    files = [
        item
        for item in tree
        if isinstance(item, dict) and item.get("type") == "blob"
    ]

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
        file
        for file in files
        if isinstance(file.get("path"), str)
        and isinstance(file.get("size"), int)
        and not isinstance(file.get("size"), bool)
        and 0 <= file["size"] <= MAX_FILE_SIZE
        and is_text_file(file["path"])
    ]


def fetch_file_content(
    owner: str,
    repository: str,
    file_path: str,
) -> str:
    """Fetch and decode a bounded UTF-8 file from the GitHub contents API."""
    if not isinstance(file_path, str) or not file_path:
        raise ValueError("File path must not be empty")

    url = (
        f"{API_BASE_URL}/repos/{owner}/{repository}"
        f"/contents/{file_path}"
    )

    response = httpx.get(
        url,
        headers=API_HEADERS,
        timeout=10,
        follow_redirects=False,
    )

    response.raise_for_status()
    data = response.json()

    if data.get("encoding") != "base64":
        raise ValueError(f"Unsupported encoding: {file_path}")

    encoded_content = data.get("content")

    if not isinstance(encoded_content, str):
        raise ValueError(f"Invalid file content response: {file_path}")

    # Reject an oversized encoded response before decoding it.
    max_encoded_size = 4 * ((MAX_FILE_SIZE + 2) // 3) + 16

    if len(encoded_content) > max_encoded_size:
        raise ValueError(f"File exceeds the {MAX_FILE_SIZE}-byte limit: {file_path}")

    try:
        decoded = base64.b64decode(encoded_content, validate=False)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"Invalid Base64 content: {file_path}") from exc

    if len(decoded) > MAX_FILE_SIZE:
        raise ValueError(f"File exceeds the {MAX_FILE_SIZE}-byte limit: {file_path}")

    try:
        return decoded.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"File is not valid UTF-8: {file_path}") from exc


def build_repository_snapshot(repository_url: str) -> RepositorySnapshot:
    owner, repository = parse_github_url(repository_url)
    metadata = fetch_repository_metadata(owner, repository)

    tree = fetch_repository_tree(
        metadata["owner"],
        metadata["repository"],
        metadata["default_branch"],
    )

    selected_files = filter_analyzable_files(tree)
    files: list[RepositoryFile] = []
    total_content_size = 0

    for file in selected_files:
        remaining_size = MAX_TOTAL_CONTENT_SIZE - total_content_size

        if remaining_size <= 0:
            break

        content = fetch_file_content(
            metadata["owner"],
            metadata["repository"],
            file["path"],
        )

        actual_size = len(content.encode("utf-8"))

        if actual_size > remaining_size:
            raise ValueError(
                "Repository exceeds the total content-size limit "
                f"of {MAX_TOTAL_CONTENT_SIZE} bytes"
            )

        files.append(
            RepositoryFile(
                path=file["path"],
                size=actual_size,
                content=content,
            )
        )
        total_content_size += actual_size

    return RepositorySnapshot(
        owner=metadata["owner"],
        repository=metadata["repository"],
        default_branch=metadata["default_branch"],
        files=files,
    )
