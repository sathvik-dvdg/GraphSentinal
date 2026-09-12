"""N-03: add blockchain chain context columns to incidents

Adds blockchain_chain_id, blockchain_contract_address, and blockchain_block_number
to the incidents table.  These fields allow the forensics API to reconcile SQLite
blockchain_tx references against the currently active Ganache chain.

Pre-N-03 rows legitimately have NULL for all three fields — they were created
before chain context was collected, so NULL is the accurate state (not fabricated
historical data).

Revision ID: a1b2c3d4e5f6
Revises: d4295f4f8129
Create Date: 2026-08-29 12:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'd4295f4f8129'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — add three nullable blockchain context columns."""
    # All three columns are nullable so existing rows (which have no chain
    # context) are left with NULL rather than a fabricated default value.
    op.add_column('incidents', sa.Column('blockchain_chain_id', sa.Integer(), nullable=True))
    op.add_column('incidents', sa.Column('blockchain_contract_address', sa.String(length=45), nullable=True))
    op.add_column('incidents', sa.Column('blockchain_block_number', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema — remove the three blockchain context columns."""
    op.drop_column('incidents', 'blockchain_block_number')
    op.drop_column('incidents', 'blockchain_contract_address')
    op.drop_column('incidents', 'blockchain_chain_id')
