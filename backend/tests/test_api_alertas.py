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
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import alertas as api_alertas
from app.database import Base
from app.models.deteccion import (
    Alerta,
    Clasificacion,
    ColaRevision,
    Deteccion,
    EstadoRevision,
    OrigenClasificacion,
)
from app.models.documento import Documento, EstadoPipeline, TipoDocumento
from app.models.fuente import AmbitoTerritorial, FormatoFuente, Fuente, TipoFuente
from app.models.norma import EstadoPrefiltro, Norma, VersionNorma
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
    # Diagnóstico del ADR 0018. La cifra viaja en la evidencia y no se cuenta al vuelo: es lo que
    # permite que el listado, que no trae los textos, diga cuántos preceptos hay archivados.
    "terminos_perdidos": ["identidad de genero", "autodeterminacion de genero"],
    "preceptos_con_diff": 2,
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


# --- El diff en la alerta (ADR 0018) --------------------------------------------------------


def _aprobar(session: Session, deteccion: Deteccion) -> Alerta:
    session.add(ColaRevision(deteccion_id=deteccion.id, estado=EstadoRevision.APROBADA))
    alerta = Alerta(deteccion_id=deteccion.id, emitida_en=datetime.datetime.now(datetime.UTC))
    session.add(alerta)
    session.commit()
    return alerta


def _versionar(session: Session, norma_id: int, *, afectada: str = "BOE-A-2016-6728") -> None:
    """Archiva un consolidado y dos preceptos reescritos, como haría `services/versionado`."""
    consolidado = Documento(
        fuente_id=1,
        identificador_oficial=f"{afectada}-consolidado-abc123abc123",
        fecha_publicacion=datetime.date(2026, 8, 15),
        url_original=(
            f"https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/{afectada}"
        ),
        sha256="c" * 64,
        sello_tiempo=datetime.datetime.now(datetime.UTC),
        ruta_almacen="cc/dd/consolidado.xml",
        estado_pipeline=EstadoPipeline.INGERIDO,
        tipo=TipoDocumento.CONSOLIDADO,
    )
    session.add(consolidado)
    session.flush()
    for ordinal, (bloque, articulo, antes, ahora) in enumerate(
        [
            (
                "a4",
                "Artículo 4",
                "Reconocimiento del derecho a la identidad de género libremente manifestada.",
                "Reconocimiento del respeto a la libertad y dignidad de las personas transexuales.",
            ),
            ("a7", "Artículo 7", "Documentación administrativa. 1. Las Administraciones…", None),
        ],
        start=1,
    ):
        session.add(
            VersionNorma(
                norma_id=norma_id,
                norma_afectada=afectada,
                bloque=bloque,
                articulo=articulo,
                documento_consolidado_id=consolidado.id,
                texto_anterior=antes,
                texto_nuevo=ahora,
                ordinal=ordinal,
                version_derivacion="2026.08.15.1",
            )
        )
    session.commit()


