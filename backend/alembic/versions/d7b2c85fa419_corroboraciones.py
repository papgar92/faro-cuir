"""quién más lo ha dicho: corroboraciones externas del informe

Revision ID: d7b2c85fa419
Revises: c3a9e1f04b72
Create Date: 2026-08-20 21:55:00.000000

ADR 0025, segunda parte. Va en migración aparte y no dentro de la c3a9e1f04b72 porque aquella ya
está aplicada: reescribirla habría exigido bajar y volver a subir el esquema para ahorrar un
fichero, y en este proyecto una migración de más cuesta menos que una migración reescrita.

Qué guarda: lo que **organizaciones de referencia** —FELGTBI+, Amnistía Internacional,
ILGA-Europe— han documentado ya sobre el cambio que describe el informe, con su enlace.

Por qué es la columna que hace publicable un hallazgo sin revisión humana: sin ella, lo que se
enseñaría es la opinión de un asistente de IA. Con ella se enseñan dos hechos verificables por
separado y ninguno nuestro — que el cambio ocurrió (lo prueba el documento archivado con su
huella) y que alguien con nombre ya lo denunció (lo prueba el enlace).

`server_default` a lista vacía para que las filas existentes queden coherentes sin un UPDATE.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7b2c85fa419"
down_revision: str | Sequence[str] | None = "c3a9e1f04b72"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "informe_revision",
        sa.Column("corroboraciones", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("informe_revision", "corroboraciones")
