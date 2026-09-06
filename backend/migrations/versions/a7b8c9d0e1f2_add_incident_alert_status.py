"""Error.md H5: add operator triage state to incidents

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-09-03 00:00:00.000000

Alert acknowledge/resolve and the Forensics "Mark Resolved" button had no
server-side home, so they lived in per-component React state / localStorage
and never agreed across pages. `alert_status` (+ the two timestamps) makes
the triage state authoritative and lets MTTA use a real acknowledge time.
Existing rows backfill to 'open' (accurate — they were never triaged).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — add triage columns to incidents."""
    op.add_column('incidents', sa.Column('alert_status', sa.String(length=20), nullable=False, server_default='open'))
    op.add_column('incidents', sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('incidents', sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_incidents_alert_status', 'incidents', ['alert_status'], unique=False)


def downgrade() -> None:
    """Downgrade schema — drop triage columns."""
    op.drop_index('ix_incidents_alert_status', table_name='incidents')
    op.drop_column('incidents', 'resolved_at')
    op.drop_column('incidents', 'acknowledged_at')
    op.drop_column('incidents', 'alert_status')
