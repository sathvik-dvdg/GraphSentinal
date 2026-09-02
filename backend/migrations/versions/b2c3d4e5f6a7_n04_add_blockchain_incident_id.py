"""N-04: add blockchain_incident_id column to incidents

Adds blockchain_incident_id to the incidents table. This field stores the exact,
authoritative on-chain incident ID decoded from the mined transaction's IncidentLogged event.

Pre-N-04 rows legitimately have NULL — they were created before transaction-specific
event ID persistence was collected, so NULL is the accurate representation.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-29 14:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — add nullable blockchain_incident_id column."""
    op.add_column('incidents', sa.Column('blockchain_incident_id', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema — remove blockchain_incident_id column."""
    op.drop_column('incidents', 'blockchain_incident_id')
