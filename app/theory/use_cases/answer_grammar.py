# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Generate and persist grammar analysis for a submitted theory answer.

Runs lazily on demand (not in the hot submission path) so LLM cost is only
incurred when the learner actually asks to review or play an answer.
"""

from __future__ import annotations

import logging

from app.ai.base import AIProvider
from app.interview.repositories.uow import InterviewUnitOfWork
from app.theory.domain.entities import TheoryTask
from app.theory.domain.evaluator import TheoryEvaluator
from app.theory.domain.evaluator_models import GrammarIssue
from app.theory.domain.exceptions import TheorySectionNotFoundError
from app.theory.repositories.mappers import theory_task_read_from_domain
from app.theory.schemas.theory import TheoryTaskRead

logger = logging.getLogger(__name__)


class AnswerGrammarService:
    """Produce grammar highlighting and a reference answer for one task round."""

    def __init__(self, uow: InterviewUnitOfWork) -> None:
        """Initialize with the active unit of work.

        Args:
            uow: Shared application unit of work for this request scope.
        """
        self._uow = uow

    async def analyze(
        self,
        *,
        interview_id: str,
        answer_id: int,
        provider: AIProvider,
    ) -> TheoryTaskRead:
        """Return a read model with grammar fields populated (cached when present).

        Args:
            interview_id: Parent interview UUID.
            answer_id: Answer row primary key to analyze.
            provider: AI provider for grammar analysis.

        Returns:
            Read model for the answer including corrected_answer and grammar_issues.

        Raises:
            TheorySectionNotFoundError: If the section does not exist.
            ValueError: If the answer is missing or empty.
        """
        section = self._uow.theory_sections.get_aggregate(interview_id)
        if section is None:
            raise TheorySectionNotFoundError(interview_id)
        task = self._find_task(section.tasks, answer_id)

        if task.answer_text is None or not task.answer_text.strip():
            raise ValueError(f"Answer has no text to analyze: {answer_id}")

        if task.grammar_issues is not None or task.corrected_answer is not None:
            return theory_task_read_from_domain(task)

        analysis = await TheoryEvaluator.analyze_answer_grammar(
            provider=provider,
            answer_text=task.answer_text,
            locale=section.locale,
        )
        issues = tuple(self._issue_to_row(issue) for issue in analysis.issues)
        corrected = analysis.corrected_answer.strip() or task.answer_text

        updated = section.with_grammar(answer_id, corrected, issues)
        self._uow.theory_sections.save_aggregate(updated)
        self._uow.commit()

        analyzed = self._find_task(updated.tasks, answer_id)
        return theory_task_read_from_domain(analyzed)

    @staticmethod
    def _find_task(tasks: tuple[TheoryTask, ...], answer_id: int) -> TheoryTask:
        """Return the task row matching ``answer_id``.

        Args:
            tasks: Theory task rows for the section.
            answer_id: Answer row primary key.

        Returns:
            The matching domain theory task.

        Raises:
            ValueError: If no task has the given id.
        """
        for task in tasks:
            if task.id == answer_id:
                return task
        raise ValueError(f"Answer not found in interview: {answer_id}")

    @staticmethod
    def _issue_to_row(issue: GrammarIssue) -> dict[str, str]:
        """Serialize one grammar issue into a storage row.

        Args:
            issue: Parsed GrammarIssue model instance.

        Returns:
            Dict with excerpt, correction, and note string values.
        """
        return {
            "excerpt": issue.excerpt,
            "correction": issue.correction,
            "note": issue.note or "",
        }
