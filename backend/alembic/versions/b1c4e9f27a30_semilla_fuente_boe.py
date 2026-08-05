"""semilla de la fuente BOE

Revision ID: b1c4e9f27a30
Revises: 0243743f134a
Create Date: 2026-08-05 22:05:00.000000

Migración de datos, no de esquema. La fila del BOE va aquí y no en un script aparte para que
cualquier entorno (local, CI, despliegue) quede en el mismo estado con solo `alembic upgrade
head`, sin un paso manual que alguien pueda olvidar.

Los datos son exactamente los de `docs/fuentes.md`, la única fila verificada de la auditoría.
`licencia_reutil` queda a NULL porque en ese documento sigue marcada como TODO(verificar):
rellenarla aquí con lo que suene plausible sería inventarse una licencia (regla de oro 8).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1c4e9f27a30"
down_revision: str | Sequence[str] | None = "0243743f134a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NOMBRE = "Boletín Oficial del Estado"


def upgrade() -> None:
    """Upgrade schema."""
    fuente = sa.table(
        "fuente",
        sa.column("nombre", sa.String),
        sa.column("tipo", sa.String),
        sa.column("ccaa", sa.String),
        sa.column("formato", sa.String),
        sa.column("url_base", sa.String),
        sa.column("licencia_reutil", sa.String),
        sa.column("activa", sa.Boolean),
    )
    op.bulk_insert(
        fuente,
        [
            {
                "nombre": _NOMBRE,
                "tipo": "boe",
                # NULL: el BOE es fuente estatal, no autonómica.
                "ccaa": None,
                "formato": "api",
                "url_base": "https://www.boe.es/datosabiertos/api/boe/sumario/",
                "licencia_reutil": None,
                "activa": True,
            }
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sa.text("DELETE FROM fuente WHERE nombre = :nombre").bindparams(nombre=_NOMBRE))
