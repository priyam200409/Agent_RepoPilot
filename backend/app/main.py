
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator

from backend.app.graph import RepositoryLoadError, analysis_graph


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
        result = analysis_graph.invoke({
            "repository_url": request.repository_url,
        })
    except RepositoryLoadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return result["report"]
