"""Error.md N2/H1: add self-healing telemetry columns to enforcement_actions

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-03 00:00:00.000000

The Self-Healing page (avg response time, edges cut, network stability bar)
was fully built in the UI but GET /api/v1/healing hardcoded duration_ms /
edges_severed / network_stability_* because the enforcement_actions table had
nowhere to store them. These nullable columns are populated at block time by
the block API and the GNN detection path; NULL on rows written before this
migration (accurate — that telemetry genuinely wasn't captured then).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — add nullable telemetry columns."""
    op.add_column('enforcement_actions', sa.Column('duration_ms', sa.Integer(), nullable=True))
    op.add_column('enforcement_actions', sa.Column('edges_severed', sa.Integer(), nullable=True))
    op.add_column('enforcement_actions', sa.Column('network_stability_before', sa.Integer(), nullable=True))
    op.add_column('enforcement_actions', sa.Column('network_stability_after', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema — drop telemetry columns."""
    op.drop_column('enforcement_actions', 'network_stability_after')
    op.drop_column('enforcement_actions', 'network_stability_before')
    op.drop_column('enforcement_actions', 'edges_severed')
    op.drop_column('enforcement_actions', 'duration_ms')
