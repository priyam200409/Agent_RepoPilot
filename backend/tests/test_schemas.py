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

from unittest.mock import MagicMock, patch

from backend.app.reviewer import review_engineering


def test_engineering_reviewer_validates_groq_response():
    evidence = [
        {
            "category": "repository",
            "metric": "analyzable_file_count",
            "value": 3,
        }
    ]

    response = MagicMock()
    response.choices[0].message.content = (
        '{"summary":"Limited repository evidence.",'
        '"findings":[{'
        '"id":"ENG-001",'
        '"category":"documentation",'
        '"severity":"medium",'
        '"title":"Limited documentation evidence",'
        '"explanation":"The evidence set is small.",'
        '"evidence":[{'
        '"category":"repository",'
        '"metric":"analyzable_file_count",'
        '"value":3'
        '}],'
        '"recommendation":"Review the project documentation."'
        '}]}'
    )

    with patch("backend.app.reviewer.get_groq_api_key", return_value="test-key"):
        with patch("backend.app.reviewer.Groq") as groq:
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

    with patch("backend.app.reviewer.get_groq_api_key", return_value="test-key"):
        with patch("backend.app.reviewer.Groq") as groq:
            groq.return_value.chat.completions.create.return_value = response

            with pytest.raises(ValueError, match="invalid engineering review"):
                review_engineering([{"category": "repository", "metric": "file_count", "value": 3}])


def test_engineering_reviewer_rejects_unsupported_evidence():
    import json

    from unittest.mock import MagicMock, patch

    import pytest

    supplied_evidence = [
        {
            "category": "repository",
            "metric": "file_count",
            "value": 3,
        }
    ]

    fake_response = {
        "summary": "Repository review completed.",
        "findings": [
            {
                "id": "ENG-001",
                "category": "testing",
                "severity": "medium",
                "title": "Insufficient test coverage",
                "explanation": "The repository may lack sufficient tests.",
                "evidence": [
                    {
                        "category": "repository",
                        "metric": "file_count",
                        "value": 999,
                    }
                ],
                "recommendation": "Add appropriate automated tests.",
            }
        ],
    }

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices = [
        MagicMock(
            message=MagicMock(content=json.dumps(fake_response))
        )
    ]

    with (
        patch(
            "backend.app.reviewer.Groq",
            return_value=mock_client,
        ),
        patch(
            "backend.app.reviewer.get_groq_api_key",
            return_value="test-key",
        ),
        pytest.raises(
            ValueError,
            match="unsupported evidence",
        ),
    ):
        review_engineering(supplied_evidence)
