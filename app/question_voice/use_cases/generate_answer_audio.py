# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Generate reference audio for a submitted theory answer."""

from pathlib import Path

from app.interview.queries.loader import InterviewQuery
from app.interview.schemas.interview import AnswerRead, InterviewRead
from app.platform.domain.config import ConfigService
from app.platform.domain.speech_settings import question_voice_settings_from_config
from app.shared.infrastructure.gateways.tts_cache import TtsCacheService
from app.shared.infrastructure.gateways.tts_exceptions import QuestionVoiceDisabledError
from app.speech.domain.tts_engine import TtsEngine


class GenerateAnswerAudio:
    """Orchestrate answer-audio synthesis for interview sessions."""

    @staticmethod
    async def execute(
        engine: TtsEngine,
        interview_id: str,
        answer_id: int,
    ) -> Path:
        """Return a WAV path for a submitted answer's reference audio.

        Args:
            engine: TTS engine used to synthesize audio.
            interview_id: Interview session UUID.
            answer_id: Answer row primary key to synthesize.

        Returns:
            Path to a cached or newly synthesized WAV file.

        Raises:
            QuestionVoiceDisabledError: When voice is disabled in config.
            ValueError: When the answer is missing, unanswered, or empty.
            QuestionVoiceSynthesisError: When synthesis cannot complete.
        """
        config = ConfigService.get_config()
        if config is None:
            raise QuestionVoiceDisabledError()
        voice_settings = question_voice_settings_from_config(config)
        if not voice_settings.enabled:
            raise QuestionVoiceDisabledError()

        interview = InterviewQuery.load(interview_id)
        if interview is None:
            raise ValueError(f"Interview not found: {interview_id}")
        answer = _resolve_answer(interview, answer_id)
        reference_text = (answer.corrected_answer or "").strip() or answer.answer_text
        return await TtsCacheService.get_or_fetch(
            engine,
            voice_settings.voice_id,
            interview.locale,
            reference_text or "",
        )


def _resolve_answer(
    interview: InterviewRead,
    answer_id: int,
) -> AnswerRead:
    """Pick the target answer row for audio synthesis.

    Args:
        interview: Interview read model with answers.
        answer_id: Answer primary key to synthesize.

    Returns:
        Answer read model with ``answer_text`` to synthesize.

    Raises:
        ValueError: If no suitable submitted answer exists.
    """
    for answer in interview.answers:
        if answer.id == answer_id:
            if not answer.answer_text or not answer.answer_text.strip():
                raise ValueError("Answer text is empty")
            return answer
    raise ValueError(f"Answer not found in interview: {answer_id}")
