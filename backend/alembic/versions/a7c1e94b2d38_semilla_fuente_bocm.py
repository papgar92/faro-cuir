"""semilla de la fuente BOCM: la cuarta autonómica, y la primera con nivel local dentro

Revision ID: a7c1e94b2d38
Revises: f4a8d21e7c93
Create Date: 2026-09-06 12:00:00.000000

ADR 0034. Da de alta el Boletín Oficial de la Comunidad de Madrid como **quinta fuente del
proyecto y cuarta autonómica**, activa, igual que hicieron `c8a41d7e5f02` (DOGC),
`e3f7a1c92b64` (BOA) y `f4a8d21e7c93` (BOCYL).

Con esta, el proyecto llega a **cinco fuentes integradas**: el límite de la primera iteración de
CLAUDE.md sección 8 queda **agotado**. La sexta (ADR 0035) va con la ampliación de ese
guardarraíl pedida por el humano el 2026-09-06, escrita en la propia sección 8.

**ESCRITA A MANO, NO AUTOGENERADA.** No toca ninguna CHECK ni ninguna columna: es solo un
INSERT, así que el recuento de CHECK del proyecto **no cambia** al aplicarla (hoy 15; el
`SELECT ... FROM pg_constraint` de CLAUDE.md sección 10 debe dar lo mismo antes y después).

`formato='api'` sin matices, por primera vez desde el BOE: aquí el sumario **y** el cuerpo son
XML, y el sumario se direcciona por la fecha sin número de edición de por medio.

`ambito_territorial='autonomico'` aunque el BOCM lleve dentro la sección `III. ADMINISTRACIÓN
LOCAL AYUNTAMIENTOS`. La columna describe **la fuente**, no lo que se publica en ella: el BOCM es
el diario oficial de la Comunidad de Madrid. Que Madrid sea uniprovincial y por tanto no tenga BOP
(`docs/fuentes.md`) es lo que hace que sus ayuntamientos publiquen aquí, y eso se cuenta en el ADR
0034 y en la auditoría de fuentes, no falseando esta columna.

**La licencia se deja en `TODO(verificar)`, no se deduce** (regla de oro 8). No se localizó una
declaración de reutilización del BOCM en la comprobación del 2026-09-06.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7c1e94b2d38"
down_revision: str | Sequence[str] | None = "f4a8d21e7c93"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NOMBRE = "Boletín Oficial de la Comunidad de Madrid"


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
            ccaa="Comunidad de Madrid",
            ambito_territorial="autonomico",
            # ISO 3166-2:ES, el mismo eje por el que cruza el mapa, y la clave con la que
            # `worker/run.py` elige la fila. Si no cuadrara con la tabla `FUENTES`, el worker
            # archivaría el BOCM bajo otro boletín.
            ccaa_codigo="MD",
            provincia=None,
            formato="api",
            url_base="https://www.bocm.es/",
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
