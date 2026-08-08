"""estado sospecha y registro de ejes en el prefiltro

Revision ID: d4f2a8c61b90
Revises: c7e1b4a9d052
Create Date: 2026-08-08 17:40:00.000000

Tarea 0.b de CLAUDE.md. Implementa el prefiltro de tres ejes (7.3) y el cuarto estado (7.2).

**ESCRITA A MANO, NO AUTOGENERADA.** Igual que la c7e1b4a9d052, y aquí con más motivo: esta
migración toca `estadoprefiltro`, que es exactamente el tipo de CHECK que el autogenerate
propone borrar. CLAUDE.md lo avisa cuatro veces y dice "máxima atención ahí".

Comprobación obligatoria tras aplicar: las CHECK del proyecto **siguen siendo 12**
(`estadoprefiltro` se sustituye, no se suma), y `origenclasificacion` sigue viva.

    SELECT conrelid::regclass, conname FROM pg_constraint WHERE contype='c' ORDER BY 1,2;

**El valor `sospecha` no reevalúa nada por sí solo.** Las filas existentes conservan su estado;
lo que las obliga a reevaluarse es que `VERSION_VOCABULARIO` haya subido, que es el mecanismo
que ya existía (`worker.run --reprefiltrar`). Poner aquí un UPDATE masivo sería tomar una
decisión de pipeline dentro de una migración de esquema.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4f2a8c61b90"
down_revision: str | Sequence[str] | None = "c7e1b4a9d052"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ESTADOS_ANTES = ("pendiente", "relevante", "descartada")
_ESTADOS_AHORA = ("pendiente", "sospecha", "relevante", "descartada")


def _lista(valores: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in valores)


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("norma", sa.Column("prefiltro_ejes", sa.JSON(), nullable=True))
    op.add_column("norma", sa.Column("prefiltro_directos", sa.Integer(), nullable=True))
    op.add_column(
        "norma", sa.Column("prefiltro_version_watchlist", sa.String(length=20), nullable=True)
    )

    # Se SUSTITUYE la CHECK, no se añade otra: dos CHECK sobre la misma columna se cumplen en
    # AND, así que la vieja seguiría prohibiendo 'sospecha' y el fallo sería silencioso hasta
    # el primer INSERT con el valor nuevo.
    op.drop_constraint("estadoprefiltro", "norma", type_="check")
    op.create_check_constraint(
        "estadoprefiltro", "norma", f"prefiltro_estado IN ({_lista(_ESTADOS_AHORA)})"
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Antes de estrechar la CHECK hay que resolver las filas que ya usan el valor nuevo, o el
    # ALTER falla a mitad. Vuelven a `pendiente` y no a `descartada`: bajar de versión no puede
    # convertir "esto merecía una segunda mirada" en "esto está descartado" — sería perder
    # normas en silencio, que es el único fallo que este proyecto no se puede permitir.
    op.execute(
        sa.text(
            "UPDATE norma SET prefiltro_estado = 'pendiente' WHERE prefiltro_estado = 'sospecha'"
        )
    )

    op.drop_constraint("estadoprefiltro", "norma", type_="check")
    op.create_check_constraint(
        "estadoprefiltro", "norma", f"prefiltro_estado IN ({_lista(_ESTADOS_ANTES)})"
    )

    op.drop_column("norma", "prefiltro_version_watchlist")
    op.drop_column("norma", "prefiltro_directos")
    op.drop_column("norma", "prefiltro_ejes")
