
import json
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

    @model_validator(mode="after")
    def validate_component_total(self):
        component_total = sum(
            component.score
            for component in self.components.values()
        )

        if component_total != self.overall:
            raise ValueError(
                "Overall score must equal the sum of component scores"
            )

        return self


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


def _evidence_key(reference: EvidenceReference) -> tuple[str, str, str]:
    """Build a stable key for comparing evidence references."""
    try:
        return (
            reference.category,
            reference.metric,
            json.dumps(
                reference.value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Evidence value must be JSON serializable"
        ) from exc


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
    def validate_report_consistency(self):
        expected_overall = (
            self.engineering_scores.overall
            + self.recruiter_scores.overall
            + 1
        ) // 2

        if self.overall_score != expected_overall:
            raise ValueError(
                "Overall report score must equal the rounded average "
                "of engineering and recruiter scores"
            )

        finding_ids = set()
        report_evidence_keys = {
            _evidence_key(reference)
            for reference in self.evidence
        }

        for review in (
            self.engineering_review,
            self.recruiter_review,
        ):
            for finding in review.findings:
                if finding.id in finding_ids:
                    raise ValueError(
                        f"Duplicate finding ID: {finding.id}"
                    )

                finding_ids.add(finding.id)

                for reference in finding.evidence:
                    if _evidence_key(reference) not in report_evidence_keys:
                        raise ValueError(
                            "Finding references evidence not included "
                            f"in the report: {finding.id}"
                        )

        for recommendation in self.recommendations:
            unknown_ids = (
                set(recommendation.finding_ids) - finding_ids
            )

            if unknown_ids:
                raise ValueError(
                    "Recommendation references unknown finding IDs: "
                    + ", ".join(sorted(unknown_ids))
                )

        return self
