# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for AnswerGrammarService lazy analysis and caching."""

import pytest

from app.interview.queries.loader import InterviewLoader as InterviewQuery
from app.interview.repositories.uow import InterviewUnitOfWork
from app.theory.use_cases.answer_grammar import AnswerGrammarService
from tests.fakes import FakeProvider, grammar_analysis_json
from tests.helpers.completed_session_seed import seed_completed_theory_interview


async def _analyze(interview_id: str, answer_id: int, provider: FakeProvider):
    """Run grammar analysis inside an explicit-commit UoW."""
    with InterviewUnitOfWork() as uow:
        return await AnswerGrammarService(uow).analyze(
            interview_id=interview_id,
            answer_id=answer_id,
            provider=provider,
        )


@pytest.mark.asyncio
async def test_analyze_persists_and_returns_grammar(isolated_db) -> None:
    """First analysis runs the LLM and stores corrected answer + issues."""
    interview_id = seed_completed_theory_interview()
    reloaded = InterviewQuery.load(interview_id)
    assert reloaded is not None
    answer_id = reloaded.answers[0].id

    provider = FakeProvider(
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
        ]
    )

    read = await _analyze(interview_id, answer_id, provider)
    assert read.corrected_answer == "A programming language."
    assert read.grammar_issues is not None
    assert read.grammar_issues[0]["excerpt"] == "language"

    after = InterviewQuery.load(interview_id)
    assert after is not None
    assert after.answers[0].corrected_answer == "A programming language."
    assert after.answers[0].grammar_issues is not None


@pytest.mark.asyncio
async def test_analyze_is_cached_on_second_call(isolated_db) -> None:
    """A second call returns stored analysis without hitting the provider."""
    interview_id = seed_completed_theory_interview()
    reloaded = InterviewQuery.load(interview_id)
    assert reloaded is not None
    answer_id = reloaded.answers[0].id

    first = FakeProvider(
        [grammar_analysis_json(corrected_answer="A programming language.", issues=[])]
    )
    await _analyze(interview_id, answer_id, first)

    second = FakeProvider([])
    read = await _analyze(interview_id, answer_id, second)
    assert read.corrected_answer == "A programming language."
    assert read.grammar_issues == []


@pytest.mark.asyncio
async def test_analyze_unknown_answer_raises(isolated_db) -> None:
    """An answer id not present in the interview raises ValueError."""
    interview_id = seed_completed_theory_interview()
    provider = FakeProvider([grammar_analysis_json(corrected_answer="x", issues=[])])
    with pytest.raises(ValueError, match="Answer not found"):
        await _analyze(interview_id, 999999, provider)
