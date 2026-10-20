"""initial schema: bridges, measurements, commands, sensors"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "177c0f1e8921"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bridges",
        sa.Column("id", sa.Integer().with_variant(sa.BigInteger(), "mysql"), autoincrement=True, nullable=False),
        sa.Column("bridge_id", sa.String(length=64), nullable=False),
        sa.Column("api_key_hash", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index(op.f("ix_bridges_bridge_id"), "bridges", ["bridge_id"], unique=True)

    op.create_table(
        "commands",
        sa.Column("id", sa.Integer().with_variant(sa.BigInteger(), "mysql"), autoincrement=True, nullable=False),
        sa.Column("bridge_id", sa.String(length=64), nullable=False),
        sa.Column("sensor_id", sa.String(length=64), nullable=True),
        sa.Column("command_type", sa.String(length=32), server_default="clean", nullable=False),
        sa.Column("payload", sa.String(length=255), nullable=False),
        sa.Column("status", sa.Enum("PENDING", "ACKNOWLEDGED", "REJECTED", name="command_status"), server_default="PENDING", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("responded_at", sa.DateTime(), nullable=True),
        sa.Column("response_note", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["bridge_id"], ["bridges.bridge_id"]),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_commands_bridge_status_created", "commands", ["bridge_id", "status", "created_at"], unique=False)

    op.create_table(
        "measurements",
        sa.Column("id", sa.Integer().with_variant(sa.BigInteger(), "mysql"), autoincrement=True, nullable=False),
        sa.Column("bridge_id", sa.String(length=64), nullable=False),
        sa.Column("sensor_id", sa.String(length=64), nullable=False),
        sa.Column("value_mm", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["bridge_id"], ["bridges.bridge_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sensor_id", "sent_at", name="uq_measurements_sensor_sent"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_measurements_bridge_sent", "measurements", ["bridge_id", "sent_at"], unique=False)

    op.create_table(
        "sensors",
        sa.Column("id", sa.Integer().with_variant(sa.BigInteger(), "mysql"), autoincrement=True, nullable=False),
        sa.Column("sensor_id", sa.String(length=64), nullable=False),
        sa.Column("bridge_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["bridge_id"], ["bridges.bridge_id"]),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index(op.f("ix_sensors_bridge_id"), "sensors", ["bridge_id"], unique=False)
    op.create_index(op.f("ix_sensors_sensor_id"), "sensors", ["sensor_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_sensors_sensor_id"), table_name="sensors")
    op.drop_index(op.f("ix_sensors_bridge_id"), table_name="sensors")
    op.drop_table("sensors")
    op.drop_index("ix_measurements_bridge_sent", table_name="measurements")
    op.drop_table("measurements")
    op.drop_index("ix_commands_bridge_status_created", table_name="commands")
    op.drop_table("commands")
    op.drop_index(op.f("ix_bridges_bridge_id"), table_name="bridges")
    op.drop_table("bridges")