"""Tests de la API pública de alertas.

El test que justifica el fichero entero es `test_solo_sale_lo_aprobado`: se siembran los cuatro
estados que puede tener una detección —sin veredicto, con veredicto sin encolar, en cola
pendiente, descartada— más una aprobada, y se comprueba que **solo sale la aprobada**. Es la
regla de oro 4 vista desde fuera: si algo se publica sin gate, es aquí donde se nota.

SQLite en memoria y una app propia con solo este router, mismo criterio que
`test_api_revision.py`: el limitador de peticiones del `app` real es global al proceso y
compartido con los demás tests de API.
"""

from __future__ import annotations

import datetime
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import alertas as api_alertas
from app.database import Base
from app.models.deteccion import (
    Clasificacion,
    ColaRevision,
    Deteccion,
    EstadoRevision,
    OrigenClasificacion,
)
from app.models.documento import Documento, EstadoPipeline, TipoDocumento
from app.models.fuente import AmbitoTerritorial, FormatoFuente, Fuente, TipoFuente
from app.models.norma import EstadoPrefiltro, Norma
from app.pipeline import watchlist
from app.pipeline.watchlist import NormaVigilada, Watchlist
from app.services import revision as servicio

# Una ley autonómica publicada en el BOE: el caso que hace falta que el ámbito salga de la
# watchlist y no de la fuente. Por fuente sería "estatal" y la comunidad quedaría en blanco
# justo en la alerta que el proyecto usa para explicarse.
LISTA = Watchlist(
    version="test",
    normas=(
        NormaVigilada(
            identificador="BOE-A-2016-6728",
            titulo="Ley 2/2016 de Identidad y Expresión de Género (Madrid)",
            nota="fixture",
            ambito="MD",
        ),
    ),
)

EVIDENCIA = {
    "regla": "R-SUP-001",
    "version_reglas": "2026.08.14",
    "version_texto_plano": "2026.08.09",
    "normas_vigiladas": ["BOE-A-2016-6728"],
    "spans": [{"inicio": 100, "fin": 140, "fragmento": "Se suprime el artículo 7."}],
    "punteros_corroborados": [],
    "punteros_sin_corroborar": [],
}


