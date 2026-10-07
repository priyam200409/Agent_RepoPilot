from urllib.parse import urlparse

from fastapi import FastAPI
from pydantic import BaseModel, field_validator


app = FastAPI(title="RepoPilot API")


class AnalyzeRequest(BaseModel):
    repository_url: str

    @field_validator("repository_url")
    @classmethod
    def validate_repository_url(cls, value: str) -> str:
        value = value.strip()
        parsed = urlparse(value)

        if (
            parsed.scheme not in {"http", "https"}
            or parsed.netloc != "github.com"
        ):
            raise ValueError("repository_url must be a valid GitHub URL")

        parts = [part for part in parsed.path.split("/") if part]

        if len(parts) != 2:
            raise ValueError(
                "repository_url must point to a GitHub repository"
            )

        return value.rstrip("/")


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/analyze")
def analyze_repository(request: AnalyzeRequest):
    return {
        "status": "accepted",
        "repository_url": request.repository_url,
    }