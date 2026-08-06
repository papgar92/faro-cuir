"""Tests del servicio que persiste el prefiltro.

SQLite en memoria, mismo criterio que `test_ingesta_service.py`: lo que se prueba es la
lógica (¿a quién reevalúa?, ¿es idempotente?, ¿distingue pendiente de descartada?), no el
dialecto. La CHECK que impide un estado inventado la crea la migración y se verifica contra
Postgres de verdad en CI.
"""

from __future__ import annotations

import datetime
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.documento import Documento, EstadoPipeline
from app.models.fuente import FormatoFuente, Fuente, TipoFuente
from app.models.norma import EstadoPrefiltro, Norma
from app.pipeline import prefiltro
from app.services import prefiltro as servicio


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    fabrica = sessionmaker(bind=engine)
    with fabrica() as sesion:
        yield sesion
    engine.dispose()


@pytest.fixture
def documento(session: Session) -> Documento:
    fuente = Fuente(
        nombre="BOE",
        tipo=TipoFuente.BOE,
        ccaa=None,
        formato=FormatoFuente.API,
        url_base="https://www.boe.es/datosabiertos/api/boe/sumario/",
        licencia_reutil=None,
        activa=True,
    )
    session.add(fuente)
    session.flush()

    doc = Documento(
        fuente_id=fuente.id,
        identificador_oficial="BOE-S-2023-51",
        fecha_publicacion=datetime.date(2023, 3, 1),
        url_original="https://www.boe.es/datosabiertos/api/boe/sumario/20230301",
        sha256="0" * 64,
        sello_tiempo=datetime.datetime.now(datetime.UTC),
        ruta_almacen="00/00/" + "0" * 64 + ".xml",
        estado_pipeline=EstadoPipeline.INGERIDO,
    )
    session.add(doc)
    session.flush()
    return doc


def _norma(documento: Documento, ident: str, titulo: str, **kwargs: object) -> Norma:
    return Norma(documento_id=documento.id, identificador_oficial=ident, titulo=titulo, **kwargs)


def test_marca_relevantes_y_descartadas(session: Session, documento: Documento) -> None:
    session.add_all(
        [
            _norma(documento, "BOE-A-1", "Ley para la igualdad de las personas trans y LGTBI"),
            _norma(documento, "BOE-A-2", "Orden por la que se aprueba el modelo 190 del IRPF"),
        ]
    )
    session.commit()

    resumen = servicio.aplicar(session, documento_id=documento.id)

    assert (resumen.evaluadas, resumen.relevantes, resumen.descartadas) == (2, 1, 1)
    normas = {n.identificador_oficial: n for n in session.scalars(select(Norma))}
    assert normas["BOE-A-1"].prefiltro_estado is EstadoPrefiltro.RELEVANTE
    assert normas["BOE-A-2"].prefiltro_estado is EstadoPrefiltro.DESCARTADA


def test_guarda_por_que_paso_y_con_que_vocabulario(session: Session, documento: Documento) -> None:
    """Sin el término y la versión, el resultado no se puede auditar ni reevaluar."""
    session.add(_norma(documento, "BOE-A-1", "Ley de identidad de género"))
    session.commit()

    servicio.aplicar(session, documento_id=documento.id)

    norma = session.scalar(select(Norma))
    assert norma is not None
    assert norma.prefiltro_terminos == ["identidad de genero"]
    assert norma.prefiltro_version == prefiltro.VERSION_VOCABULARIO
    assert norma.prefiltro_evaluado_en is not None


def test_al_descartar_guarda_lista_vacia_no_nulo(session: Session, documento: Documento) -> None:
    """NULL significaría "no evaluado", que es otra cosa distinta de "evaluado y sin match"."""
    session.add(_norma(documento, "BOE-A-1", "Orden sobre el modelo 190 del IRPF"))
    session.commit()

    servicio.aplicar(session, documento_id=documento.id)

    norma = session.scalar(select(Norma))
    assert norma is not None
    assert norma.prefiltro_terminos == []
    assert norma.prefiltro_version == prefiltro.VERSION_VOCABULARIO