class TestDiffPublicado:
    def test_el_listado_trae_una_muestra_recortada_y_no_los_36_preceptos(
        self, client: TestClient, sesion_db: Session
    ) -> None:
        """El equilibrio de la pantalla más vista: enseñar algo sin mandar varios megas.

        Una tarjeta que anuncia «34 preceptos modificados» y no enseña ninguno pide que te fíes.
        Los 34 enteros en cada elemento del listado son varios megas por página. Así que va uno,
        recortado, y el resto en el detalle.
        """
        deteccion = _norma_con_deteccion(sesion_db, ident="BOE-A-2024-10767")
        _versionar(sesion_db, deteccion.norma_id)
        _aprobar(sesion_db, deteccion)

        cuerpo = client.get("/api/alertas").json()

        assert len(cuerpo) == 1
        assert cuerpo[0]["preceptos_con_diff"] == 2
        assert cuerpo[0]["terminos_perdidos"] == [
            "identidad de genero",
            "autodeterminacion de genero",
        ]
        # Uno, no los dos que hay archivados: el listado enseña, el detalle documenta.
        assert len(cuerpo[0]["cambios"]) == 1
        assert cuerpo[0]["cambios"][0]["bloque"] == "a4"
        assert len(cuerpo[0]["cambios"][0]["texto_anterior"]) <= 710

    def test_el_detalle_trae_las_dos_redacciones_con_la_huella_del_consolidado(
        self, client: TestClient, sesion_db: Session
    ) -> None:
        """Sin decir de qué documento salen y con qué huella, el diff hay que creérselo."""
        deteccion = _norma_con_deteccion(sesion_db, ident="BOE-A-2024-10767")
        _versionar(sesion_db, deteccion.norma_id)
        alerta = _aprobar(sesion_db, deteccion)

        cuerpo = client.get(f"/api/alertas/{alerta.id}").json()

        assert [c["bloque"] for c in cuerpo["cambios"]] == ["a4", "a7"]
        a4 = cuerpo["cambios"][0]
        assert "identidad de género libremente manifestada" in a4["texto_anterior"]
        assert "personas transexuales" in a4["texto_nuevo"]
        assert a4["consolidado_sha256"] == "c" * 64
        assert a4["truncado"] is False
        # Una supresión llega con la redacción nueva a NULL, y eso significa "ya no hay texto".
        assert cuerpo["cambios"][1]["texto_nuevo"] is None

    def test_no_se_cuela_el_diff_de_otra_norma_afectada(
        self, client: TestClient, sesion_db: Session
    ) -> None:
        """Una versión de otra norma vigilada no sostiene esta alerta, así que no se publica."""
        deteccion = _norma_con_deteccion(sesion_db, ident="BOE-A-2024-10767")
        _versionar(sesion_db, deteccion.norma_id)
        _versionar(sesion_db, deteccion.norma_id, afectada="BOE-A-2016-11096")
        alerta = _aprobar(sesion_db, deteccion)

        cuerpo = client.get(f"/api/alertas/{alerta.id}").json()

        assert {c["norma_afectada"] for c in cuerpo["cambios"]} == {"BOE-A-2016-6728"}

    def test_una_alerta_sin_diff_no_finge_tenerlo(
        self, client: TestClient, sesion_db: Session
    ) -> None:
        deteccion = _norma_con_deteccion(sesion_db, ident="BOE-A-2024-0009")
        alerta = _aprobar(sesion_db, deteccion)

        cuerpo = client.get(f"/api/alertas/{alerta.id}").json()

        assert cuerpo["cambios"] == []

    def test_un_diff_archivado_despues_de_aprobar_no_se_publica(
        self, client: TestClient, sesion_db: Session
    ) -> None:
        """Regla de oro 4 aplicada a un dato que llega tarde. Lo encontró la auditoría del 16/08.

        R-MOD-001 dispara aunque el diff no exista todavía, y la consolidación del BOE tarda días.
        Sin este filtro, una alerta aprobada el martes empezaba a publicar el viernes dos
        redacciones literales que **nadie revisó nunca**, colgadas de una aprobación vieja.
        """
        deteccion = _norma_con_deteccion(sesion_db, ident="BOE-A-2024-10767")
        alerta = _aprobar(sesion_db, deteccion)
        # El versionado llega después: es el caso normal, no un ataque.
        _versionar(sesion_db, deteccion.norma_id)
        sesion_db.execute(
            update(VersionNorma).values(creada_en=alerta.emitida_en + datetime.timedelta(hours=2))
        )
        sesion_db.commit()

        cuerpo = client.get(f"/api/alertas/{alerta.id}").json()

        assert cuerpo["cambios"] == []


def test_el_filtro_usa_el_signo_que_se_ve_y_no_el_de_la_regla(
    client: TestClient, sesion_db: Session
) -> None:
    """El filtro y la pantalla tienen que hablar de lo mismo.

    `clasificacion` (la regla) y `clasificacion_humana` (la persona) son dos columnas distintas a
    propósito, y la tarjeta enseña la segunda cuando existe. Mientras el filtro miró solo la
    primera, el resultado era el que se vio usando la web el 2026-08-22: tres alertas cuya regla
    se abstuvo y a las que una persona puso «avance» no salían en «Avances», y sí salían en «Sin
    signo» — es decir, la pantalla enseñaba tarjetas que ponen «Avance» bajo el filtro de las que
    no tienen ninguno.

    Este test siembra exactamente ese caso: una alerta que la regla dejó en `indeterminado` y que
    una persona marcó como avance, más otra que nadie tocó.
    """
    con_persona = _norma_con_deteccion(sesion_db, ident="BOE-A-2021-18287", con_regla=False)
    sin_persona = _norma_con_deteccion(sesion_db, ident="BOE-A-2023-5366", con_regla=False)
    sesion_db.add_all(
        [
            ColaRevision(deteccion_id=con_persona.id, estado=EstadoRevision.PENDIENTE),
            ColaRevision(deteccion_id=sin_persona.id, estado=EstadoRevision.PENDIENTE),
        ]
    )
    sesion_db.commit()

    cola_con = sesion_db.scalar(
        select(ColaRevision).where(ColaRevision.deteccion_id == con_persona.id)
    )
    cola_sin = sesion_db.scalar(
        select(ColaRevision).where(ColaRevision.deteccion_id == sin_persona.id)
    )
    assert cola_con is not None and cola_sin is not None
    servicio.aprobar(sesion_db, cola_con.id, nota="Leído entero.", clasificacion="avance")
    servicio.aprobar(sesion_db, cola_sin.id, nota="Sin decidir el signo.")

    avances = client.get("/api/alertas", params={"clasificacion": "avance"}).json()
    sin_signo = client.get("/api/alertas", params={"clasificacion": "indeterminado"}).json()

    # La que decidió una persona sale bajo SU signo...
    assert [a["norma"]["identificador_oficial"] for a in avances] == ["BOE-A-2021-18287"]
    # ...y no contamina el cajón de las que no tienen ninguno.
    assert [a["norma"]["identificador_oficial"] for a in sin_signo] == ["BOE-A-2023-5366"]
