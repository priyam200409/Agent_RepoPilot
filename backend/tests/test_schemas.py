import pytest
from pydantic import ValidationError

from backend.app.schemas import (
    AnalysisReport,
    EvidenceReference,
    Finding,
    Priority,
    Recommendation,
    ReviewResult,
    ReviewScores,
    ScoreComponent,
    Severity,
)


def make_finding():
    return Finding(
        id="ENG-001",
        category="testing",
        severity=Severity.HIGH,
        title="No test evidence detected",
        explanation="The supplied evidence contains no test-file entry.",
        evidence=[
            EvidenceReference(
                category="repository",
                metric="analyzable_file_count",
                value=3,
            )
        ],
        recommendation="Add automated tests for critical behavior.",
    )


def test_finding_requires_evidence():
    with pytest.raises(ValidationError):
        Finding(
            id="ENG-002",
            category="testing",
            severity="high",
            title="Missing tests",
            explanation="Testing evidence is absent.",
            evidence=[],
            recommendation="Add tests.",
        )


@pytest.mark.parametrize("score", [-1, 101])
def test_score_component_rejects_out_of_range_scores(score):
    with pytest.raises(ValidationError):
        ScoreComponent(score=score, rationale="Test score")


def test_score_component_accepts_valid_score():
    component = ScoreComponent(
        score=85,
        rationale="The score follows the defined evaluation criteria.",
    )

    assert component.score == 85


def test_recommendation_must_reference_existing_finding():
    with pytest.raises(ValidationError, match="unknown finding IDs"):
        AnalysisReport(
            repository_url="https://github.com/example/project",
            repository_name="project",
            engineering_review=ReviewResult(
                summary="Engineering review",
                findings=[make_finding()],
            ),
            recruiter_review=ReviewResult(
                summary="Recruiter review",
                findings=[],
            ),
            engineering_scores=ReviewScores(
                overall=70,
                components={
                    "testing": ScoreComponent(
                        score=70,
                        rationale="Limited test evidence.",
                    )
                },
            ),
            recruiter_scores=ReviewScores(
                overall=75,
                components={
                    "clarity": ScoreComponent(
                        score=75,
                        rationale="Example evaluation.",
                    )
                },
            ),
            overall_score=73,
            recommendations=[
                Recommendation(
                    id="REC-001",
                    priority=Priority.HIGH,
                    title="Add tests",
                    action="Create automated tests.",
                    rationale="Improve reliability.",
                    finding_ids=["UNKNOWN-001"],
                )
            ],
            evidence=[
                EvidenceReference(
                    category="repository",
                    metric="analyzable_file_count",
                    value=3,
                )
            ],
        )


def test_finding_rejects_unexpected_fields():
    with pytest.raises(ValidationError):
        Finding(
            **{
                **make_finding().model_dump(),
                "invented_field": True,
            }
        )