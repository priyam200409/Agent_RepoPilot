from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvidenceReference(ContractModel):
    category: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    value: Any


class Finding(ContractModel):
    id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    severity: Severity
    title: str = Field(min_length=1, max_length=200)
    explanation: str = Field(min_length=1)
    evidence: list[EvidenceReference] = Field(min_length=1)
    recommendation: str = Field(min_length=1)


class ScoreComponent(ContractModel):
    score: int = Field(ge=0, le=100)
    rationale: str = Field(min_length=1)


class ReviewScores(ContractModel):
    overall: int = Field(ge=0, le=100)
    components: dict[str, ScoreComponent] = Field(min_length=1)


class Recommendation(ContractModel):
    id: str = Field(min_length=1)
    priority: Priority
    title: str = Field(min_length=1, max_length=200)
    action: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    finding_ids: list[str] = Field(min_length=1)


class ReviewResult(ContractModel):
    summary: str = Field(min_length=1)
    findings: list[Finding]


class AnalysisReport(ContractModel):
    repository_url: str = Field(min_length=1)
    repository_name: str = Field(min_length=1)
    engineering_review: ReviewResult
    recruiter_review: ReviewResult
    engineering_scores: ReviewScores
    recruiter_scores: ReviewScores
    overall_score: int = Field(ge=0, le=100)
    recommendations: list[Recommendation]
    evidence: list[EvidenceReference]
    status: str = "completed"

    @model_validator(mode="after")
    def validate_recommendation_references(self):
        finding_ids = {
            finding.id
            for review in (
                self.engineering_review,
                self.recruiter_review,
            )
            for finding in review.findings
        }

        for recommendation in self.recommendations:
            unknown_ids = set(recommendation.finding_ids) - finding_ids
            if unknown_ids:
                raise ValueError(
                    "Recommendation references unknown finding IDs: "
                    + ", ".join(sorted(unknown_ids))
                )

        return self