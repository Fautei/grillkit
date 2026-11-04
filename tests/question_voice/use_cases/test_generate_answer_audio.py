# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for answer-audio orchestration."""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.interview.schemas.interview import AnswerRead, InterviewRead
from app.platform.domain.config import AppConfig
from app.question_voice.use_cases.generate_answer_audio import (
    GenerateAnswerAudio,
    _resolve_answer,
)
from app.shared.infrastructure.gateways.tts_exceptions import QuestionVoiceDisabledError
from app.speech.domain.tts_engine import TtsEngine


def _engine():
    """Build a dummy TTS engine for orchestration tests."""
    return MagicMock(spec=TtsEngine)


def _make_answer(
    *,
    answer_id: int = 1,
    answer_text: str | None = "An answer.",
    corrected_answer: str | None = None,
) -> AnswerRead:
    """Build an AnswerRead for tests."""
    return AnswerRead(
        id=answer_id,
        question_id="q1",
        order=1,
        round=0,
        question_text="What is Python?",
        question_code=None,
        answer_text=answer_text,
        corrected_answer=corrected_answer,
        score=None,
        feedback=None,
        started_at=None,
    )


def _make_interview(answers: list[AnswerRead], status: str = "completed") -> InterviewRead:
    """Build an InterviewRead for tests."""
    return InterviewRead(
        id="test-interview-id",
        status=status,
        locale="en",
        selection_spec="{}",
        question_ids='["q1"]',
        question_count=len(answers),
        question_time_limit_seconds=None,
        answers=answers,
        score=None,
        overall_feedback=None,
        started_at=datetime.now(),
        completed_at=datetime.now(),
    )


class TestGenerateAnswerAudio:
    """Tests for GenerateAnswerAudio.execute."""

    @pytest.mark.asyncio
    async def test_raises_when_no_config(self):
        """Missing config raises QuestionVoiceDisabledError."""
        with (
            patch(
                "app.question_voice.use_cases.generate_answer_audio.ConfigService.get_config",
                return_value=None,
            ),
            pytest.raises(QuestionVoiceDisabledError),
        ):
            await GenerateAnswerAudio.execute(_engine(), "interview-id", answer_id=1)

    @pytest.mark.asyncio
    async def test_raises_when_voice_disabled(self):
        """Disabled voice raises QuestionVoiceDisabledError."""
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            question_voice_enabled=False,
        )
        with (
            patch(
                "app.question_voice.use_cases.generate_answer_audio.ConfigService.get_config",
                return_value=config,
            ),
            pytest.raises(QuestionVoiceDisabledError),
        ):
            await GenerateAnswerAudio.execute(_engine(), "interview-id", answer_id=1)

    @pytest.mark.asyncio
    async def test_returns_cached_path_for_answer_text(self):
        """Enabled voice returns WAV path synthesized from answer_text."""
        engine = _engine()
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            question_voice_enabled=True,
            tts_voice_id="en_US-lessac-medium",
            locale="en",
        )
        answer = _make_answer(answer_id=7, answer_text="Lists use square brackets.")
        interview = _make_interview([answer])
        cached_path = Path("/tmp/cache/answer.wav")

        with (
            patch(
                "app.question_voice.use_cases.generate_answer_audio.ConfigService.get_config",
                return_value=config,
            ),
            patch(
                "app.question_voice.use_cases.generate_answer_audio.InterviewQuery.load",
                return_value=interview,
            ),
            patch(
                "app.question_voice.use_cases.generate_answer_audio.TtsCacheService.get_or_fetch",
                new_callable=AsyncMock,
                return_value=cached_path,
            ) as mock_cache,
        ):
            result = await GenerateAnswerAudio.execute(
                engine, "interview-id", answer_id=7
            )

        assert result == cached_path
        mock_cache.assert_called_once_with(
            engine,
            "en_US-lessac-medium",
            "en",
            "Lists use square brackets.",
        )

    @pytest.mark.asyncio
    async def test_uses_corrected_answer_when_present(self):
        """Reference audio synthesizes the corrected answer when available."""
        engine = _engine()
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            question_voice_enabled=True,
            tts_voice_id="en_US-lessac-medium",
            locale="en",
        )
        answer = _make_answer(
            answer_id=7,
            answer_text="its a list",
            corrected_answer="It is a list.",
        )
        interview = _make_interview([answer])
        cached_path = Path("/tmp/cache/answer.wav")

        with (
            patch(
                "app.question_voice.use_cases.generate_answer_audio.ConfigService.get_config",
                return_value=config,
            ),
            patch(
                "app.question_voice.use_cases.generate_answer_audio.InterviewQuery.load",
                return_value=interview,
            ),
            patch(
                "app.question_voice.use_cases.generate_answer_audio.TtsCacheService.get_or_fetch",
                new_callable=AsyncMock,
                return_value=cached_path,
            ) as mock_cache,
        ):
            result = await GenerateAnswerAudio.execute(
                engine, "interview-id", answer_id=7
            )

        assert result == cached_path
        mock_cache.assert_called_once_with(
            engine,
            "en_US-lessac-medium",
            "en",
            "It is a list.",
        )

    @pytest.mark.asyncio
    async def test_raises_when_interview_missing(self):
        """Missing interview raises ValueError."""
        config = AppConfig(
            provider_type="openai-compatible",
            base_url="http://localhost",
            model="gpt-4",
            question_voice_enabled=True,
            tts_voice_id="en_US-lessac-medium",
            locale="en",
        )
        with (
            patch(
                "app.question_voice.use_cases.generate_answer_audio.ConfigService.get_config",
                return_value=config,
            ),
            patch(
                "app.question_voice.use_cases.generate_answer_audio.InterviewQuery.load",
                return_value=None,
            ),
            pytest.raises(ValueError, match="Interview not found"),
        ):
            await GenerateAnswerAudio.execute(_engine(), "missing-id", answer_id=1)


class TestResolveAnswer:
    """Tests for _resolve_answer helper."""

    def test_returns_matching_answer_by_id(self):
        """answer_id selects the matching submitted answer."""
        target = _make_answer(answer_id=2, answer_text="Second answer")
        interview = _make_interview([_make_answer(answer_id=1), target])
        result = _resolve_answer(interview, answer_id=2)
        assert result.id == 2
        assert result.answer_text == "Second answer"

    def test_raises_when_answer_not_found(self):
        """Unknown answer_id raises ValueError."""
        interview = _make_interview([_make_answer(answer_id=1)])
        with pytest.raises(ValueError, match="Answer not found"):
            _resolve_answer(interview, answer_id=99)

    def test_raises_when_answer_text_empty(self):
        """Empty or null answer_text raises ValueError."""
        empty = _make_answer(answer_id=1, answer_text="   ")
        interview = _make_interview([empty])
        with pytest.raises(ValueError, match="Answer text is empty"):
            _resolve_answer(interview, answer_id=1)

    def test_raises_when_answer_unanswered(self):
        """Null answer_text raises ValueError."""
        unanswered = _make_answer(answer_id=1, answer_text=None)
        interview = _make_interview([unanswered])
        with pytest.raises(ValueError, match="Answer text is empty"):
            _resolve_answer(interview, answer_id=1)
