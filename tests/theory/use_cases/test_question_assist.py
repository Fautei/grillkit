# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for SubmitTheoryAnswer question assist (clarification and hint)."""

import pytest

from app.interview.domain.events import EvaluatingEvent, QuestionAssistEvent
from app.interview.domain.exceptions import InterviewNotActiveError
from app.interview.queries.loader import InterviewLoader as InterviewQuery
from app.interview.repositories.uow import InterviewUnitOfWork
from app.shared.infrastructure.models import Answer, Interview
from app.theory.domain.exceptions import (
    TheorySectionNotFoundError,
    UnansweredTaskNotFoundError,
)
from app.theory.use_cases.submit_answer import SubmitTheoryAnswer
from tests.helpers.interview_seed import (
    persist_interview_with_answers,
    seed_two_question_interview,
)
from tests.helpers.selection import minimal_selection_spec

CLARIFICATION_JSON = (
    '{"clarification": "What is the difference between a list and a tuple?"}'
)
MODEL_ANSWER_JSON = '{"model_answer": "Lists are mutable, tuples are immutable."}'


async def _process_question_assist(**kwargs):
    """Run question assist inside an auto-commit UoW."""
    with InterviewUnitOfWork(auto_commit=True) as uow:
        service = SubmitTheoryAnswer(uow)
        return [event async for event in service.stream_question_assist(**kwargs)]


@pytest.mark.asyncio
async def test_question_assist_clarification(isolated_db, fake_ai_provider):
    """Clarification is generated without consuming the open round."""
    interview_id = seed_two_question_interview()
    provider = fake_ai_provider([CLARIFICATION_JSON])

    events = await _process_question_assist(
        interview_id=interview_id,
        question_id="q1",
        kind="clarification",
        provider=provider,
    )

    assert [type(e) for e in events] == [EvaluatingEvent, QuestionAssistEvent]
    assist = events[1]
    assert isinstance(assist, QuestionAssistEvent)
    assert assist.kind == "clarification"
    assert assist.question_id == "q1"
    assert assist.text == "What is the difference between a list and a tuple?"

    reloaded = InterviewQuery.load(interview_id)
    assert reloaded is not None
    q1 = next(a for a in reloaded.answers if a.question_id == "q1")
    assert q1.answer_text is None
    assert q1.score is None
    assert len(reloaded.answers) == 2


@pytest.mark.asyncio
async def test_question_assist_model_answer(isolated_db, fake_ai_provider):
    """Model answer hint is generated without consuming the open round."""
    interview_id = seed_two_question_interview("qa-hint-1")
    provider = fake_ai_provider([MODEL_ANSWER_JSON])

    events = await _process_question_assist(
        interview_id=interview_id,
        question_id="q2",
        kind="hint",
        provider=provider,
    )

    assert [type(e) for e in events] == [EvaluatingEvent, QuestionAssistEvent]
    assist = events[1]
    assert isinstance(assist, QuestionAssistEvent)
    assert assist.kind == "hint"
    assert assist.question_id == "q2"
    assert assist.text == "Lists are mutable, tuples are immutable."

    reloaded = InterviewQuery.load(interview_id)
    assert reloaded is not None
    q2 = next(a for a in reloaded.answers if a.question_id == "q2")
    assert q2.answer_text is None


@pytest.mark.asyncio
async def test_question_assist_repeated_request_keeps_round_open(
    isolated_db, fake_ai_provider
):
    """Multiple assist requests do not create extra task rows."""
    interview_id = seed_two_question_interview("qa-repeat-1")
    provider = fake_ai_provider([CLARIFICATION_JSON, MODEL_ANSWER_JSON, CLARIFICATION_JSON])

    for _ in range(3):
        await _process_question_assist(
            interview_id=interview_id,
            question_id="q1",
            kind="clarification",
            provider=provider,
        )

    reloaded = InterviewQuery.load(interview_id)
    assert reloaded is not None
    assert len(reloaded.answers) == 2
    q1 = next(a for a in reloaded.answers if a.question_id == "q1")
    assert q1.answer_text is None


@pytest.mark.asyncio
async def test_question_assist_answered_question_rejected(isolated_db):
    """Assist is rejected when the question has no open round."""
    interview_id = persist_interview_with_answers(
        Interview(
            id="qa-answered-1",
            locale="en",
            selection_spec=minimal_selection_spec(categories=["basics"]),
            status="active",
        ),
        [
            Answer(
                question_id="q1",
                order=1,
                round=0,
                question_text="Question one?",
                answer_text="Already answered.",
            ),
        ],
        question_count=1,
    )

    with pytest.raises(UnansweredTaskNotFoundError):
        await _process_question_assist(
            interview_id=interview_id,
            question_id="q1",
            kind="clarification",
            provider=object(),
        )


@pytest.mark.asyncio
async def test_question_assist_completed_interview_rejected(isolated_db):
    """Assist is rejected for a completed interview."""
    interview_id = persist_interview_with_answers(
        Interview(
            id="qa-completed-1",
            locale="en",
            selection_spec=minimal_selection_spec(categories=["basics"]),
            status="completed",
        ),
        [
            Answer(
                question_id="q1",
                order=1,
                round=0,
                question_text="Question one?",
            ),
        ],
        question_count=1,
    )

    with pytest.raises(InterviewNotActiveError):
        await _process_question_assist(
            interview_id=interview_id,
            question_id="q1",
            kind="hint",
            provider=object(),
        )


@pytest.mark.asyncio
async def test_question_assist_missing_section_rejected(isolated_db):
    """Assist is rejected when the interview has no theory section."""
    with InterviewUnitOfWork(auto_commit=True) as uow:
        uow.interviews.add(
            Interview(
                id="qa-no-section",
                locale="en",
                selection_spec=minimal_selection_spec(categories=["basics"]),
                status="active",
            )
        )

    with pytest.raises(TheorySectionNotFoundError):
        await _process_question_assist(
            interview_id="qa-no-section",
            question_id="q1",
            kind="clarification",
            provider=object(),
        )
