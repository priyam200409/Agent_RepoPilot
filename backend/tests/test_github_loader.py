
import base64
from contextlib import contextmanager

import httpx
import pytest

import backend.app.github_loader as loader
from backend.app.github_loader import (
    MAX_FILE_SIZE,
    MAX_FILE_RESPONSE_SIZE,
    MAX_METADATA_RESPONSE_SIZE,
    MAX_TREE_RESPONSE_SIZE,
    fetch_file_content,
    filter_analyzable_files,
    is_text_file,
    parse_github_url,
)


class FakeStreamResponse:
    def __init__(
        self,
        body=b"",
        *,
        status_code=200,
        headers=None,
        chunks=None,
    ):
        self.status_code = status_code
        self.headers = headers or {}
        self.request = httpx.Request(
            "GET", "https://api.github.com/test"
        )
        self._body = body
        self._chunks = chunks if chunks is not None else [body]

    def raise_for_status(self):
        response = httpx.Response(
            self.status_code,
            headers=self.headers,
            request=self.request,
        )
        response.raise_for_status()

    def iter_bytes(self):
        yield from self._chunks


def install_stream_mock(monkeypatch, response):
    @contextmanager
    def fake_stream(*args, **kwargs):
        yield response

    monkeypatch.setattr(loader.httpx, "stream", fake_stream)


def make_json_response(data):
    import json

    return FakeStreamResponse(
        json.dumps(data).encode("utf-8"),
        headers={"content-type": "application/json"},
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


def test_parse_github_url_accepts_www_hostname():
    assert parse_github_url(
        "https://www.github.com/owner/repo"
    ) == ("owner", "repo")


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
        None,
    ]

    result = filter_analyzable_files(files)

    assert [file["path"] for file in result] == ["valid.py"]


def test_filter_analyzable_files_accepts_maximum_file_size():
    files = [{"path": "main.py", "size": MAX_FILE_SIZE}]

    assert filter_analyzable_files(files) == files


def test_fetch_file_content_rejects_invalid_base64(monkeypatch):
    response = make_json_response(
        {"encoding": "base64", "content": "%%%invalid%%%"}
    )
    install_stream_mock(monkeypatch, response)

    with pytest.raises(ValueError, match="Invalid Base64"):
        fetch_file_content("owner", "repo", "main.py")


def test_fetch_file_content_rejects_non_utf8(monkeypatch):
    response = make_json_response(
        {
            "encoding": "base64",
            "content": base64.b64encode(b"\xff").decode(),
        }
    )
    install_stream_mock(monkeypatch, response)

    with pytest.raises(ValueError, match="valid UTF-8"):
        fetch_file_content("owner", "repo", "main.py")


def test_fetch_file_content_rejects_oversized_content(monkeypatch):
    oversized = b"a" * (MAX_FILE_SIZE + 1)
    response = make_json_response(
        {
            "encoding": "base64",
            "content": base64.b64encode(oversized).decode(),
        }
    )
    install_stream_mock(monkeypatch, response)

    with pytest.raises(ValueError, match="exceeds"):
        fetch_file_content("owner", "repo", "main.py")


def test_fetch_file_content_accepts_valid_base64_with_whitespace(
    monkeypatch,
):
    response = make_json_response(
        {
            "encoding": "base64",
            "content": "aGVs\nbG8=\n",
        }
    )
    install_stream_mock(monkeypatch, response)

    assert fetch_file_content("owner", "repo", "main.py") == "hello"


def test_fetch_file_content_propagates_http_error(monkeypatch):
    response = FakeStreamResponse(status_code=403)
    install_stream_mock(monkeypatch, response)

    with pytest.raises(httpx.HTTPStatusError):
        fetch_file_content("owner", "repo", "main.py")


def test_repository_tree_rejects_truncated_response(monkeypatch):
    response = make_json_response(
        {"truncated": True, "tree": []}
    )
    install_stream_mock(monkeypatch, response)

    with pytest.raises(ValueError, match="too large"):
        loader.fetch_repository_tree("owner", "repo", "main")


def test_repository_tree_rejects_file_limit(monkeypatch):
    response = make_json_response(
        {
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
    )
    install_stream_mock(monkeypatch, response)

    with pytest.raises(ValueError, match="file limit"):
        loader.fetch_repository_tree("owner", "repo", "main")


def test_bounded_response_rejects_oversized_content_length(
    monkeypatch,
):
    response = FakeStreamResponse(
        b"",
        headers={"content-length": str(MAX_METADATA_RESPONSE_SIZE + 1)},
    )
    install_stream_mock(monkeypatch, response)

    with pytest.raises(ValueError, match="size limit"):
        loader.get_bounded_response(
            "https://api.github.com/test",
            max_response_size=MAX_METADATA_RESPONSE_SIZE,
            timeout=10,
        )


@pytest.mark.parametrize(
    ("limit", "constant"),
    [
        (MAX_METADATA_RESPONSE_SIZE, MAX_METADATA_RESPONSE_SIZE),
        (MAX_TREE_RESPONSE_SIZE, MAX_TREE_RESPONSE_SIZE),
        (MAX_FILE_RESPONSE_SIZE, MAX_FILE_RESPONSE_SIZE),
    ],
)
def test_response_limits_are_positive_and_configured(limit, constant):
    assert limit == constant
    assert limit > 0


def test_bounded_response_rejects_oversized_stream_without_length(
    monkeypatch,
):
    response = FakeStreamResponse(
        chunks=[b"a" * 8, b"b" * 8],
    )
    install_stream_mock(monkeypatch, response)

    with pytest.raises(ValueError, match="size limit"):
        loader.get_bounded_response(
            "https://api.github.com/test",
            max_response_size=10,
            timeout=10,
        )


def test_bounded_response_accepts_body_within_limit(monkeypatch):
    response = FakeStreamResponse(chunks=[b"hello", b" world"])
    install_stream_mock(monkeypatch, response)

    result = loader.get_bounded_response(
        "https://api.github.com/test",
        max_response_size=20,
        timeout=10,
    )

    assert result.content == b"hello world"


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
