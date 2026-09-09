"""semilla de la fuente BOPV: la quinta autonómica y la sexta del proyecto

Revision ID: b3d5f80a1c47
Revises: a7c1e94b2d38
Create Date: 2026-09-06 16:00:00.000000

ADR 0035. Da de alta el Boletín Oficial del País Vasco como **sexta fuente del proyecto y quinta
autonómica**, activa, igual que hicieron `c8a41d7e5f02` (DOGC), `e3f7a1c92b64` (BOA),
`f4a8d21e7c93` (BOCYL) y `a7c1e94b2d38` (BOCM).

**Con esta se agota el guardarraíl ampliado de CLAUDE.md sección 8**, que el humano subió de 5 a
6 el 2026-09-06. La séptima necesita otra decisión suya, no otra migración.

**ESCRITA A MANO, NO AUTOGENERADA.** No toca ninguna CHECK ni ninguna columna: es solo un
INSERT, así que el recuento de CHECK del proyecto **no cambia** al aplicarla (hoy 15; el
`SELECT ... FROM pg_constraint` de CLAUDE.md sección 10 debe dar lo mismo antes y después).

`formato='api'`: sumario y cuerpo son XML. La resolución fecha → edición pasa por un fichero de
calendario que es HTML con dos arrays de JavaScript dentro (ADR 0035), pero de ahí no sale ni un
carácter de articulado: solo el nombre del fichero del sumario. Misma raya que el ADR 0029 trazó
para el BOCYL, y por eso el valor sigue describiendo la vía por la que entra el texto que el
sistema analiza y cita.

**La licencia se deja en `TODO(verificar)`, no se deduce** (regla de oro 8). No se localizó una
declaración de reutilización en la comprobación del 2026-09-06.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3d5f80a1c47"
down_revision: str | Sequence[str] | None = "a7c1e94b2d38"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NOMBRE = "Boletín Oficial del País Vasco"


def upgrade() -> None:
    """Upgrade schema."""
    fuente = sa.table(
        "fuente",
        sa.column("nombre", sa.String),
        sa.column("tipo", sa.String),
        sa.column("ccaa", sa.String),
        sa.column("ambito_territorial", sa.String),
        sa.column("ccaa_codigo", sa.String),
        sa.column("provincia", sa.String),
        sa.column("formato", sa.String),
        sa.column("url_base", sa.String),
        sa.column("licencia_reutil", sa.String),
        sa.column("activa", sa.Boolean),
    )
    op.execute(
        fuente.insert().values(
            nombre=_NOMBRE,
            tipo="boletin_autonomico",
            ccaa="País Vasco",
            ambito_territorial="autonomico",
            # ISO 3166-2:ES, el mismo eje por el que cruza el mapa, y la clave con la que
            # `worker/run.py` elige la fila. Si no cuadrara con la tabla `FUENTES`, el worker
            # archivaría el BOPV bajo otro boletín.
            ccaa_codigo="PV",
            provincia=None,
            formato="api",
            url_base="https://www.euskadi.eus/bopv2/datos/",
            licencia_reutil="TODO(verificar)",
            activa=True,
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Solo la fila de la fuente. **Los documentos y normas ingeridos NO se borran**: son archivo
    # con su huella y su sello (6.5), y una bajada de versión de esquema no es motivo para
    # destruir lo que se archivó. Si la FK lo impide, es que hay datos, y entonces el borrado
    # tiene que decidirlo una persona mirándolos.
    op.execute(sa.text("DELETE FROM fuente WHERE nombre = :nombre").bindparams(nombre=_NOMBRE))
