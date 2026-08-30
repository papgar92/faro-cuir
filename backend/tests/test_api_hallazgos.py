"""Tests de la API pública de hallazgos históricos. ADR 0025, decisiones 3 y 4.

El test que justifica el fichero entero es `test_solo_sale_lo_corroborado_y_sin_aprobar`: se
siembran a la vez los cuatro informes que pueden existir —semáforo `mirar`, `alerta` sin
corroborar, `alerta` ya aprobado y `alerta` corroborado sin aprobar— y se comprueba que **solo
sale el último**. Las otras tres son las tres formas de publicar algo que este proyecto no puede
publicar:

- un `mirar` es material de trabajo, no una conclusión de nadie;
- un `alerta` **sin corroborar** sería «un asistente de IA cree que esto es un retroceso»,
  publicado, que es el juicio propio que prohíbe la regla de oro 2;
- un `alerta` **ya aprobado** es una alerta, y saldría dos veces por dos rutas distintas
  diciendo cosas distintas sobre la misma detección.

SQLite en memoria y una app propia con solo este router, mismo criterio que
`test_api_alertas.py`: el limitador del `app` real es global al proceso.
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

from app.api import hallazgos as api_hallazgos
from app.database import Base
from app.models.deteccion import (
    Clasificacion,
    ColaRevision,
    Deteccion,
    EstadoRevision,
    InformeRevision,
    OrigenClasificacion,
    Semaforo,
)
from app.models.documento import Documento, EstadoPipeline, TipoDocumento
from app.models.fuente import AmbitoTerritorial, FormatoFuente, Fuente, TipoFuente
from app.models.norma import EstadoPrefiltro, Norma, VersionNorma
from app.pipeline import watchlist
from app.pipeline.watchlist import NormaVigilada, Watchlist
from app.services import revision as servicio_revision

LISTA = Watchlist(
    version="test",
    normas=(
        NormaVigilada(
            identificador="BOE-A-2006-16212",
            titulo="RD 1030/2006, cartera de servicios comunes del SNS",
            nota="fixture",
            ambito="ES",
        ),
    ),
)

EVIDENCIA = {
    "regla": "R-MOD-001",
    "version_reglas": "2026.08.20.3",
    "version_texto_plano": "2026.08.16",
    "normas_vigiladas": ["BOE-A-2006-16212"],
    "spans": [{"inicio": 100, "fin": 140, "fragmento": "queda redactado como sigue"}],
    "terminos_perdidos": [],
    "preceptos_con_diff": 1,
}

CORROBORACION = [
    {
        "organizacion": "Ministerio de Sanidad",
        "que_dice": (
            "Reconoce en el preámbulo de una orden posterior que estos criterios excluyeron."
        ),
        "url": "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2021-18287",
    }
]


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
    aplicacion.include_router(api_hallazgos.router)
    aplicacion.dependency_overrides[api_hallazgos.get_session] = lambda: sesion_db
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


def _deteccion(
    session: Session, *, ident: str, fecha: datetime.date = datetime.date(2014, 11, 6)
) -> Deteccion:
    sumario = _sumario(session, fecha)
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
        titulo=f"Orden {ident}",
        url_texto=f"https://www.boe.es/diario_boe/xml.php?id={ident}",
        documento_texto_id=cuerpo.id,
        prefiltro_estado=EstadoPrefiltro.RELEVANTE,
        prefiltro_terminos=[],
        prefiltro_evaluado_en=datetime.datetime.now(datetime.UTC),
    )
    session.add(norma)
    session.flush()
    deteccion = Deteccion(
        norma_id=norma.id,
        extraccion_json={"extraccion": {"articulos": []}, "modelo": "qwen2.5:3b-instruct"},
        clasificacion=Clasificacion.INDETERMINADO,
        origen=OrigenClasificacion.DERIVADO_DIFF,
        regla_aplicada="R-MOD-001",
        evidencia_json=EVIDENCIA,
        severidad=3,
        confianza=0.7,
    )
    session.add(deteccion)
    session.flush()
    return deteccion


def _con_informe(
    session: Session,
    *,
    ident: str,
    semaforo: Semaforo,
    corroboraciones: list[dict[str, str]],
    fecha: datetime.date = datetime.date(2014, 11, 6),
) -> ColaRevision:
    deteccion = _deteccion(session, ident=ident, fecha=fecha)
    cola = ColaRevision(deteccion_id=deteccion.id, estado=EstadoRevision.PENDIENTE)
    session.add(cola)
    session.flush()
    session.add(
        InformeRevision(
            cola_revision_id=cola.id,
            semaforo=semaforo,
            resumen=("Ata el acceso a un diagnóstico que solo se tiene en pareja heterosexual."),
            a_quien_afecta=("A una mujer lesbiana, a una sin pareja y a un hombre trans gestante."),
            recomendacion="A alerta, con signo retroceso.",
            refutacion="Que la redacción anterior ya exigiera estudio de esterilidad.",
            citas=[{"texto": "coito vaginal", "apartado": "5.3.8.1.a)", "version": "nueva"}],
            corroboraciones=corroboraciones,
            generado_por="asistente de IA (sin revisión humana)",
        )
    )
    session.flush()
    return cola


def test_solo_sale_lo_corroborado_y_sin_aprobar(client: TestClient, sesion_db: Session) -> None:
    """Los cuatro informes posibles a la vez. Sale uno.

    Es la decisión 4 del ADR 0025 vista desde fuera de la API, y el motivo de que las tres
    condiciones vivan en el `where` de `services/hallazgos.consulta()` y no en un bucle.
    """
    _con_informe(
        sesion_db, ident="BOE-A-2014-0001", semaforo=Semaforo.MIRAR, corroboraciones=CORROBORACION
    )
    _con_informe(sesion_db, ident="BOE-A-2014-0002", semaforo=Semaforo.ALERTA, corroboraciones=[])
    aprobado = _con_informe(
        sesion_db, ident="BOE-A-2014-0003", semaforo=Semaforo.ALERTA, corroboraciones=CORROBORACION
    )
    _con_informe(
        sesion_db, ident="BOE-A-2014-0004", semaforo=Semaforo.ALERTA, corroboraciones=CORROBORACION
    )
    sesion_db.commit()
    servicio_revision.aprobar(sesion_db, aprobado.id, nota="Verificado contra el BOE.")

    hallazgos = client.get("/api/hallazgos").json()

    assert [h["norma"]["identificador_oficial"] for h in hallazgos] == ["BOE-A-2014-0004"]


def test_aprobar_un_hallazgo_lo_saca_de_aqui(client: TestClient, sesion_db: Session) -> None:
    """Deja de ser hallazgo en cuanto alguien lo revisa, sin que nadie lo mueva de sitio.

    Es la prueba de que las dos superficies del ADR 0025 no son una etiqueta: la misma detección
    cambia de sitio porque cambió la base, no porque un campo diga otra cosa.
    """
    cola = _con_informe(
        sesion_db, ident="BOE-A-2014-11444", semaforo=Semaforo.ALERTA, corroboraciones=CORROBORACION
    )
    sesion_db.commit()
    assert len(client.get("/api/hallazgos").json()) == 1
    hallazgo_id = client.get("/api/hallazgos").json()[0]["id"]

    servicio_revision.aprobar(sesion_db, cola.id, nota="Revisado.")

    assert client.get("/api/hallazgos").json() == []
    # Y el detalle también deja de responder, porque sale de la misma consulta.
    assert client.get(f"/api/hallazgos/{hallazgo_id}").status_code == 404


def test_no_publica_la_opinion_del_asistente(client: TestClient, sesion_db: Session) -> None:
    """`recomendacion` y `semaforo` NO salen a la web. Regla de oro 2.

    Lo que un hallazgo afirma son dos hechos verificables y ninguno nuestro: que el cambio
    ocurrió y que alguien con nombre ya lo denunció. «Yo publicaría esto» no es ninguno de los
    dos. `refutacion` sí sale, y va aquí junto a la comprobación para que se vea que la que se
    quita es la opinión, no la autocrítica.
    """
    _con_informe(
        sesion_db, ident="BOE-A-2014-11444", semaforo=Semaforo.ALERTA, corroboraciones=CORROBORACION
    )
    sesion_db.commit()

    informe = client.get("/api/hallazgos").json()[0]["informe"]

    assert "recomendacion" not in informe
    assert "semaforo" not in informe
    assert informe["refutacion"]
    assert informe["corroboraciones"][0]["organizacion"] == "Ministerio de Sanidad"
    assert informe["generado_por"] == "asistente de IA (sin revisión humana)"


def test_dice_que_no_lo_ha_revisado_nadie(client: TestClient, sesion_db: Session) -> None:
    """El campo que separa esto de una alerta viaja siempre y solo puede valer `False`."""
    _con_informe(
        sesion_db, ident="BOE-A-2014-11444", semaforo=Semaforo.ALERTA, corroboraciones=CORROBORACION
    )
    sesion_db.commit()

    hallazgo = client.get("/api/hallazgos").json()[0]

    assert hallazgo["revisado_por_humano"] is False
    # Un hallazgo no tiene fecha de emisión porque nadie lo emitió: lleva cuándo se escribió el
    # informe, que es otra cosa y se llama distinto a propósito.
    assert "emitida_en" not in hallazgo
    assert hallazgo["generado_en"]


def test_no_publica_preceptos_que_el_informe_no_pudo_ver(
    client: TestClient, sesion_db: Session
) -> None:
    """El corte temporal de `hallazgos.corte_temporal`, que es `generado_en`.

    El BOE consolida con retraso (por eso existe `--versionar`). Un precepto archivado DESPUÉS de
    escribirse el informe no lo vio ni el asistente ni nadie, así que publicarlo colgado de este
    hallazgo sería presentarlo como parte de lo que el informe dijo. Es el mismo agujero que la
    auditoría del 2026-08-16 encontró en las alertas, con otro dueño.
    """
    cola = _con_informe(
        sesion_db, ident="BOE-A-2014-11444", semaforo=Semaforo.ALERTA, corroboraciones=CORROBORACION
    )
    deteccion = sesion_db.get(Deteccion, cola.deteccion_id)
    assert deteccion is not None
    informe = sesion_db.scalar(
        select(InformeRevision).where(InformeRevision.cola_revision_id == cola.id)
    )
    assert informe is not None
    consolidado = _sumario(sesion_db, datetime.date(2014, 11, 6))

    antes = informe.generado_en - datetime.timedelta(days=1)
    despues = informe.generado_en + datetime.timedelta(days=7)
    sesion_db.add_all(
        [
            VersionNorma(
                norma_id=deteccion.norma_id,
                norma_afectada="BOE-A-2006-16212",
                articulo="5.3.8.1.a)",
                bloque="A3",
                texto_anterior="lo que decia antes",
                texto_nuevo="visto por el informe",
                documento_consolidado_id=consolidado.id,
                ordinal=1,
                version_derivacion="2026.08.15.1",
                creada_en=antes,
            ),
            VersionNorma(
                norma_id=deteccion.norma_id,
                norma_afectada="BOE-A-2006-16212",
                articulo="5.3.8.2",
                bloque="A4",
                texto_anterior="lo que decia antes",
                texto_nuevo="LLEGO DESPUES Y NADIE LO HA VISTO",
                documento_consolidado_id=consolidado.id,
                ordinal=2,
                version_derivacion="2026.08.15.1",
                creada_en=despues,
            ),
        ]
    )
    sesion_db.commit()

    detalle = client.get(f"/api/hallazgos/{informe.id}").json()

    textos = [c["texto_nuevo"] for c in detalle["cambios"]]
    assert "visto por el informe" in textos
    assert "LLEGO DESPUES Y NADIE LO HA VISTO" not in textos
