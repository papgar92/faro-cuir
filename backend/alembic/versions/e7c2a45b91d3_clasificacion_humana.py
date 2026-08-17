"""la persona que revisa puede fijar el signo que la regla no afirmó

Revision ID: e7c2a45b91d3
Revises: d1e5c93a7b48
Create Date: 2026-08-17 20:05:00.000000

Lo pidió el humano revisando, y con el caso perfecto: la **Ley 4/2023** —la norma con la que este
proyecto se explica— sale publicada como «sin signo». Y es correcto que la regla no lo afirme:
R-DER-001 se abstiene a propósito porque derogar una norma es lo que hace tanto quien la desmonta
como quien la sustituye por otra mejor (ver la cabecera de `pipeline/reglas.py`). Pero quien lee
el texto **sí** lo sabe, y no tenía dónde decirlo.

## Por qué una columna nueva y no sobrescribir `deteccion.clasificacion`

Porque son dos afirmaciones distintas y el proyecto entero se apoya en no mezclarlas:

- `deteccion.clasificacion` es lo que **derivó una regla auditable** del texto archivado. Un
  tercero puede reconstruirlo leyendo la regla y el documento, sin ejecutar nuestro código (7.6).
  Sobrescribirlo destruiría esa propiedad: la fila diría «retroceso, regla R-DER-001» y la regla
  no diría eso.
- `cola_revision.clasificacion_humana` es lo que **decidió una persona** con el texto delante, en
  el gate. Es una fuente de autoridad distinta, y se guarda por separado y con nombre propio.

La CHECK admite los mismos cuatro valores que `deteccion.clasificacion` para que no puedan
divergir dos vocabularios sobre lo mismo. NULL significa «quien revisó no cambió el signo», que
no es lo mismo que «dijo que es neutro».

**ESCRITA A MANO, NO AUTOGENERADA.** Añade una CHECK nueva (`clasificacionhumana`) y no toca
ninguna existente: las del proyecto pasan de 13 a **14**.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7c2a45b91d3"
down_revision: str | Sequence[str] | None = "d1e5c93a7b48"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CLASIFICACIONES = ("avance", "retroceso", "neutro", "indeterminado")


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "cola_revision", sa.Column("clasificacion_humana", sa.String(length=20), nullable=True)
    )
    op.create_check_constraint(
        "clasificacionhumana",
        "cola_revision",
        "clasificacion_humana IS NULL OR clasificacion_humana IN ({})".format(
            ", ".join(f"'{c}'" for c in _CLASIFICACIONES)
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("clasificacionhumana", "cola_revision", type_="check")
    op.drop_column("cola_revision", "clasificacion_humana")
