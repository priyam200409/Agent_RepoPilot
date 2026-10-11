
import base64
import binascii
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import quote, urlparse

import httpx


MAX_FILES = 200
MAX_FILE_SIZE = 100 * 1024
MAX_TOTAL_CONTENT_SIZE = 2 * 1024 * 1024

MAX_METADATA_RESPONSE_SIZE = 256 * 1024
MAX_TREE_RESPONSE_SIZE = 2 * 1024 * 1024
MAX_FILE_RESPONSE_SIZE = 256 * 1024

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


def get_bounded_response(
    url: str,
    *,
    max_response_size: int,
    timeout: int,
) -> httpx.Response:
    """Fetch an HTTP response while enforcing a body-size limit."""
    if max_response_size <= 0:
        raise ValueError("Response-size limit must be positive")

    with httpx.stream(
        "GET",
        url,
        headers=API_HEADERS,
        timeout=timeout,
        follow_redirects=False,
    ) as response:
        response.raise_for_status()

        content_length = response.headers.get("content-length")

        if content_length is not None:
            try:
                declared_size = int(content_length)
            except ValueError as exc:
                raise ValueError("Invalid HTTP Content-Length header") from exc

            if declared_size < 0 or declared_size > max_response_size:
                raise ValueError(
                    "GitHub response exceeds the permitted size limit"
                )

        body = bytearray()

        for chunk in response.iter_bytes():
            if len(body) + len(chunk) > max_response_size:
                raise ValueError(
                    "GitHub response exceeds the permitted size limit"
                )

            body.extend(chunk)

        return httpx.Response(
            status_code=response.status_code,
            headers=response.headers,
            content=bytes(body),
            request=response.request,
        )


def parse_github_url(repository_url: str) -> tuple[str, str]:
    """Validate a public GitHub repository URL and return owner/repository."""
    if not isinstance(repository_url, str) or not repository_url:
        raise ValueError("URL must be a valid GitHub URL")

    try:
        parsed = urlparse(repository_url)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("URL must be a valid GitHub URL") from exc

    hostname = (parsed.hostname or "").lower()

    if (
        parsed.scheme not in {"http", "https"}
        or hostname not in {"github.com", "www.github.com"}
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.query
        or parsed.fragment
        or parsed.netloc.lower() not in {"github.com", "www.github.com"}
    ):
        raise ValueError("URL must be a valid GitHub URL")

    parts = parsed.path.strip("/").split("/")

    if (
        len(parts) != 2
        or not all(parts)
        or "%" in parsed.path
        or "\\" in parsed.path
        or any(part in {".", ".."} for part in parts)
    ):
        raise ValueError("URL must point to a GitHub repository")

    owner, repository = parts

    if repository.endswith(".git"):
        repository = repository[:-4]

    valid_chars = set(
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789-_."
    )

    if (
        not owner
        or not repository
        or not set(owner) <= valid_chars
        or not set(repository) <= valid_chars
        or owner in {".", ".."}
        or repository in {".", ".."}
    ):
        raise ValueError("URL contains an invalid repository name")

    return owner, repository


def fetch_repository_metadata(owner: str, repository: str) -> dict:
    """Fetch and validate repository metadata from GitHub."""
    url = f"{API_BASE_URL}/repos/{owner}/{repository}"

    response = get_bounded_response(
        url,
        max_response_size=MAX_METADATA_RESPONSE_SIZE,
        timeout=10,
    )

    if response.status_code == 404:
        raise ValueError("GitHub repository not found")

    try:
        data = response.json()
    except ValueError as exc:
        raise ValueError(
            "Invalid repository metadata response from GitHub"
        ) from exc

    if not isinstance(data, dict):
        raise ValueError("Invalid repository metadata from GitHub")

    try:
        repository_owner = data["owner"]["login"]
        repository_name = data["name"]
        default_branch = data["default_branch"]
    except (KeyError, TypeError) as exc:
        raise ValueError("Invalid repository metadata from GitHub") from exc

    if not all(
        isinstance(value, str) and value
        for value in (repository_owner, repository_name, default_branch)
    ):
        raise ValueError("Invalid repository metadata from GitHub")

    return {
        "owner": repository_owner,
        "repository": repository_name,
        "default_branch": default_branch,
    }


def fetch_repository_tree(
    owner: str,
    repository: str,
    branch: str,
) -> list[dict]:
    """Fetch the recursive Git tree while enforcing the file-count limit."""
    encoded_branch = quote(branch, safe="")
    url = (
        f"{API_BASE_URL}/repos/{owner}/{repository}"
        f"/git/trees/{encoded_branch}?recursive=1"
    )

    response = get_bounded_response(
        url,
        max_response_size=MAX_TREE_RESPONSE_SIZE,
        timeout=15,
    )

    try:
        data = response.json()
    except ValueError as exc:
        raise ValueError("Invalid repository tree response from GitHub") from exc

    if not isinstance(data, dict):
        raise ValueError("Invalid repository tree response from GitHub")

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
    """Return whether a path uses a supported text-file format."""
    path = PurePosixPath(file_path)

    if path.name in {"Dockerfile", "Makefile"}:
        return True

    return path.suffix.lower() in TEXT_EXTENSIONS


def filter_analyzable_files(files: list[dict]) -> list[dict]:
    """Keep supported text files within the per-file size limit."""
    return [
        file
        for file in files
        if isinstance(file, dict)
        and isinstance(file.get("path"), str)
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
    """Fetch and strictly decode a bounded UTF-8 file from GitHub."""
    if not isinstance(file_path, str) or not file_path:
        raise ValueError("File path must not be empty")

    url = (
        f"{API_BASE_URL}/repos/{owner}/{repository}"
        f"/contents/{quote(file_path, safe='/')}"
    )

    response = get_bounded_response(
        url,
        max_response_size=MAX_FILE_RESPONSE_SIZE,
        timeout=10,
    )

    try:
        data = response.json()
    except ValueError as exc:
        raise ValueError(f"Invalid file content response: {file_path}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Invalid file content response: {file_path}")

    if data.get("encoding") != "base64":
        raise ValueError(f"Unsupported encoding: {file_path}")

    encoded_content = data.get("content")

    if not isinstance(encoded_content, str):
        raise ValueError(f"Invalid file content response: {file_path}")

    normalized_content = "".join(encoded_content.split())
    max_encoded_size = 4 * ((MAX_FILE_SIZE + 2) // 3)

    if len(normalized_content) > max_encoded_size:
        raise ValueError(
            f"File exceeds the {MAX_FILE_SIZE}-byte limit: {file_path}"
        )

    try:
        decoded = base64.b64decode(normalized_content, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"Invalid Base64 content: {file_path}") from exc

    if len(decoded) > MAX_FILE_SIZE:
        raise ValueError(
            f"File exceeds the {MAX_FILE_SIZE}-byte limit: {file_path}"
        )

    try:
        return decoded.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"File is not valid UTF-8: {file_path}") from exc


def build_repository_snapshot(repository_url: str) -> RepositorySnapshot:
    """Build a bounded snapshot containing analyzable repository files."""
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