@pytest.fixture(autouse=True)
def watchlist_de_prueba(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(watchlist, "watchlist", lambda: LISTA)


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
    aplicacion.include_router(api_alertas.router)
    aplicacion.dependency_overrides[api_alertas.get_session] = lambda: sesion_db
    with TestClient(aplicacion) as cliente:
        yield cliente


def _sumario(session: Session, fecha: datetime.date) -> Documento:
    fuente = session.scalar(select(Fuente))
    if fuente is None:
        fuente = Fuente(
            nombre="BOE",
            tipo=TipoFuente.BOE,
            ambito_territorial=AmbitoTerritorial.ESTATAL,
            ccaa=None,
            formato=FormatoFuente.API,
            url_base="https://www.boe.es/datosabiertos/api/boe/sumario/",
            licencia_reutil=None,
            activa=True,
        )
        session.add(fuente)
        session.flush()
    # Un sumario por fecha: la clave natural `(fuente_id, identificador_oficial)` es lo que hace
    # idempotente al worker, y aquí lo mismo — varias normas del mismo día comparten boletín.
    identificador = f"BOE-S-{fecha.isoformat()}"
    existente = session.scalar(
        select(Documento).where(Documento.identificador_oficial == identificador)
    )
    if existente is not None:
        return existente

    documento = Documento(
        fuente_id=fuente.id,
        identificador_oficial=identificador,
        fecha_publicacion=fecha,
        url_original="https://www.boe.es/datosabiertos/api/boe/sumario/x",
        sha256=f"{abs(hash(fecha)) % 10**60:064d}",
        sello_tiempo=datetime.datetime.now(datetime.UTC),
        ruta_almacen="00/00/x.xml",
        estado_pipeline=EstadoPipeline.INGERIDO,
        tipo=TipoDocumento.SUMARIO,
    )
    session.add(documento)
    session.flush()
    return documento


def _norma_con_deteccion(
    session: Session,
    *,
    ident: str,
    fecha: datetime.date = datetime.date(2024, 5, 29),
    con_regla: bool = True,
    con_cuerpo: bool = True,
) -> Deteccion:
    sumario = _sumario(session, fecha)
    cuerpo = None
    if con_cuerpo:
        cuerpo = Documento(
            fuente_id=sumario.fuente_id,
            identificador_oficial=ident,
            fecha_publicacion=fecha,
            url_original=f"https://www.boe.es/diario_boe/xml.php?id={ident}",
            sha256=f"{abs(hash(ident)) % 10**60:064d}",
            sello_tiempo=datetime.datetime.now(datetime.UTC),
            ruta_almacen=f"aa/bb/{ident}.xml",
            estado_pipeline=EstadoPipeline.INGERIDO,
            tipo=TipoDocumento.TEXTO_NORMA,
        )
        session.add(cuerpo)
        session.flush()

    norma = Norma(
        documento_id=sumario.id,
        identificador_oficial=ident,
        titulo=f"Norma {ident}",
        url_texto=f"https://www.boe.es/diario_boe/xml.php?id={ident}",
        documento_texto_id=cuerpo.id if cuerpo else None,
        prefiltro_estado=EstadoPrefiltro.RELEVANTE,
        prefiltro_terminos=[],
        prefiltro_evaluado_en=datetime.datetime.now(datetime.UTC),
    )
    session.add(norma)
    session.flush()

    deteccion = Deteccion(
        norma_id=norma.id,
        extraccion_json={"extraccion": {"articulos": []}, "modelo": "qwen2.5:3b-instruct"},
        clasificacion=Clasificacion.RETROCESO if con_regla else Clasificacion.INDETERMINADO,
        origen=OrigenClasificacion.DERIVADO_DIFF if con_regla else OrigenClasificacion.HEURISTICA,
        regla_aplicada="R-SUP-001" if con_regla else None,
        evidencia_json=EVIDENCIA if con_regla else None,
        severidad=4 if con_regla else 1,
        confianza=0.8 if con_regla else 0.0,
    )
    session.add(deteccion)
    session.flush()
    return deteccion


def test_solo_sale_lo_aprobado(client: TestClient, sesion_db: Session) -> None:
    """Los cinco estados posibles a la vez. Sale uno.

    Es la regla de oro 4 vista desde fuera de la API, y el motivo de que la consulta parta de
    `alerta` en vez de filtrar `deteccion`: la aprobación no es un campo que haya que acordarse
    de mirar, es la tabla de la que se lee.
    """
    _norma_con_deteccion(sesion_db, ident="BOE-A-2024-0001", con_regla=False)  # centinela
    _norma_con_deteccion(sesion_db, ident="BOE-A-2024-0002")  # con veredicto, sin encolar
    pendiente = _norma_con_deteccion(sesion_db, ident="BOE-A-2024-0003")
    descartada = _norma_con_deteccion(sesion_db, ident="BOE-A-2024-0004")
    aprobada = _norma_con_deteccion(sesion_db, ident="BOE-A-2024-0005")
    sesion_db.add_all(
        [
            ColaRevision(deteccion_id=pendiente.id, estado=EstadoRevision.PENDIENTE),
            ColaRevision(deteccion_id=descartada.id, estado=EstadoRevision.DESCARTADA),
            ColaRevision(deteccion_id=aprobada.id, estado=EstadoRevision.PENDIENTE),
        ]
    )
    sesion_db.commit()
    cola_aprobada = sesion_db.scalar(
        select(ColaRevision).where(ColaRevision.deteccion_id == aprobada.id)
    )
    assert cola_aprobada is not None
    servicio.aprobar(sesion_db, cola_aprobada.id, nota="Verificado contra el BOE.")

    alertas = client.get("/api/alertas").json()

    assert [a["norma"]["identificador_oficial"] for a in alertas] == ["BOE-A-2024-0005"]


def test_la_alerta_viaja_con_lo_que_hace_falta_para_comprobarla(
    client: TestClient, sesion_db: Session
) -> None:
    """Publicar un veredicto sin su evidencia sería pedir que se fíen (6.5 y 7.6)."""
    deteccion = _norma_con_deteccion(sesion_db, ident="BOE-A-2024-10767")
    sesion_db.add(ColaRevision(deteccion_id=deteccion.id, estado=EstadoRevision.PENDIENTE))
    sesion_db.commit()
    cola = sesion_db.scalar(select(ColaRevision))
    assert cola is not None
    servicio.aprobar(sesion_db, cola.id)

    alerta = client.get("/api/alertas").json()[0]

    assert alerta["clasificacion"] == "retroceso"
    assert alerta["regla_aplicada"] == "R-SUP-001"
    assert alerta["version_reglas"] == "2026.08.14"
    assert alerta["spans"] == [
        {"inicio": 100, "fin": 140, "fragmento": "Se suprime el artículo 7."}
    ]
    assert alerta["texto_archivado"]["sha256"]
    assert alerta["texto_archivado"]["url_original"].endswith("BOE-A-2024-10767")


def test_el_ambito_sale_de_la_watchlist_y_no_de_la_fuente(
    client: TestClient, sesion_db: Session
) -> None:
    """Una ley autonómica se publica en el BOE: por fuente sería estatal y Madrid quedaría vacía.

    Es el dato que hace posible colorear el mapa en el caso que el proyecto existe para enseñar.
    """
    deteccion = _norma_con_deteccion(sesion_db, ident="BOE-A-2024-10767")
    sesion_db.add(ColaRevision(deteccion_id=deteccion.id, estado=EstadoRevision.PENDIENTE))
    sesion_db.commit()
    cola = sesion_db.scalar(select(ColaRevision))
    assert cola is not None
    servicio.aprobar(sesion_db, cola.id)

    vigiladas = client.get("/api/alertas").json()[0]["normas_vigiladas"]

    assert vigiladas == [
        {
            "identificador": "BOE-A-2016-6728",
            "titulo": "Ley 2/2016 de Identidad y Expresión de Género (Madrid)",
            "ambito": "MD",
        }
    ]


def test_no_se_publica_lo_que_dijo_el_modelo(client: TestClient, sesion_db: Session) -> None:
    """La detección lleva `extraccion_json` lleno y la alerta no lo enseña (reglas 3 y 10)."""
    deteccion = _norma_con_deteccion(sesion_db, ident="BOE-A-2024-10767")
    sesion_db.add(ColaRevision(deteccion_id=deteccion.id, estado=EstadoRevision.PENDIENTE))
    sesion_db.commit()
    cola = sesion_db.scalar(select(ColaRevision))
    assert cola is not None
    servicio.aprobar(sesion_db, cola.id, nota="Nota interna del revisor.")

    cuerpo = client.get("/api/alertas").text

    assert "extraccion_json" not in cuerpo
    assert "qwen" not in cuerpo
    # La nota tampoco: a quien la escribe se le dijo que se guarda con la decisión, no que se
    # publica. Ver la cabecera de `schemas/alerta.py`.
    assert "Nota interna" not in cuerpo


def test_ordena_por_fecha_del_boletin_y_no_por_cuando_lo_miramos(
    client: TestClient, sesion_db: Session
) -> None:
    """Una cronología de retrocesos es de lo que pasó, no de cuándo lo procesamos nosotros."""
    for ident, fecha in (
        ("BOE-A-2023-0001", datetime.date(2023, 3, 1)),
        ("BOE-A-2024-0001", datetime.date(2024, 5, 29)),
    ):
        deteccion = _norma_con_deteccion(sesion_db, ident=ident, fecha=fecha)
        sesion_db.add(ColaRevision(deteccion_id=deteccion.id, estado=EstadoRevision.PENDIENTE))
        sesion_db.commit()
    # Se aprueba primero la ANTIGUA, así que el orden de emisión y el de publicación difieren.
    for ident in ("BOE-A-2023-0001", "BOE-A-2024-0001"):
        norma = sesion_db.scalar(select(Norma).where(Norma.identificador_oficial == ident))
        assert norma is not None
        deteccion = sesion_db.scalar(select(Deteccion).where(Deteccion.norma_id == norma.id))
        assert deteccion is not None
        cola = sesion_db.scalar(
            select(ColaRevision).where(ColaRevision.deteccion_id == deteccion.id)
        )
        assert cola is not None
        servicio.aprobar(sesion_db, cola.id)

    fechas = [a["fecha_publicacion"] for a in client.get("/api/alertas").json()]

    assert fechas == ["2024-05-29", "2023-03-01"]


def test_una_alerta_sin_cuerpo_archivado_no_rompe(client: TestClient, sesion_db: Session) -> None:
    """`texto_archivado` a null es información, no un hueco: no hay huella que ofrecer."""
    deteccion = _norma_con_deteccion(sesion_db, ident="BOE-A-2024-0009", con_cuerpo=False)
    sesion_db.add(ColaRevision(deteccion_id=deteccion.id, estado=EstadoRevision.PENDIENTE))
    sesion_db.commit()
    cola = sesion_db.scalar(select(ColaRevision))
    assert cola is not None
    servicio.aprobar(sesion_db, cola.id)

    assert client.get("/api/alertas").json()[0]["texto_archivado"] is None


def test_el_tamano_de_pagina_lo_decide_el_servidor(client: TestClient) -> None:
    assert client.get("/api/alertas", params={"limite": 101}).status_code == 422
    assert client.get("/api/alertas", params={"desplazamiento": -1}).status_code == 422


def test_alerta_inexistente_da_404(client: TestClient) -> None:
    assert client.get("/api/alertas/9999").status_code == 404
