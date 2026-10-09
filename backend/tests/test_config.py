import pytest

from backend.app.config import get_groq_api_key


def test_get_groq_api_key(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    assert get_groq_api_key() == "test-key"


def test_get_groq_api_key_strips_whitespace(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "  test-key  ")

    assert get_groq_api_key() == "test-key"


@pytest.mark.parametrize("value", ["", "   "])
def test_get_groq_api_key_rejects_empty_value(monkeypatch, value):
    monkeypatch.setenv("GROQ_API_KEY", value)

    with pytest.raises(RuntimeError, match="GROQ_API_KEY is not configured"):
        get_groq_api_key()


def test_get_groq_api_key_rejects_missing_variable(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="GROQ_API_KEY is not configured"):
        get_groq_api_key()