def test_es_idempotente(session: Session, documento: Documento) -> None:
    session.add(_norma(documento, "BOE-A-1", "Ley de personas trans"))
    session.commit()

    assert servicio.aplicar(session, documento_id=documento.id).evaluadas == 1
    # La segunda pasada no toca nada: ya está evaluada con el vocabulario vigente.
    assert servicio.aplicar(session, documento_id=documento.id).evaluadas == 0


def test_reevalua_lo_evaluado_con_un_vocabulario_anterior(
    session: Session, documento: Documento
) -> None:
    """El motivo entero de guardar la versión.

    Si al añadir un término solo se evaluaran las normas nuevas, el término nuevo protegería
    únicamente al futuro y las normas ya descartadas se quedarían mal clasificadas para
    siempre.
    """
    norma = _norma(
        documento,
        "BOE-A-1",
        "Ley de personas trans",
        prefiltro_estado=EstadoPrefiltro.DESCARTADA,
        prefiltro_terminos=[],
        prefiltro_version="1999.01.01",
        prefiltro_evaluado_en=datetime.datetime.now(datetime.UTC),
    )
    session.add(norma)
    session.commit()

    resumen = servicio.aplicar(session, documento_id=documento.id)

    assert resumen.evaluadas == 1
    session.refresh(norma)
    assert norma.prefiltro_estado is EstadoPrefiltro.RELEVANTE
    assert norma.prefiltro_version == prefiltro.VERSION_VOCABULARIO


def test_cuenta_las_que_pasan_solo_por_terminos_de_contexto(
    session: Session, documento: Documento
) -> None:
    """El embudo tiene que separar la señal fuerte del ruido de la lista genérica."""
    session.add_all(
        [
            _norma(documento, "BOE-A-1", "Orden sobre la identidad de género del alumnado"),
            _norma(documento, "BOE-A-2", "Orden que actualiza la cartera de servicios comunes"),
        ]
    )
    session.commit()

    resumen = servicio.aplicar(session, documento_id=documento.id)

    assert resumen.relevantes == 2
    assert resumen.solo_por_contexto == 1


def test_solo_toca_el_documento_indicado(session: Session, documento: Documento) -> None:
    otro = Documento(
        fuente_id=documento.fuente_id,
        identificador_oficial="BOE-S-2024-305",
        fecha_publicacion=datetime.date(2024, 12, 19),
        url_original="https://www.boe.es/datosabiertos/api/boe/sumario/20241219",
        sha256="1" * 64,
        sello_tiempo=datetime.datetime.now(datetime.UTC),
        ruta_almacen="11/11/" + "1" * 64 + ".xml",
        estado_pipeline=EstadoPipeline.INGERIDO,
    )
    session.add(otro)
    session.flush()
    session.add_all(
        [
            _norma(documento, "BOE-A-1", "Ley de personas trans"),
            _norma(otro, "BOE-A-2", "Ley de personas trans"),
        ]
    )
    session.commit()

    assert servicio.aplicar(session, documento_id=documento.id).evaluadas == 1

    sin_evaluar = session.scalar(select(Norma).where(Norma.identificador_oficial == "BOE-A-2"))
    assert sin_evaluar is not None
    assert sin_evaluar.prefiltro_estado is EstadoPrefiltro.PENDIENTE


def test_sin_documento_barre_toda_la_tabla(session: Session, documento: Documento) -> None:
    session.add_all(
        [
            _norma(documento, "BOE-A-1", "Ley de personas trans"),
            _norma(documento, "BOE-A-2", "Orden del modelo 190"),
        ]
    )
    session.commit()

    assert servicio.aplicar(session).evaluadas == 2


def test_pendiente_es_el_estado_por_defecto(session: Session, documento: Documento) -> None:
    """Una norma recién ingerida no está descartada: está sin mirar."""
    session.add(_norma(documento, "BOE-A-1", "Lo que sea"))
    session.commit()

    norma = session.scalar(select(Norma))
    assert norma is not None
    assert norma.prefiltro_estado is EstadoPrefiltro.PENDIENTE
    assert norma.prefiltro_version is None
