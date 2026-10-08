from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator

from backend.app.github_loader import build_repository_snapshot


app = FastAPI(title="RepoPilot API")


class AnalyzeRequest(BaseModel):
    repository_url: str

    @field_validator("repository_url")
    @classmethod
    def validate_repository_url(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("repository_url cannot be empty")

        return value.rstrip("/")


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/analyze")
def analyze_repository(request: AnalyzeRequest):
    try:
        snapshot = build_repository_snapshot(request.repository_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "status": "loaded",
        "repository": {
            "owner": snapshot.owner,
            "name": snapshot.repository,
            "default_branch": snapshot.default_branch,
            "file_count": len(snapshot.files),
        },
        "files": [
            {
                "path": file.path,
                "size": file.size,
            }
            for file in snapshot.files
        ],
    }