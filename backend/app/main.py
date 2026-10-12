
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

from backend.app.graph import RepositoryLoadError, analysis_graph


app = FastAPI(title="RepoPilot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


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
