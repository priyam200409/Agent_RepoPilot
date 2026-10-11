
import pytest

from backend.app.github_loader import (
    MAX_FILE_SIZE,
    filter_analyzable_files,
    is_text_file,
    parse_github_url,
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
