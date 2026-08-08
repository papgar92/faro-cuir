"""ambito territorial en fuente y semilla de los 43 boletines provinciales

Revision ID: c7e1b4a9d052
Revises: ae3da0c963fe
Create Date: 2026-08-08 16:10:00.000000

Implementa el **ADR 0014**: la capa local entra en alcance y se vigila a través del BOP.

**ESCRITA A MANO, NO AUTOGENERADA, Y A PROPÓSITO.** El `autogenerate` de alembic ha propuesto
borrar las CHECK de `Enum(native_enum=False, create_constraint=True)` en *cada* migración de
este repo — cuatro veces, y en la última proponía ocho de golpe, incluida `origenclasificacion`
de `deteccion`, que es la que hace que el veredicto del LLM no sea representable en el esquema
(ADR 0004). Esta migración toca dos CHECK, así que era justo la ocasión de que volviera a
pasar. Escribiéndola a mano el problema no puede ni presentarse.

Comprobación obligatoria después de aplicar (CLAUDE.md sección 11): las CHECK del proyecto
pasan de **11 a 12** (entra `ambitoterritorial`; `tipofuente` se sustituye, no se suma).

    SELECT conrelid::regclass, conname FROM pg_constraint WHERE contype='c' ORDER BY 1,2;

Tres cambios de esquema y uno de datos:

1. `fuente.ambito_territorial` — eje independiente de `tipo` (ver el docstring del modelo).
2. `fuente.provincia` y `fuente.ccaa_codigo`.
3. `fuente.formato` pasa a **nullable**. No es una relajación por comodidad: se registran 43
   fuentes cuyo nombre y URL están verificados y cuyo formato no. NULL significa "no
   comprobado"; poner "html" porque es lo más probable sería inventarlo (regla de oro 8) y
   además quedaría indistinguible de un dato auditado.
4. Semilla de los 43 BOP con `activa=false`. Los datos son exactamente los de
   `docs/fuentes.md`, verificados el 2026-08-08 contra el directorio oficial del Punto de
   Acceso General. `activa=false` no es un detalle: "sabemos que existe y no la estamos
   mirando" es un hueco de cobertura declarado, y una fuente ausente de la tabla es un hueco
   invisible.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7e1b4a9d052"
down_revision: str | Sequence[str] | None = "ae3da0c963fe"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_TIPOS_ANTES = ("boe", "boletin_autonomico", "parlamento")
_TIPOS_AHORA = ("boe", "boletin_autonomico", "boletin_provincial", "parlamento")
_AMBITOS = ("estatal", "autonomico", "provincial", "local")


def _lista(valores: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in valores)


# Los 43 boletines provinciales: (provincia, ccaa, codigo ISO 3166-2:ES, url).
# Nombre y URL verificados el 2026-08-08 contra
# administracion.gob.es/pag_Home/espanaAdmon/boletinesYLegislacion/BO_Diputaciones.html
#
# No están las 50 provincias y eso es correcto: las 7 que faltan son las CCAA uniprovinciales
# (Asturias, Cantabria, Illes Balears, Madrid, Murcia, Navarra, La Rioja), que no tienen BOP
# porque su boletín autonómico hace ese papel. 43 + 7 = 50.
_BOP: tuple[tuple[str, str, str, str], ...] = (
    (
        "Almería",
        "Andalucía",
        "AN",
        "https://www.dipalme.org/Servicios/cmsdipro/index.nsf/bop_view.xsp",
    ),
    ("Cádiz", "Andalucía", "AN", "https://www.bopcadiz.es"),
    ("Córdoba", "Andalucía", "AN", "https://bop.dipucordoba.es"),
    ("Granada", "Andalucía", "AN", "https://bop.dipgra.es/publica/consulta-de-bops/"),
    ("Huelva", "Andalucía", "AN", "https://sede.diphuelva.es/servicios/bop"),
    ("Jaén", "Andalucía", "AN", "https://bop.dipujaen.es"),
    ("Málaga", "Andalucía", "AN", "https://www.bopmalaga.es"),
    ("Sevilla", "Andalucía", "AN", "https://www.dipusevilla.es/bop/"),
    ("Huesca", "Aragón", "AR", "https://bop.dphuesca.es/index.php/mod.menus/mem.detalle"),
    ("Teruel", "Aragón", "AR", "https://236ws.dpteruel.es/DPT/bopt.nsf"),
    ("Zaragoza", "Aragón", "AR", "https://bop.dpz.es/BOPZ/"),
    ("Las Palmas", "Canarias", "CN", "https://www.boplaspalmas.net/nbop2/index.php"),
    (
        "Santa Cruz de Tenerife",
        "Canarias",
        "CN",
        "https://www.bopsantacruzdetenerife.es/bopsc2/index.php",
    ),
    ("Albacete", "Castilla-La Mancha", "CM", "https://bop.dipualba.es"),
    ("Ciudad Real", "Castilla-La Mancha", "CM", "https://bop.dipucr.es"),
    (
        "Cuenca",
        "Castilla-La Mancha",
        "CM",
        "https://www.dipucuenca.es/boletin-oficial-de-la-provincia",
    ),
    ("Guadalajara", "Castilla-La Mancha", "CM", "https://boletin.dguadalajara.es/boletin/"),
    ("Toledo", "Castilla-La Mancha", "CM", "https://bop.diputoledo.es/webEbop/ebopCalendar.jsp"),
    ("Ávila", "Castilla y León", "CL", "https://www.diputacionavila.es/boletin-oficial/"),
    ("Burgos", "Castilla y León", "CL", "https://bopbur.diputaciondeburgos.es/search"),
    ("León", "Castilla y León", "CL", "https://bop.dipuleon.es/publica/consulta-de-bops/"),
    (
        "Palencia",
        "Castilla y León",
        "CL",
        "https://www.diputaciondepalencia.es/servicios/boletin-oficial-provincia",
    ),
    ("Salamanca", "Castilla y León", "CL", "https://sede.diputaciondesalamanca.gob.es/BOP/"),
    ("Segovia", "Castilla y León", "CL", "https://www.dipsegovia.es/bop"),
    ("Soria", "Castilla y León", "CL", "https://bop.dipsoria.es"),
    ("Valladolid", "Castilla y León", "CL", "https://bop.sede.diputaciondevalladolid.es/"),
    (
        "Zamora",
        "Castilla y León",
        "CL",
        "https://www.diputaciondezamora.es/opencms/servicios/BOP/bop/index.html",
    ),
    ("Barcelona", "Catalunya", "CT", "https://bop.diba.cat"),
    ("Girona", "Catalunya", "CT", "https://www.ddgi.cat/bop/"),
    ("Lleida", "Catalunya", "CT", "https://ebop.diputaciolleida.cat/bop/"),
    ("Tarragona", "Catalunya", "CT", "https://www.diputaciodetarragona.cat/ebop/"),
    ("Alicante", "C. Valenciana", "VC", "https://sede.diputacionalicante.es/consultas-bop/"),
    ("Castellón", "C. Valenciana", "VC", "https://bop.dipcas.es/PortalBOP/boletin.do"),
    ("Valencia", "C. Valenciana", "VC", "https://bop.dival.es/bop/drvisapi.dll"),
    ("Badajoz", "Extremadura", "EX", "https://www.dip-badajoz.es/bop/"),
    ("Cáceres", "Extremadura", "EX", "https://bop.dip-caceres.es/bop/index.html"),
    ("A Coruña", "Galicia", "GA", "https://bop.dacoruna.gal/bopportal/"),
    (
        "Lugo",
        "Galicia",
        "GA",
        "https://www.deputacionlugo.gal/boletin-oficial-da-provincia-de-lugo",
    ),
    ("Ourense", "Galicia", "GA", "https://bop.depourense.es/portal/"),
    ("Pontevedra", "Galicia", "GA", "https://boppo.depo.gal/"),
    ("Álava", "Euskadi", "PV", "https://www.araba.eus/botha/Inicio/SGBO5001.aspx"),
    ("Bizkaia", "Euskadi", "PV", "https://www.bizkaia.eus/es/bob"),
    ("Gipuzkoa", "Euskadi", "PV", "https://egoitza.gipuzkoa.eus/es/bog"),
)

# Los tres forales no se llaman "BOP" sino Boletín Oficial del Territorio Histórico, por el
# régimen foral. A efectos de este proyecto cumplen la misma función —es donde publican sus
# ayuntamientos— pero el nombre oficial es el que es y no se homogeneiza.
_NOMBRES_FORALES = {
    "Álava": "Boletín Oficial del Territorio Histórico de Álava (BOTHA)",
    "Bizkaia": "Boletín Oficial de Bizkaia (BOB)",
    "Gipuzkoa": "Boletín Oficial de Gipuzkoa (BOG)",
}


def _nombre(provincia: str) -> str:
    return _NOMBRES_FORALES.get(provincia, f"Boletín Oficial de la Provincia de {provincia}")


def upgrade() -> None:
    """Upgrade schema."""
    # --- 1. Columnas nuevas, primero nullable para poder rellenar lo que ya existe ---------
    op.add_column("fuente", sa.Column("ambito_territorial", sa.String(length=20), nullable=True))
    op.add_column("fuente", sa.Column("provincia", sa.String(length=100), nullable=True))
    op.add_column("fuente", sa.Column("ccaa_codigo", sa.String(length=2), nullable=True))

    # --- 2. Relleno de las filas existentes ------------------------------------------------
    # Se deriva del `tipo`, que es dato ya presente, en vez de asumir que la única fila es el
    # BOE: la migración tiene que ser correcta también sobre una base que ya tenga autonómicas.
    op.execute(
        sa.text(
            "UPDATE fuente SET ambito_territorial = CASE "
            "WHEN tipo = 'boe' THEN 'estatal' ELSE 'autonomico' END "
            "WHERE ambito_territorial IS NULL"
        )
    )
    op.alter_column("fuente", "ambito_territorial", nullable=False)

    # --- 3. CHECK del ámbito ---------------------------------------------------------------
    op.create_check_constraint(
        "ambitoterritorial", "fuente", f"ambito_territorial IN ({_lista(_AMBITOS)})"
    )

    # --- 4. `tipofuente` gana un valor. Se sustituye la CHECK, no se añade otra: dos CHECK
    #        sobre la misma columna se cumplen en AND y la vieja seguiría prohibiendo el valor
    #        nuevo, que es un fallo silencioso de los buenos.
    op.drop_constraint("tipofuente", "fuente", type_="check")
    op.create_check_constraint("tipofuente", "fuente", f"tipo IN ({_lista(_TIPOS_AHORA)})")

    # --- 5. `formato` pasa a nullable. Ver el encabezado: NULL = "no comprobado". -----------
    op.alter_column("fuente", "formato", existing_type=sa.String(length=10), nullable=True)

    # --- 6. Índices de cruce ---------------------------------------------------------------
    op.create_index("ix_fuente_ccaa", "fuente", ["ccaa"])
    op.create_index("ix_fuente_ccaa_codigo", "fuente", ["ccaa_codigo"])
    op.create_index("ix_fuente_provincia", "fuente", ["provincia"])
    op.create_index("ix_fuente_ambito_territorial", "fuente", ["ambito_territorial"])

    # --- 7. Semilla de los 43 --------------------------------------------------------------
    tabla = sa.table(
        "fuente",
        sa.column("nombre", sa.String),
        sa.column("tipo", sa.String),
        sa.column("ccaa", sa.String),
        sa.column("ccaa_codigo", sa.String),
        sa.column("ambito_territorial", sa.String),
        sa.column("provincia", sa.String),
        sa.column("formato", sa.String),
        sa.column("url_base", sa.String),
        sa.column("licencia_reutil", sa.String),
        sa.column("activa", sa.Boolean),
    )
    op.bulk_insert(
        tabla,
        [
            {
                "nombre": _nombre(provincia),
                "tipo": "boletin_provincial",
                "ccaa": ccaa,
                "ccaa_codigo": codigo,
                "ambito_territorial": "provincial",
                "provincia": provincia,
                # NULL los dos: sin verificar en docs/fuentes.md.
                "formato": None,
                "licencia_reutil": None,
                # Registrada, no vigilada. Ver el encabezado y el ADR 0014.
                "activa": False,
                "url_base": url,
            }
            for provincia, ccaa, codigo, url in _BOP
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sa.text("DELETE FROM fuente WHERE tipo = 'boletin_provincial'"))

    op.drop_index("ix_fuente_ambito_territorial", table_name="fuente")
    op.drop_index("ix_fuente_provincia", table_name="fuente")
    op.drop_index("ix_fuente_ccaa_codigo", table_name="fuente")
    op.drop_index("ix_fuente_ccaa", table_name="fuente")

    # Volver a NOT NULL exige que no queden NULL. Las filas provinciales ya se han borrado
    # arriba, que son las únicas que lo tienen a NULL por diseño.
    op.alter_column("fuente", "formato", existing_type=sa.String(length=10), nullable=False)

    op.drop_constraint("tipofuente", "fuente", type_="check")
    op.create_check_constraint("tipofuente", "fuente", f"tipo IN ({_lista(_TIPOS_ANTES)})")

    op.drop_constraint("ambitoterritorial", "fuente", type_="check")
    op.drop_column("fuente", "ccaa_codigo")
    op.drop_column("fuente", "provincia")
    op.drop_column("fuente", "ambito_territorial")
