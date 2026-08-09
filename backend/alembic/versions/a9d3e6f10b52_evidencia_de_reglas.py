"""spans de evidencia en deteccion y versión del catálogo de reglas en norma

Revision ID: a9d3e6f10b52
Revises: e5a1c8b47f23
Create Date: 2026-08-09 21:10:00.000000

Implementa el ADR 0016: el clasificador deriva las supresiones del **texto archivado**, y 7.6
exige que cada veredicto emita `regla_aplicada` más los spans sobre los que se aplicó. La
columna `regla_aplicada` ya existía desde `7f8c9d354e09`; los spans no tenían dónde ir.

**ESCRITA A MANO, NO AUTOGENERADA**, como las cuatro anteriores. Esta no toca ninguna CHECK —
son cuatro columnas nullable— pero el autogenerate seguiría proponiendo borrar las CHECK ajenas
generadas por `Enum(native_enum=False, create_constraint=True)`, y ya ha propuesto borrar
`origenclasificacion` (ADR 0004) una vez. A mano el problema no puede ni presentarse.

Comprobación obligatoria tras aplicar: las CHECK del proyecto **siguen siendo 13**, ninguna se
añade y ninguna se pierde.

    SELECT conrelid::regclass, conname FROM pg_constraint
    WHERE contype='c' AND conrelid <> 0 ORDER BY 1,2;

Las cuatro columnas son nullable y sin `server_default` a propósito: NULL significa "todavía no
se ha pasado el catálogo por aquí", que es la verdad de todas las filas existentes. Rellenarlas
con un valor por defecto las haría indistinguibles de las evaluadas — el mismo error que
`formato` evitó en la migración `c7e1b4a9d052`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a9d3e6f10b52"
down_revision: str | Sequence[str] | None = "e5a1c8b47f23"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # JSONB y no JSON: es la misma variante que `extraccion_json` en el modelo, y aquí sí se
    # va a consultar por contenido (qué detecciones se produjeron con qué `version_reglas`)
    # cuando toque reevaluar tras subir el catálogo.
    op.add_column(
        "deteccion",
        sa.Column("evidencia_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("norma", sa.Column("reglas_version", sa.String(length=20), nullable=True))
    op.add_column("norma", sa.Column("reglas_version_texto", sa.String(length=20), nullable=True))
    op.add_column(
        "norma", sa.Column("reglas_evaluado_en", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("norma", "reglas_evaluado_en")
    op.drop_column("norma", "reglas_version_texto")
    op.drop_column("norma", "reglas_version")
    op.drop_column("deteccion", "evidencia_json")
