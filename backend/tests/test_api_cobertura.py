"""Tests de `GET /api/cobertura`, el endpoint que declara los huecos del proyecto (ADR 0014).

El test que justifica el fichero entero es `test_una_fuente_activa_con_normas_ilegibles_no_se_
presenta_como_cobertura`: una fuente puede estar **activa** y entregar documentos que el pipeline
no consigue leer. Pasó con el DOGC —172 de 264 normas (ADR 0020)— y esta ruta, que existe
precisamente para no callarse los huecos, era el único sitio del sistema donde ese hueco no se
veía.

SQLite en memoria y una app propia con solo este router, mismo criterio que `test_api_alertas.py`.
"""

from __future__ import annotations

import datetime
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import cobertura as api_cobertura
from app.database import Base
from app.models.documento import Documento, EstadoPipeline, TipoDocumento
from app.models.fuente import AmbitoTerritorial, FormatoFuente, Fuente, TipoFuente
from app.models.norma import EstadoPrefiltro, Norma


@pytest.fixture
def sesion_db() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    fabrica = sessionmaker(bind=engine)
    with fabrica() as sesion:
        yield sesion
    engine.dispose()


@pytest.fixture
def client(sesion_db: Session) -> Iterator[TestClient]:
    aplicacion = FastAPI()
    aplicacion.include_router(api_cobertura.router)
    aplicacion.dependency_overrides[api_cobertura.get_session] = lambda: sesion_db
    with TestClient(aplicacion) as cliente:
        yield cliente


def _fuente(session: Session, *, codigo: str | None, activa: bool = True) -> Fuente:
    fuente = Fuente(
        nombre=f"Boletín {codigo or 'estatal'}",
        tipo=TipoFuente.BOLETIN_AUTONOMICO if codigo else TipoFuente.BOE,
        ambito_territorial=AmbitoTerritorial.AUTONOMICO if codigo else AmbitoTerritorial.ESTATAL,
        ccaa="Catalunya" if codigo else None,
        ccaa_codigo=codigo,
        formato=FormatoFuente.API,
        url_base="https://ejemplo.invalid/",
        licencia_reutil=None,
        activa=activa,
    )
    session.add(fuente)
    session.flush()
    return fuente


def _normas(session: Session, fuente: Fuente, *estados: EstadoPrefiltro) -> None:
    documento = Documento(
        fuente_id=fuente.id,
        identificador_oficial=f"S-{fuente.id}",
        fecha_publicacion=datetime.date(2024, 12, 31),
        url_original="https://ejemplo.invalid/sumario",
        sha256=f"{fuente.id:064d}",
        sello_tiempo=datetime.datetime.now(datetime.UTC),
        ruta_almacen=f"00/00/{fuente.id:064d}.xml",
        estado_pipeline=EstadoPipeline.INGERIDO,
        tipo=TipoDocumento.SUMARIO,
    )
    session.add(documento)
    session.flush()
    for indice, estado in enumerate(estados):
        session.add(
            Norma(
                documento_id=documento.id,
                identificador_oficial=f"N-{fuente.id}-{indice}",
                titulo="Orden",
                prefiltro_estado=estado,
            )
        )
    session.commit()


def test_una_fuente_activa_con_normas_ilegibles_no_se_presenta_como_cobertura(
    client: TestClient, sesion_db: Session
) -> None:
    """`vigiladas` dice que estamos suscritos; `ilegibles` dice cuánto no estamos leyendo.

    Sin la segunda cifra, esta comunidad sale como «1 de 1 vigilada» con dos de sus tres normas
    sin que nadie las haya analizado, que es exactamente la cobertura aparente que el ADR 0020
    existe para deshacer.
    """
    fuente = _fuente(sesion_db, codigo="CT")
    _normas(
        sesion_db,
        fuente,
        EstadoPrefiltro.ILEGIBLE,
        EstadoPrefiltro.ILEGIBLE,
        EstadoPrefiltro.DESCARTADA,
    )

    cuerpo = client.get("/api/cobertura").json()
    catalunya = next(c for c in cuerpo["por_ccaa"] if c["ccaa_codigo"] == "CT")

    assert (catalunya["vigiladas"], catalunya["conocidas"]) == (1, 1)
    assert (catalunya["normas"], catalunya["ilegibles"]) == (3, 2)


def test_las_dos_cifras_van_siempre_juntas_aunque_sean_cero(
    client: TestClient, sesion_db: Session
) -> None:
    """`ilegibles` a solas no dice si son 2 de 3 o 2 de 20.000, y omitirla al ser cero haría
    que la ausencia del campo se leyera como "no medido"."""
    fuente = _fuente(sesion_db, codigo="CT")
    _normas(sesion_db, fuente, EstadoPrefiltro.DESCARTADA)

    catalunya = next(
        c for c in client.get("/api/cobertura").json()["por_ccaa"] if c["ccaa_codigo"] == "CT"
    )

    assert (catalunya["normas"], catalunya["ilegibles"]) == (1, 0)


def test_las_normas_sin_comunidad_suman_al_total_y_no_al_desglose(
    client: TestClient, sesion_db: Session
) -> None:
    """El BOE no pertenece a ninguna comunidad. Dejarlo fuera del total dejaría al endpoint
    contando solo la parte del sistema que menos normas tiene."""
    estatal = _fuente(sesion_db, codigo=None)
    _normas(sesion_db, estatal, EstadoPrefiltro.DESCARTADA, EstadoPrefiltro.SOSPECHA)
    autonomica = _fuente(sesion_db, codigo="CT")
    _normas(sesion_db, autonomica, EstadoPrefiltro.ILEGIBLE)

    cuerpo = client.get("/api/cobertura").json()

    assert (cuerpo["normas"], cuerpo["ilegibles"]) == (3, 1)
    assert sum(c["normas"] for c in cuerpo["por_ccaa"]) == 1


def test_sin_normas_ingeridas_las_cifras_son_cero_y_no_faltan(client: TestClient) -> None:
    """Una base recién migrada no puede hacer que el contrato cambie de forma."""
    cuerpo = client.get("/api/cobertura").json()

    assert (cuerpo["normas"], cuerpo["ilegibles"]) == (0, 0)
