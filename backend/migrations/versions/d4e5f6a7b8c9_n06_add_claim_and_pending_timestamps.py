"""N-06: add blockchain_claimed_at and blockchain_pending_since to incidents

Adds blockchain_claimed_at and blockchain_pending_since to the incidents table.
These fields enable atomic outbox claim leasing and pending transaction timeout tracking.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-29 15:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — add nullable claim and pending timestamp columns."""
    op.add_column('incidents', sa.Column('blockchain_claimed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('incidents', sa.Column('blockchain_pending_since', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema — remove claim and pending timestamp columns."""
    op.drop_column('incidents', 'blockchain_pending_since')
    op.drop_column('incidents', 'blockchain_claimed_at')
