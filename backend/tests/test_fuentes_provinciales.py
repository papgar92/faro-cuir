"""Invariantes de la semilla de los 43 boletines provinciales (ADR 0014).

Una lista de 43 filas escritas a mano se rompe en silencio: se duplica una provincia al
copiar, se pega una URL en la fila de al lado, se pierde una comunidad entera. Nada de eso
levanta un error — simplemente el desglose de cobertura enseña un número que nadie contrasta.

Estos tests son la comprobación que hace que la lista se sostenga sola. La mayoría son
**puros**: leen la tupla del módulo de migración, así que corren siempre, sin base de datos y
sin haber aplicado nada. El último sí necesita PostgreSQL y se salta si no lo hay, con el
mismo criterio que `test_health.py`.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.database import engine

_MIGRACION = (
    Path(__file__).resolve().parent.parent
    / "alembic"
    / "versions"
    / "c7e1b4a9d052_ambito_territorial_y_43_bop.py"
)


def _cargar_migracion() -> Any:
    """Importa el módulo de migración por ruta.

    Alembic no expone `versions/` como paquete importable, y no hay que hacerlo importable
    solo para esto: lo que interesa es el dato, no ejecutar la migración.
    """
    spec = importlib.util.spec_from_file_location("migracion_bop", _MIGRACION)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


BOP: tuple[tuple[str, str, str, str], ...] = _cargar_migracion()._BOP

# Reparto por comunidad, copiado de `docs/fuentes.md`. Está escrito aquí a mano **a propósito**:
# si se derivara de la propia lista, el test comprobaría que la lista es igual a sí misma.
REPARTO_ESPERADO = {
    "AN": 8,
    "AR": 3,
    "CL": 9,
    "CM": 5,
    "CN": 2,
    "CT": 4,
    "EX": 2,
    "GA": 4,
    "PV": 3,
    "VC": 3,
}

# Las 7 CCAA uniprovinciales, que no tienen BOP porque su boletín autonómico hace ese papel.
UNIPROVINCIALES = 7
PROVINCIAS_DE_ESPANA = 50


def test_hay_43_boletines_provinciales() -> None:
    assert len(BOP) == 43


def test_la_cuenta_cuadra_con_la_division_provincial() -> None:
    """43 + 7 uniprovinciales = 50 provincias.

    Es la comprobación que de verdad vale, porque es **independiente** del recuento del
    directorio oficial: no dice "he contado 43 y hay 43", dice que esos 43 encajan con una
    cifra que viene de otro sitio. Si algún día alguien añade un BOP inventado o borra uno
    real, esta suma deja de dar 50.
    """
    assert len(BOP) + UNIPROVINCIALES == PROVINCIAS_DE_ESPANA


def test_no_hay_provincias_ni_urls_repetidas() -> None:
    provincias = [provincia for provincia, _, _, _ in BOP]
    urls = [url for _, _, _, url in BOP]
    assert len(set(provincias)) == len(provincias), "provincia duplicada"
    assert len(set(urls)) == len(urls), "URL duplicada: probable copia y pega entre filas"


def test_el_reparto_por_comunidad_es_el_de_la_auditoria() -> None:
    reparto: dict[str, int] = {}
    for _, _, codigo, _ in BOP:
        reparto[codigo] = reparto.get(codigo, 0) + 1
    assert reparto == REPARTO_ESPERADO


def test_cada_comunidad_tiene_un_solo_nombre() -> None:
    """El código ISO y el nombre visible tienen que ir siempre juntos.

    Si la misma comunidad aparece como "Euskadi" en unas filas y "País Vasco" en otras, el
    desglose de cobertura la parte en dos y ninguna de las dos mitades es correcta.
    """
    nombres_por_codigo: dict[str, set[str]] = {}
    for _, ccaa, codigo, _ in BOP:
        nombres_por_codigo.setdefault(codigo, set()).add(ccaa)
    discrepantes = {c: n for c, n in nombres_por_codigo.items() if len(n) > 1}
    assert not discrepantes, f"la misma comunidad con varios nombres: {discrepantes}"


def test_las_urls_son_https() -> None:
    """CLAUDE.md 6.2: `url_guard` solo admite https y puerto 443.

    Una URL en http aquí no fallaría al insertarse: fallaría el día que se active esa fuente,
    lejos de donde se escribió.
    """
    malas = [url for _, _, _, url in BOP if not url.startswith("https://")]
    assert not malas, malas


def test_los_codigos_son_los_que_usa_el_mapa_del_frontend() -> None:
    """Cruce con `frontend/src/components/MapaCCAA/ccaa-paths.ts`.

    El desglose por comunidad cruza por código. Si el backend siembra "PV" y el mapa dibuja
    "EU", el cruce no falla: devuelve cero fuentes y la interfaz enseña, tan tranquila, que
    Euskadi no tiene ninguna. Este test es el que convierte ese silencio en un rojo.
    """
    paths = (
        Path(__file__).resolve().parents[2]
        / "frontend"
        / "src"
        / "components"
        / "MapaCCAA"
        / "ccaa-paths.ts"
    )
    if not paths.exists():  # pragma: no cover - el frontend puede no estar en un despliegue
        pytest.skip("no está el fichero de geometría del frontend")

    contenido = paths.read_text(encoding="utf-8")
    codigos_del_mapa = set(re.findall(r'code: "(\w+)"', contenido))
    codigos_sembrados = {codigo for _, _, codigo, _ in BOP}
    huerfanos = codigos_sembrados - codigos_del_mapa
    assert not huerfanos, f"códigos que el mapa no dibuja: {sorted(huerfanos)}"


def test_las_43_estan_en_la_base_y_ninguna_activa() -> None:
    """`activa=false` no es un detalle de la semilla: es la afirmación que hace el sistema.

    "Sabemos que existe y no la estamos mirando" es un hueco de cobertura declarado. Si alguna
    se activara sin tener ingestor, el sistema pasaría a afirmar que vigila algo que no vigila.
    """
    # `connect_timeout` por el mismo motivo que en `test_health.py`: fuera de docker
    # DATABASE_URL apunta a `db`, que no resuelve, y sin tope este salto costaba 2 minutos.
    sonda = create_engine(engine.url, connect_args={"connect_timeout": 2})
    try:
        with sonda.connect() as conexion:
            filas = conexion.execute(
                text(
                    "SELECT count(*), count(*) FILTER (WHERE activa), "
                    "count(*) FILTER (WHERE formato IS NOT NULL) "
                    "FROM fuente WHERE ambito_territorial = 'provincial'"
                )
            ).one()
    except SQLAlchemyError:
        pytest.skip("no hay un PostgreSQL con las migraciones aplicadas")
    finally:
        sonda.dispose()

    total, activas, con_formato = filas
    assert total == 43
    assert activas == 0, "hay una fuente provincial activa y no existe ingestor de BOP"
    assert con_formato == 0, "formato relleno sin haberlo verificado (docs/fuentes.md)"
