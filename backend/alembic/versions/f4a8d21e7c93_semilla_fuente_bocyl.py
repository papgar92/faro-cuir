"""semilla de la fuente BOCYL: la tercera autonómica

Revision ID: f4a8d21e7c93
Revises: e3f7a1c92b64
Create Date: 2026-08-29 15:00:00.000000

ADR 0029. Da de alta el Boletín Oficial de Castilla y León como **cuarta fuente del proyecto y
tercera autonómica**, activa, igual que hicieron `c8a41d7e5f02` (DOGC) y `e3f7a1c92b64` (BOA).

Con esta, el proyecto llega a **cuatro fuentes integradas**: queda **una** dentro del límite de
cinco de la primera iteración (CLAUDE.md sección 8).

**ESCRITA A MANO, NO AUTOGENERADA.** No toca ninguna CHECK ni ninguna columna: es solo un
INSERT, así que el recuento de CHECK del proyecto **no cambia** al aplicarla (hoy 15; el
`SELECT ... FROM pg_constraint` de CLAUDE.md sección 10 debe dar lo mismo antes y después).

`formato='api'` con un matiz que conviene no perder: el **cuerpo** es XML estructurado y
direccionable por identificador —eso es una interfaz de datos—, pero el **sumario** hay que
leerlo de HTML. Se anota `api` porque es lo que describe la vía por la que entra el texto que el
sistema analiza y cita; el raspado del sumario está documentado en el ADR 0029 y en
`docs/fuentes.md`, no escondido detrás de este valor.

**La licencia se deja en `TODO(verificar)`, no se deduce** (regla de oro 8). A diferencia del
DOGC y del BOA, cuyos catálogos de datos abiertos declaran CC BY 4.0, no se localizó una
declaración de reutilización del BOCYL. Inventarla sería peor que no tenerla.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f4a8d21e7c93"
down_revision: str | Sequence[str] | None = "e3f7a1c92b64"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NOMBRE = "Boletín Oficial de Castilla y León"


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
            ccaa="Castilla y León",
            ambito_territorial="autonomico",
            # ISO 3166-2:ES, el mismo eje por el que cruza el mapa, y la clave con la que
            # `worker/run.py` elige la fila. Si no cuadrara con la tabla `FUENTES`, el worker
            # archivaría el BOCYL bajo otro boletín.
            ccaa_codigo="CL",
            provincia=None,
            formato="api",
            url_base="https://bocyl.jcyl.es/",
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
