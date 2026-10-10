
import json
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from backend.app.reviewer import review_engineering, review_recruiter
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
        evidence=[EvidenceReference(category="repository", metric="analyzable_file_count", value=3)],
        recommendation="Add automated tests for critical behavior.",
    )


def make_valid_analysis_report():
    evidence = EvidenceReference(category="repository", metric="analyzable_file_count", value=3)
    return AnalysisReport(
        repository_url="https://github.com/example/project",
        repository_name="project",
        engineering_review=ReviewResult(summary="Engineering review completed.", findings=[make_finding()]),
        recruiter_review=ReviewResult(summary="Recruiter review completed.", findings=[]),
        engineering_scores=ReviewScores(
            overall=70,
            components={"testing": ScoreComponent(score=70, rationale="Testing evidence needs improvement.")},
        ),
        recruiter_scores=ReviewScores(
            overall=75,
            components={"documentation": ScoreComponent(score=75, rationale="Documentation signals were evaluated.")},
        ),
        overall_score=73,
        recommendations=[
            Recommendation(
                id="REC-001",
                priority=Priority.HIGH,
                title="Add automated tests",
                action="Create automated tests for critical behavior.",
                rationale="The review identified a testing improvement.",
                finding_ids=["ENG-001"],
            )
        ],
        evidence=[evidence],
    )


def test_finding_requires_evidence():
    with pytest.raises(ValidationError):
        Finding(
            id="ENG-002", category="testing", severity="high", title="Missing tests",
            explanation="Testing evidence is absent.", evidence=[], recommendation="Add tests.",
        )


@pytest.mark.parametrize("score", [-1, 101])
def test_score_component_rejects_out_of_range_scores(score):
    with pytest.raises(ValidationError):
        ScoreComponent(score=score, rationale="Test score")


def test_score_component_accepts_valid_score():
    assert ScoreComponent(score=85, rationale="The score follows the defined evaluation criteria.").score == 85


def test_recommendation_must_reference_existing_finding():
    report = make_valid_analysis_report().model_dump()
    report["recommendations"][0]["finding_ids"] = ["UNKNOWN-001"]
    with pytest.raises(ValidationError, match="unknown finding IDs"):
        AnalysisReport.model_validate(report)


def test_finding_rejects_unexpected_fields():
    with pytest.raises(ValidationError):
        Finding(**{**make_finding().model_dump(), "invented_field": True})


def test_review_scores_reject_inconsistent_component_total():
    with pytest.raises(ValidationError, match="sum of component scores"):
        ReviewScores(
            overall=80,
            components={"testing": ScoreComponent(score=70, rationale="Testing needs improvement.")},
        )


def test_analysis_report_rejects_inconsistent_overall_score():
    report = make_valid_analysis_report().model_dump()
    report["overall_score"] = 80
    with pytest.raises(ValidationError, match="rounded average"):
        AnalysisReport.model_validate(report)


def test_analysis_report_rejects_evidence_missing_from_report():
    report = make_valid_analysis_report().model_dump()
    report["evidence"] = [{"category": "documentation", "metric": "documentation_file", "value": "README.md"}]
    with pytest.raises(ValidationError, match="evidence not included in the report"):
        AnalysisReport.model_validate(report)


def test_analysis_report_accepts_consistent_report():
    report = make_valid_analysis_report()
    assert report.overall_score == 73
    assert report.engineering_scores.overall == 70
    assert report.recruiter_scores.overall == 75
    assert report.recommendations[0].finding_ids == ["ENG-001"]


def test_analysis_report_rejects_duplicate_finding_ids():
    report = make_valid_analysis_report().model_dump()
    report["recruiter_review"]["findings"] = [report["engineering_review"]["findings"][0]]
    with pytest.raises(ValidationError, match="Duplicate finding ID"):
        AnalysisReport.model_validate(report)


def test_engineering_reviewer_validates_groq_response():
    response = MagicMock()
    response.choices[0].message.content = json.dumps({
        "summary": "Limited repository evidence.",
        "findings": [{
            "id": "ENG-001", "category": "documentation", "severity": "medium",
            "title": "Limited documentation evidence", "explanation": "The evidence set is small.",
            "evidence": [{"category": "repository", "metric": "analyzable_file_count", "value": 3}],
            "recommendation": "Review the project documentation.",
        }],
    })
    evidence = [{"category": "repository", "metric": "analyzable_file_count", "value": 3}]
    with patch("backend.app.reviewer.get_groq_api_key", return_value="test-key"), patch("backend.app.reviewer.Groq") as groq:
        groq.return_value.chat.completions.create.return_value = response
        result = review_engineering(evidence)
    assert result.summary == "Limited repository evidence."
    assert result.findings[0].id == "ENG-001"
    groq.return_value.chat.completions.create.assert_called_once()


def test_engineering_reviewer_rejects_empty_evidence():
    with pytest.raises(ValueError, match="Repository evidence is required"):
        review_engineering([])


def test_engineering_reviewer_rejects_invalid_response():
    response = MagicMock()
    response.choices[0].message.content = '{"summary":"Missing findings"}'
    with patch("backend.app.reviewer.get_groq_api_key", return_value="test-key"), patch("backend.app.reviewer.Groq") as groq:
        groq.return_value.chat.completions.create.return_value = response
        with pytest.raises(ValueError, match="invalid engineering review"):
            review_engineering([{"category": "repository", "metric": "file_count", "value": 3}])


def test_engineering_reviewer_rejects_unsupported_evidence():
    evidence = [{"category": "repository", "metric": "file_count", "value": 3}]
    response = {
        "summary": "Repository review completed.",
        "findings": [{
            "id": "ENG-001", "category": "testing", "severity": "medium",
            "title": "Insufficient test coverage", "explanation": "The repository may lack sufficient tests.",
            "evidence": [{"category": "repository", "metric": "file_count", "value": 999}],
            "recommendation": "Add appropriate automated tests.",
        }],
    }
    client = MagicMock()
    client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content=json.dumps(response)))
    ]
    with (
        patch("backend.app.reviewer.Groq", return_value=client),
        patch("backend.app.reviewer.get_groq_api_key", return_value="test-key"),
        pytest.raises(ValueError, match="unsupported evidence"),
    ):
        review_engineering(evidence)


def test_recruiter_reviewer_validates_groq_response():
    evidence = [{"category": "documentation", "metric": "readme_present", "value": True}]
    response = {
        "summary": "The repository includes a README.",
        "findings": [{
            "id": "REC-001", "category": "documentation", "severity": "info",
            "title": "README is present",
            "explanation": "A README is available to introduce the repository.",
            "evidence": [{"category": "documentation", "metric": "readme_present", "value": True}],
            "recommendation": "Ensure the README explains setup and project usage.",
        }],
    }
    client = MagicMock()
    client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content=json.dumps(response)))
    ]
    with (
        patch("backend.app.reviewer.Groq", return_value=client),
        patch("backend.app.reviewer.get_groq_api_key", return_value="test-key"),
    ):
        result = review_recruiter(evidence)
    assert result.summary == "The repository includes a README."
    assert len(result.findings) == 1
    assert result.findings[0].id == "REC-001"
    request = client.chat.completions.create.call_args.kwargs
    assert "recruiter" in request["messages"][0]["content"].lower()
