"""crear tabla fuente

Revision ID: 15e7acd73e2b
Revises:
Create Date: 2026-08-04 23:08:45.406599

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "15e7acd73e2b"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "fuente",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=200), nullable=False),
        sa.Column(
            "tipo",
            sa.Enum(
                "boe",
                "boletin_autonomico",
                "parlamento",
                name="tipofuente",
                native_enum=False,
                create_constraint=True,
                length=30,
            ),
            nullable=False,
        ),
        sa.Column("ccaa", sa.String(length=100), nullable=True),
        sa.Column(
            "formato",
            sa.Enum(
                "api",
                "rss",
                "html",
                "pdf",
                name="formatofuente",
                native_enum=False,
                create_constraint=True,
                length=10,
            ),
            nullable=False,
        ),
        sa.Column("url_base", sa.String(length=500), nullable=False),
        sa.Column("licencia_reutil", sa.String(length=200), nullable=True),
        sa.Column("activa", sa.Boolean(), server_default="true", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("fuente")
