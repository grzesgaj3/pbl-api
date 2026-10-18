"""add sensors table

Adds the ``sensors`` registry: one row per measuring station, linked to the
bridge that reported it. It is populated automatically on the first measurement
of a given ``sensor_id`` (first writer wins); readings count and last-seen time
are derived from ``measurements``. Targets MariaDB/InnoDB with utf8mb4, like the
rest of the schema.

Revision ID: 45df17cd9773
Revises: 177c0f1e8921
Create Date: 2026-10-18 19:04:22.291142

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '45df17cd9773'
down_revision: Union[str, Sequence[str], None] = '177c0f1e8921'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('sensors',
    sa.Column('id', sa.Integer().with_variant(sa.BigInteger(), 'mysql'), autoincrement=True, nullable=False),
    sa.Column('sensor_id', sa.String(length=64), nullable=False),
    sa.Column('bridge_id', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.ForeignKeyConstraint(['bridge_id'], ['bridges.bridge_id'], ),
    sa.PrimaryKeyConstraint('id'),
    mysql_charset='utf8mb4',
    mysql_collate='utf8mb4_unicode_ci'
    )
    op.create_index(op.f('ix_sensors_bridge_id'), 'sensors', ['bridge_id'], unique=False)
    op.create_index(op.f('ix_sensors_sensor_id'), 'sensors', ['sensor_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_sensors_sensor_id'), table_name='sensors')
    op.drop_index(op.f('ix_sensors_bridge_id'), table_name='sensors')
    op.drop_table('sensors')
