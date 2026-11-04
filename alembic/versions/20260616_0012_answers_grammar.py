# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Add grammar-analysis columns (corrected_answer, grammar_issues) to answers."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260616_0012"
down_revision: str | None = "20260615_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Store grammar analysis and reference answer on each theory answer row."""
    with op.batch_alter_table("answers") as batch_op:
        batch_op.add_column(sa.Column("corrected_answer", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("grammar_issues", sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove grammar columns from answers."""
    with op.batch_alter_table("answers") as batch_op:
        batch_op.drop_column("corrected_answer")
        batch_op.drop_column("grammar_issues")
