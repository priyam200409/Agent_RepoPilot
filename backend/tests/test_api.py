from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_health():
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_analyze_repository(monkeypatch):
    def mock_snapshot(url):
        class File:
            path = "main.py"
            size = 100

        class Snapshot:
            owner = "test-owner"
            repository = "test-repo"
            default_branch = "main"
            files = [File()]

        return Snapshot()

    monkeypatch.setattr(
        "backend.app.main.build_repository_snapshot",
        mock_snapshot,
    )

    response = client.post(
        "/api/analyze",
        json={"repository_url": "https://github.com/test-owner/test-repo"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "loaded"
    assert response.json()["repository"]["file_count"] == 1


def test_analyze_invalid_repository(monkeypatch):
    def mock_snapshot(url):
        raise ValueError("GitHub repository not found")

    monkeypatch.setattr(
        "backend.app.main.build_repository_snapshot",
        mock_snapshot,
    )

    response = client.post(
        "/api/analyze",
        json={"repository_url": "https://github.com/test-owner/missing"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "GitHub repository not found"}


def test_analyze_empty_url():
    response = client.post(
        "/api/analyze",
        json={"repository_url": ""},
    )

    assert response.status_code == 422