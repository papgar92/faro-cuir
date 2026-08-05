"""crear tabla documento

Revision ID: 0243743f134a
Revises: 15e7acd73e2b
Create Date: 2026-08-05 21:29:56.392023

Nota sobre el autogenerate: alembic propuso además dos `op.drop_constraint` sobre las CHECK
`tipofuente` y `formatofuente` de la tabla `fuente`. Es un falso positivo conocido al usar
`Enum(native_enum=False, create_constraint=True)`: alembic no reconstruye esas CHECK al
reflejar el esquema, así que las ve como sobrantes. Aplicarlo habría borrado en silencio la
validación de vocabulario a nivel de base de datos que se añadió a propósito en la migración
anterior. Se han eliminado a mano las dos líneas.

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0243743f134a"
down_revision: str | Sequence[str] | None = "15e7acd73e2b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "documento",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fuente_id", sa.Integer(), nullable=False),
        sa.Column("identificador_oficial", sa.String(length=200), nullable=False),
        sa.Column("fecha_publicacion", sa.Date(), nullable=False),
        sa.Column("url_original", sa.String(length=1000), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("sello_tiempo", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ruta_almacen", sa.String(length=300), nullable=False),
        sa.Column(
            "estado_pipeline",
            sa.Enum(
                "ingerido",
                "prefiltrado",
                "extraido",
                "clasificado",
                "descartado",
                "error",
                name="estadopipeline",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            server_default="ingerido",
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["fuente_id"], ["fuente.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fuente_id", "identificador_oficial", name="uq_documento_fuente_ident"),
    )
    op.create_index(
        op.f("ix_documento_estado_pipeline"), "documento", ["estado_pipeline"], unique=False
    )
    op.create_index(
        op.f("ix_documento_fecha_publicacion"), "documento", ["fecha_publicacion"], unique=False
    )
    op.create_index(op.f("ix_documento_fuente_id"), "documento", ["fuente_id"], unique=False)
    op.create_index(op.f("ix_documento_sha256"), "documento", ["sha256"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_documento_sha256"), table_name="documento")
    op.drop_index(op.f("ix_documento_fuente_id"), table_name="documento")
    op.drop_index(op.f("ix_documento_fecha_publicacion"), table_name="documento")
    op.drop_index(op.f("ix_documento_estado_pipeline"), table_name="documento")
    op.drop_table("documento")
