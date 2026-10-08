from backend.app.github_loader import (
    filter_analyzable_files,
    is_text_file,
    parse_github_url,
)


def test_parse_github_url():
    assert parse_github_url(
        "https://github.com/priyam200409/Agent_RepoPilot"
    ) == ("priyam200409", "Agent_RepoPilot")


def test_parse_github_url_rejects_invalid_host():
    try:
        parse_github_url("https://google.com/test")
        assert False
    except ValueError:
        assert True


def test_is_text_file():
    assert is_text_file("backend/app/main.py")
    assert is_text_file("Dockerfile")
    assert not is_text_file("assets/logo.png")


def test_filter_analyzable_files():
    files = [
        {"path": "main.py", "size": 100},
        {"path": "README.md", "size": 200},
        {"path": "image.png", "size": 100},
        {"path": "large.py", "size": 100 * 1024 + 1},
    ]

    result = filter_analyzable_files(files)

    assert [file["path"] for file in result] == [
        "main.py",
        "README.md",
    ]