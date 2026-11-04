# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for POST /interview/{id}/theory/answer-grammar."""

from fastapi.testclient import TestClient

from app.interview.queries.loader import InterviewLoader as InterviewQuery
from tests.fakes import grammar_analysis_json
from tests.helpers.completed_session_seed import seed_completed_theory_interview


def test_answer_grammar_generates_and_returns_json(
    client: TestClient, isolated_db, override_ws_ai_provider
) -> None:
    """Endpoint runs grammar analysis and returns highlighting payload."""
    interview_id = seed_completed_theory_interview()
    reloaded = InterviewQuery.load(interview_id)
    assert reloaded is not None
    answer_id = reloaded.answers[0].id

    override_ws_ai_provider(
        client,
        [
            grammar_analysis_json(
                corrected_answer="A programming language.",
                issues=[
                    {
                        "excerpt": "language",
                        "correction": "language.",
                        "note": "missing period",
                    }
                ],
            )
        ],
    )

    response = client.post(
        f"/interview/{interview_id}/theory/answer-grammar",
        params={"answer_id": answer_id},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["corrected_answer"] == "A programming language."
    assert payload["grammar_issues"][0]["excerpt"] == "language"


def test_answer_grammar_second_call_uses_cache(
    client: TestClient, isolated_db, override_ws_ai_provider
) -> None:
    """A second call returns stored analysis without a provider reply."""
    interview_id = seed_completed_theory_interview("grammar-cache-1")
    reloaded = InterviewQuery.load(interview_id)
    assert reloaded is not None
    answer_id = reloaded.answers[0].id

    override_ws_ai_provider(
        client, [grammar_analysis_json(corrected_answer="A programming language.", issues=[])]
    )

    first = client.post(
        f"/interview/{interview_id}/theory/answer-grammar",
        params={"answer_id": answer_id},
    )
    assert first.status_code == 200

    second = client.post(
        f"/interview/{interview_id}/theory/answer-grammar",
        params={"answer_id": answer_id},
    )
    assert second.status_code == 200
    assert second.json()["corrected_answer"] == "A programming language."


def test_answer_grammar_missing_section_returns_404(
    client: TestClient, isolated_db
) -> None:
    """A nonexistent interview returns 404."""
    response = client.post(
        "/interview/does-not-exist/theory/answer-grammar",
        params={"answer_id": 1},
    )
    assert response.status_code == 404
