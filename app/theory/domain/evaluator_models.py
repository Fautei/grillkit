# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Pydantic models for structured theory AI evaluation output."""

from pydantic import BaseModel, Field

from app.shared.evaluation_models import InterviewEvaluation, SectionEvaluation

__all__ = [
    "AnswerEvaluation",
    "AnswerGrammarAnalysis",
    "FollowUpEvaluation",
    "GrammarIssue",
    "InterviewEvaluation",
    "ModelAnswer",
    "QuestionClarification",
    "SectionEvaluation",
]


class AnswerEvaluation(BaseModel):
    """Evaluation of a single initial answer (round=0).

    Attributes:
        score: Rating 1-5.
        feedback: Detailed feedback on the answer.
        strengths: Key strengths demonstrated.
        weaknesses: Areas for improvement.
        follow_up_needed: Whether a follow-up question is needed.
        follow_up_question: The follow-up question text, if needed.
    """

    score: int = Field(..., ge=1, le=5, description="Rating 1-5")
    feedback: str = Field(..., description="Detailed feedback")
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    follow_up_needed: bool = Field(..., description="Whether a follow-up is needed")
    follow_up_question: str | None = Field(None, description="Follow-up question text")


class FollowUpEvaluation(BaseModel):
    """Evaluation of a follow-up answer (round >= 1).

    Attributes:
        score: Rating 1-5 for the follow-up.
        feedback: Detailed feedback.
        needs_further_follow_up: Whether another follow-up is needed.
        follow_up_question: Next follow-up question text, if needed.
    """

    score: int = Field(..., ge=1, le=5, description="Rating 1-5")
    feedback: str = Field(..., description="Detailed feedback")
    needs_further_follow_up: bool = Field(
        ..., description="Whether another follow-up is needed"
    )
    follow_up_question: str | None = Field(
        None, description="Next follow-up question text"
    )


class QuestionClarification(BaseModel):
    """AI clarification of an ambiguous interview question.

    Attributes:
        clarification: Reworded, unambiguous question text.
    """

    clarification: str = Field(
        ..., description="Reworded, unambiguous version of the question"
    )


class ModelAnswer(BaseModel):
    """AI-generated reference (model) answer for an interview question.

    Attributes:
        model_answer: Concise reference answer text.
    """

    model_answer: str = Field(
        ..., description="Concise reference answer covering the key points"
    )


class GrammarIssue(BaseModel):
    """One grammar/style problem in the candidate's answer.

    Attributes:
        excerpt: Verbatim substring copied from the answer that is incorrect.
        correction: The corrected replacement for ``excerpt``.
        note: Short optional explanation of the problem.
    """

    excerpt: str = Field(..., description="Exact substring of the answer to highlight")
    correction: str = Field(..., description="Corrected replacement for the excerpt")
    note: str | None = Field(None, description="Brief explanation, if useful")


class AnswerGrammarAnalysis(BaseModel):
    """Grammar-focused analysis of one answer for language training.

    Attributes:
        corrected_answer: Grammatically corrected version of the answer, used as
            the reference for highlighting and text-to-speech playback.
        issues: Ordered list of grammar issues with verbatim excerpts to highlight.
    """

    corrected_answer: str = Field(
        ..., description="Grammar-only corrected version of the answer text"
    )
    issues: list[GrammarIssue] = Field(
        default_factory=list,
        description="Grammar issues, each excerpt a verbatim substring of the answer",
    )
