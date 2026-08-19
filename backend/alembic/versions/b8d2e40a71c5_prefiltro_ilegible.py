"""quinto estado del prefiltro: ilegible

Revision ID: b8d2e40a71c5
Revises: e7c2a45b91d3
Create Date: 2026-08-18 17:10:00.000000

ADR 0020. Una norma cuyo cuerpo está archivado y el pipeline no puede parsear se queda hoy en
`pendiente`, o sea indistinguible de "esperando su texto íntegro". Medido el 2026-08-18 sobre el
DOGC: **172 de 264 normas** en esa situación, el 65 % de la segunda fuente del proyecto.

**ESCRITA A MANO, NO AUTOGENERADA.** Igual que la d4f2a8c61b90, que añadió `sospecha`, y por el
mismo motivo: el autogenerate propone borrar las CHECK ajenas cuando toca `estadoprefiltro`.
CLAUDE.md lo avisa cuatro veces.

Comprobación obligatoria tras aplicar: las CHECK del proyecto **siguen siendo 14**
(`estadoprefiltro` se sustituye, no se suma), y `origenclasificacion` sigue viva.

    SELECT conrelid::regclass, conname FROM pg_constraint
    WHERE contype='c' AND conrelid <> 0 ORDER BY 1,2;

**Sin UPDATE masivo**, mismo criterio que la d4f2a8c61b90: quién es ilegible lo decide el
pipeline leyendo el almacén, no una migración de esquema escribiendo a ciegas. Las 172 filas
reciben su estado en la primera pasada de `worker.run --reprefiltrar`, y lo reciben sin ayuda
porque ya están en la cola de reevaluación (tienen `documento_texto_id` y
`prefiltro_version_texto IS NULL`).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8d2e40a71c5"
down_revision: str | Sequence[str] | None = "e7c2a45b91d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ESTADOS_ANTES = ("pendiente", "sospecha", "relevante", "descartada")
_ESTADOS_AHORA = ("pendiente", "sospecha", "relevante", "descartada", "ilegible")


def _lista(valores: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in valores)


def upgrade() -> None:
    """Upgrade schema."""
    # Se SUSTITUYE la CHECK, no se añade otra: dos CHECK sobre la misma columna se cumplen en
    # AND, así que la vieja seguiría prohibiendo 'ilegible' y el fallo sería silencioso hasta
    # el primer UPDATE con el valor nuevo.
    op.drop_constraint("estadoprefiltro", "norma", type_="check")
    op.create_check_constraint(
        "estadoprefiltro", "norma", f"prefiltro_estado IN ({_lista(_ESTADOS_AHORA)})"
    )


def downgrade() -> None:
    """Downgrade schema."""
    # A `pendiente` y no a `descartada`, igual que hizo la d4f2a8c61b90 con `sospecha`: bajar de
    # versión no puede convertir "el sistema no puede leer esto" en "esto no nos afecta". Sería
    # perder normas en silencio, que es el único fallo que este proyecto no se permite. Vuelven
    # a ser indistinguibles de las que esperan su cuerpo — que es justo el problema que el ADR
    # 0020 arregla, y por eso bajar de esta versión es perder información, no solo esquema.
    conexion = op.get_bind()
    # Se cuenta ANTES de tocar nada y se dice por el log. La advertencia de arriba solo la lee
    # quien abre el fichero; quien ejecuta `alembic downgrade` merece ver cuántas filas pierden
    # la distinción, que es información que este downgrade destruye y no puede devolver.
    afectadas = conexion.execute(
        sa.text("SELECT count(*) FROM norma WHERE prefiltro_estado = 'ilegible'")
    ).scalar_one()
    if afectadas:
        print(
            f"AVISO: {afectadas} normas pasan de 'ilegible' a 'pendiente'. Se pierde la "
            "distincion entre 'falta descargarlo' y 'esta descargado y no se puede leer'."
        )
    op.execute(
        sa.text(
            "UPDATE norma SET prefiltro_estado = 'pendiente' WHERE prefiltro_estado = 'ilegible'"
        )
    )

    op.drop_constraint("estadoprefiltro", "norma", type_="check")
    op.create_check_constraint(
        "estadoprefiltro", "norma", f"prefiltro_estado IN ({_lista(_ESTADOS_ANTES)})"
    )
