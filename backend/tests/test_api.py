
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas import ReviewResult


client = TestClient(app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_analyze_repository(monkeypatch):
    class File:
        path = "main.py"
        size = 100
        content = "print('hello')"

    class Snapshot:
        owner = "test-owner"
        repository = "test-repo"
        default_branch = "main"
        files = [File()]

    monkeypatch.setattr(
        "backend.app.graph.build_repository_snapshot",
        lambda url: Snapshot(),
    )
    review = ReviewResult(summary="Review completed.", findings=[])

    with (
        patch("backend.app.graph.review_engineering", return_value=review),
        patch("backend.app.graph.review_recruiter", return_value=review),
    ):
        response = client.post(
            "/api/analyze",
            json={"repository_url": "https://github.com/test-owner/test-repo"},
        )

    assert response.status_code == 200
    report = response.json()
    assert report["status"] == "completed"
    assert report["repository_name"] == "test-repo"
    assert "engineering_review" in report
    assert "recruiter_review" in report
    assert "engineering_scores" in report
    assert "recommendations" in report


def test_analyze_invalid_repository(monkeypatch):
    def fail_loading(url):
        raise ValueError("GitHub repository not found")

    monkeypatch.setattr(
        "backend.app.graph.build_repository_snapshot",
        fail_loading,
    )
    response = client.post(
        "/api/analyze",
        json={"repository_url": "https://github.com/test-owner/missing"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "GitHub repository not found"}


def test_analyze_empty_url():
    response = client.post("/api/analyze", json={"repository_url": ""})
    assert response.status_code == 422
