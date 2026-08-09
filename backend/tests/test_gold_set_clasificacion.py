"""El gold set contra la etapa 4: `clasificacion_esperada` frente a lo que el pipeline guardó.

Verificación 4 del ADR 0016. Se compara contra **la fila de `deteccion` de la base de datos**,
no contra una llamada directa al catálogo, y la diferencia importa: lo que hay que medir es lo
que el sistema concluye de punta a punta —prefiltro, cuerpo archivado, catálogo, persistencia—,
no si una función devuelve lo que se espera de ella cuando se la llama a mano. Un fallo en la
cola del clasificador (que una norma no llegue a evaluarse) es invisible para lo segundo y es
justo el modo de fallo que este proyecto se ha encontrado ya dos veces.

Por eso necesita PostgreSQL y el almacén poblado, y por eso se **salta con el motivo y el
remedio escritos** cuando no los hay, en vez de fingir que mide. Mismo criterio que
`test_health.py`.

**Hoy hay una sola etiqueta de clasificación en el corpus** (`BOE-A-2024-10767`). Con una no se
mide nada: esto comprueba que el mecanismo existe y que ese caso —el que el proyecto usa para
explicar por qué existe— sale bien. Ninguna cifra de cobertura del clasificador se publica
antes de que el gold set tenga volumen, igual que con el eje léxico.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.database import engine as engine_real
from app.models.deteccion import Deteccion
from app.models.norma import Norma
from tests.gold_set.esquema import CasoGoldSet, cargar_casos

_REMEDIO = (
    "Levanta la pila (`docker compose up -d`), ingiere el día del caso "
    "(`docker compose exec worker python -m worker.run --fuente boe --fecha AAAA-MM-DD`) y "
    "pasa el catálogo (`--reclasificar`). La suite se ejecuta dentro del contenedor: "
    "`docker compose exec backend python -m pytest`."
)


def _hay_postgres() -> bool:
    sonda = create_engine(engine_real.url, connect_args={"connect_timeout": 2})
    try:
        with sonda.connect() as conexion:
            conexion.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False
    finally:
        sonda.dispose()


def _casos_con_clasificacion() -> list[CasoGoldSet]:
    return [caso for caso in cargar_casos() if caso.clasificacion_esperada is not None]


def test_hay_al_menos_un_caso_con_clasificacion_etiquetada() -> None:
    """Sin esto, el test de abajo pasaría en verde recorriendo una lista vacía.

    Es el modo de fallo clásico de un test parametrizado sobre datos: el día que alguien deje
    todas las `clasificacion_esperada` en `null`, la suite seguiría verde y nadie se enteraría
    de que la etapa 4 ha dejado de estar medida.
    """
    assert _casos_con_clasificacion()


@pytest.mark.parametrize(
    "caso", _casos_con_clasificacion(), ids=lambda caso: caso.identificador_oficial
)
def test_la_clasificacion_persistida_coincide_con_la_etiqueta(caso: CasoGoldSet) -> None:
    if not _hay_postgres():
        pytest.skip(f"no hay un PostgreSQL alcanzable en DATABASE_URL. {_REMEDIO}")

    with sessionmaker(bind=engine_real)() as session:
        norma = session.scalar(
            select(Norma).where(Norma.identificador_oficial == caso.identificador_oficial)
        )
        if norma is None:
            pytest.skip(
                f"{caso.identificador_oficial} no está ingerida "
                f"(fecha {caso.fecha_publicacion}). {_REMEDIO}"
            )
        if norma.reglas_evaluado_en is None:
            pytest.skip(
                f"{caso.identificador_oficial} está ingerida pero el catálogo de reglas no ha "
                f"pasado por ella. {_REMEDIO}"
            )

        deteccion = session.scalar(select(Deteccion).where(Deteccion.norma_id == norma.id))

        assert deteccion is not None, (
            f"{caso.identificador_oficial}: se esperaba {caso.clasificacion_esperada!r} y no "
            "hay ninguna detección. Sin fila no hay nada que revisar ni que emitir."
        )
        assert deteccion.clasificacion.value == caso.clasificacion_esperada
        # 7.6: un veredicto sin regla ni evidencia no se puede auditar, así que no cuenta como
        # acierto aunque la etiqueta coincida.
        assert deteccion.regla_aplicada is not None
        assert deteccion.evidencia_json is not None
        assert deteccion.evidencia_json["spans"]
