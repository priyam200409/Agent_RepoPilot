
import base64

import httpx
import pytest

import backend.app.github_loader as loader
from backend.app.github_loader import (
    MAX_FILE_SIZE,
    filter_analyzable_files,
    is_text_file,
    parse_github_url,
    fetch_file_content,
)


def test_parse_github_url():
    assert parse_github_url(
        "https://github.com/priyam200409/Agent_RepoPilot"
    ) == ("priyam200409", "Agent_RepoPilot")


def test_parse_github_url_accepts_git_suffix():
    assert parse_github_url(
        "https://github.com/priyam200409/Agent_RepoPilot.git"
    ) == ("priyam200409", "Agent_RepoPilot")


@pytest.mark.parametrize(
    "url",
    [
        "https://google.com/test",
        "https://github.com.evil.com/user/repo",
        "https://user@github.com/user/repo",
        "https://github.com:8443/user/repo",
        "https://github.com/user/repo?tab=readme",
        "https://github.com/user/repo#readme",
        "https://github.com/user/repo/extra",
        "https://github.com/user/%2e%2e",
        "ftp://github.com/user/repo",
        "",
    ],
)
def test_parse_github_url_rejects_invalid_urls(url):
    with pytest.raises(ValueError):
        parse_github_url(url)


def test_is_text_file():
    assert is_text_file("backend/app/main.py")
    assert is_text_file("Dockerfile")
    assert not is_text_file("assets/logo.png")


def test_filter_analyzable_files():
    files = [
        {"path": "main.py", "size": 100},
        {"path": "README.md", "size": 200},
        {"path": "image.png", "size": 100},
        {"path": "large.py", "size": MAX_FILE_SIZE + 1},
    ]

    result = filter_analyzable_files(files)

    assert [file["path"] for file in result] == [
        "main.py",
        "README.md",
    ]


def test_filter_analyzable_files_rejects_invalid_metadata():
    files = [
        {"path": "valid.py", "size": 100},
        {"path": "negative.py", "size": -1},
        {"path": "unknown.py"},
        {"path": "string.py", "size": "100"},
        {"path": "boolean.py", "size": True},
    ]

    result = filter_analyzable_files(files)

    assert [file["path"] for file in result] == ["valid.py"]


def test_filter_analyzable_files_accepts_maximum_file_size():
    files = [{"path": "main.py", "size": MAX_FILE_SIZE}]

    assert filter_analyzable_files(files) == files


def test_fetch_file_content_rejects_invalid_base64(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"encoding": "base64", "content": "%%%invalid%%%"}

    monkeypatch.setattr(
        loader.httpx, "get", lambda *args, **kwargs: FakeResponse()
    )

    with pytest.raises(ValueError, match="Invalid Base64"):
        fetch_file_content("owner", "repo", "main.py")


def test_fetch_file_content_rejects_non_utf8(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "encoding": "base64",
                "content": base64.b64encode(b"\xff").decode(),
            }

    monkeypatch.setattr(
        loader.httpx, "get", lambda *args, **kwargs: FakeResponse()
    )

    with pytest.raises(ValueError, match="valid UTF-8"):
        fetch_file_content("owner", "repo", "main.py")


def test_fetch_file_content_rejects_oversized_content(monkeypatch):
    oversized = b"a" * (MAX_FILE_SIZE + 1)

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "encoding": "base64",
                "content": base64.b64encode(oversized).decode(),
            }

    monkeypatch.setattr(
        loader.httpx, "get", lambda *args, **kwargs: FakeResponse()
    )

    with pytest.raises(ValueError, match="exceeds"):
        fetch_file_content("owner", "repo", "main.py")


def test_fetch_file_content_propagates_http_error(monkeypatch):
    def fake_get(*args, **kwargs):
        request = httpx.Request("GET", "https://api.github.com/test")
        response = httpx.Response(403, request=request)
        response.raise_for_status()

    monkeypatch.setattr(loader.httpx, "get", fake_get)

    with pytest.raises(httpx.HTTPStatusError):
        fetch_file_content("owner", "repo", "main.py")


def test_repository_tree_rejects_truncated_response(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"truncated": True, "tree": []}

    monkeypatch.setattr(
        loader.httpx, "get", lambda *args, **kwargs: FakeResponse()
    )

    with pytest.raises(ValueError, match="too large"):
        loader.fetch_repository_tree("owner", "repo", "main")


def test_repository_tree_rejects_file_limit(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "truncated": False,
                "tree": [
                    {
                        "type": "blob",
                        "path": f"file{i}.py",
                        "size": 1,
                    }
                    for i in range(loader.MAX_FILES + 1)
                ],
            }

    monkeypatch.setattr(
        loader.httpx, "get", lambda *args, **kwargs: FakeResponse()
    )

    with pytest.raises(ValueError, match="file limit"):
        loader.fetch_repository_tree("owner", "repo", "main")


def test_build_snapshot_rejects_total_content_limit(monkeypatch):
    monkeypatch.setattr(
        loader,
        "parse_github_url",
        lambda url: ("owner", "repo"),
    )
    monkeypatch.setattr(
        loader,
        "fetch_repository_metadata",
        lambda owner, repo: {
            "owner": owner,
            "repository": repo,
            "default_branch": "main",
        },
    )
    monkeypatch.setattr(
        loader,
        "fetch_repository_tree",
        lambda *args: [
            {"path": "first.py", "size": 10, "type": "blob"},
            {"path": "second.py", "size": 10, "type": "blob"},
        ],
    )

    content = "x" * (loader.MAX_TOTAL_CONTENT_SIZE // 2 + 1)
    monkeypatch.setattr(
        loader,
        "fetch_file_content",
        lambda *args: content,
    )

    with pytest.raises(ValueError, match="total content-size limit"):
        loader.build_repository_snapshot(
            "https://github.com/owner/repo"
        )
