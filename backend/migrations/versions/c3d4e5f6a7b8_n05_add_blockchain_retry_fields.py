"""N-05: add blockchain outbox and retry fields to incidents

Adds blockchain_status, blockchain_retry_count, and blockchain_last_error to the incidents table.
These fields enable persistent outbox retry and tracking for pending/failed blockchain operations.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-29 14:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — add nullable blockchain outbox tracking columns."""
    op.add_column('incidents', sa.Column('blockchain_status', sa.String(length=30), nullable=True))
    op.add_column('incidents', sa.Column('blockchain_retry_count', sa.Integer(), server_default='0', nullable=True))
    op.add_column('incidents', sa.Column('blockchain_last_error', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema — remove blockchain outbox tracking columns."""
    op.drop_column('incidents', 'blockchain_last_error')
    op.drop_column('incidents', 'blockchain_retry_count')
    op.drop_column('incidents', 'blockchain_status')
