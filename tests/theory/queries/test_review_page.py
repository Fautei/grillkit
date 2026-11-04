# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for TheoryReviewService."""

from unittest.mock import patch

from app.interview.repositories.uow import InterviewUnitOfWork
from app.platform.domain.config import AppConfig
from app.theory.queries.review_page import TheoryReviewPage
from tests.helpers.completed_session_seed import seed_completed_theory_interview


def test_theory_review_service_builds_chat_history(isolated_db) -> None:
    """Theory review exposes answered rounds and fallback section feedback."""
    interview_id = seed_completed_theory_interview()
    with InterviewUnitOfWork() as uow:
        context = TheoryReviewPage(uow).build_context_for(interview_id)
    assert context is not None
    assert len(context.answers) == 1
    assert context.answers[0].feedback == "Clear and concise."
    assert "Clear and concise." in context.section_feedback["section_feedback"]


def test_theory_review_context_reports_voice_disabled_by_default(isolated_db) -> None:
    """Answer playback flag is False when no voice config is present."""
    interview_id = seed_completed_theory_interview()
    with (
        patch(
            "app.theory.queries.review_page.ConfigService.get_config",
            return_value=None,
        ),
        InterviewUnitOfWork() as uow,
    ):
        context = TheoryReviewPage(uow).build_context_for(interview_id)
    assert context is not None
    assert context.question_voice_enabled is False


def test_theory_review_context_reports_voice_enabled(isolated_db) -> None:
    """Answer playback flag is True when question voice is enabled in config."""
    interview_id = seed_completed_theory_interview()
    config = AppConfig(
        provider_type="openai-compatible",
        base_url="http://localhost",
        model="gpt-4",
        question_voice_enabled=True,
    )
    with (
        patch(
            "app.theory.queries.review_page.ConfigService.get_config",
            return_value=config,
        ),
        InterviewUnitOfWork() as uow,
    ):
        context = TheoryReviewPage(uow).build_context_for(interview_id)
    assert context is not None
    assert context.question_voice_enabled is True


def test_theory_review_page_renders_history(client, isolated_db) -> None:
    """Theory review page renders chat history and section feedback."""
    interview_id = seed_completed_theory_interview("results-theory-page-1")
    response = client.get(f"/interview/{interview_id}/theory")
    assert response.status_code == 200
    assert "Conversation History" in response.text
    assert "A programming language" in response.text
    assert "Clear and concise." in response.text
