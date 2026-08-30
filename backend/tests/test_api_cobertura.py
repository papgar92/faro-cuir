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


def test_cuenta_los_boletines_archivados_y_no_los_cuerpos(
    client: TestClient, sesion_db: Session
) -> None:
    """La cifra que la portada llama «documentos archivados».

    Vivía como `len()` de `GET /api/documentos`, que tiene tope 100: con 162 sumarios en el
    almacén, la franja de la portada decía **100**. Una lista topada contada por su longitud no
    es un total, y el componente que la enseña existe justamente para no mentir sobre el volumen
    del sistema.

    Se cuentan **sumarios**, no cuerpos ni consolidados, por lo mismo que `GET /api/documentos`
    solo lista sumarios (ADR 0015).
    """
    fuente = _fuente(sesion_db, codigo="CT")
    _normas(sesion_db, fuente, EstadoPrefiltro.DESCARTADA)
    sesion_db.add(
        Documento(
            fuente_id=fuente.id,
            identificador_oficial="CUERPO-1",
            fecha_publicacion=datetime.date(2024, 12, 31),
            url_original="https://ejemplo.invalid/cuerpo",
            sha256="f" * 64,
            sello_tiempo=datetime.datetime.now(datetime.UTC),
            ruta_almacen="ff/ff/" + "f" * 64 + ".xml",
            estado_pipeline=EstadoPipeline.INGERIDO,
            tipo=TipoDocumento.TEXTO_NORMA,
        )
    )
    sesion_db.commit()

    assert client.get("/api/cobertura").json()["documentos"] == 1


def test_publica_que_comunidades_no_tienen_ley_autonomica(
    client: TestClient, sesion_db: Session
) -> None:
    """El dato estaba verificado en la watchlist y no llegaba a ninguna pantalla.

    Sin él, el mapa pintaba igual dos silencios opuestos: Aragón sin alertas es «hay dos leyes
    vigiladas y nadie las ha tocado», y Castilla y León sin alertas es «no hay ninguna ley que
    tocar». Con el mismo relleno, el segundo se lee como tranquilidad — que es exactamente lo
    que este mapa existe para no hacer.

    Es un hecho verificado con su fecha, no una valoración (regla de oro 2).
    """
    _fuente(sesion_db, codigo="CL")
    sesion_db.commit()

    por_ccaa = {c["ccaa_codigo"]: c for c in client.get("/api/cobertura").json()["por_ccaa"]}

    assert "no tiene ley autonomica LGTBI" in por_ccaa["CL"]["sin_ley_autonomica"]


def test_una_comunidad_sin_ley_sale_aunque_no_tenga_ninguna_fuente_registrada(
    client: TestClient, sesion_db: Session
) -> None:
    """Asturias es uniprovincial: no tiene BOP propio, así que no tiene ninguna fila en `fuente`.

    `por_ccaa` se construye agrupando esa tabla, de modo que Asturias no aparecía en la respuesta
    y su ausencia de marco no habría llegado nunca al mapa. Es la mitad del dato, y la mitad que
    menos se ve.
    """
    respuesta = client.get("/api/cobertura").json()
    por_ccaa = {c["ccaa_codigo"]: c for c in respuesta["por_ccaa"]}

    assert "AS" in por_ccaa
    assert por_ccaa["AS"]["conocidas"] == 0
    assert "no tiene ley autonomica LGTBI" in por_ccaa["AS"]["sin_ley_autonomica"]
    # Añadir la fila no puede inflar los totales, que se suman de la consulta y no del diccionario.
    assert respuesta["conocidas"] == 0


def test_una_comunidad_con_ley_no_lleva_el_campo(client: TestClient, sesion_db: Session) -> None:
    """`None` significa «sí tiene ley», no «no lo sabemos»: la watchlist lo tiene verificado."""
    _fuente(sesion_db, codigo="AR")
    sesion_db.commit()

    por_ccaa = {c["ccaa_codigo"]: c for c in client.get("/api/cobertura").json()["por_ccaa"]}

    assert por_ccaa["AR"]["sin_ley_autonomica"] is None


def test_publica_la_linea_base_de_leyes_vigentes(client: TestClient, sesion_db: Session) -> None:
    """La línea base: qué marco protector EXISTE hoy, sobre el que las alertas son el delta.

    El mapa solo sabía pintar *cambios*, y el ADR 0027 midió que eso son ~5 casos al año: quince
    comunidades en blanco no porque no pase nada, sino porque el mapa no sabía decir qué hay.
    """
    _fuente(sesion_db, codigo="AR")
    sesion_db.commit()

    por_ccaa = {c["ccaa_codigo"]: c for c in client.get("/api/cobertura").json()["por_ccaa"]}

    tipos = {ley["tipo"] for ley in por_ccaa["AR"]["leyes_vigentes"]}
    assert tipos == {"trans", "lgtbi"}
    assert all(
        ley["identificador"].startswith("BOE-A-") for ley in por_ccaa["AR"]["leyes_vigentes"]
    )


def test_una_ley_derogada_no_cuenta_como_marco_vigente(
    client: TestClient, sesion_db: Session
) -> None:
    """Euskadi tiene DOS entradas en la watchlist y una está derogada (Ley 14/2012).

    Se sigue vigilando a propósito —una norma derogada aparece en las referencias de las que la
    citan, y perder ese rastro sería perder el histórico—, pero **no es marco vigente**. Sin esta
    distinción la línea base diría que Euskadi tiene una ley que ya no existe.
    """
    por_ccaa = {c["ccaa_codigo"]: c for c in client.get("/api/cobertura").json()["por_ccaa"]}

    identificadores = {ley["identificador"] for ley in por_ccaa["PV"]["leyes_vigentes"]}

    assert "BOE-A-2024-4867" in identificadores
    assert "BOE-A-2012-9664" not in identificadores


def test_la_linea_base_cubre_las_diecisiete_comunidades(client: TestClient) -> None:
    """Sin huecos: o hay leyes vigentes, o está verificado que no hay ley. Nunca silencio.

    Es la misma exigencia que el embudo del prefiltro (7.2): lo que el sistema no puede decir se
    cuenta, no se omite. Una comunidad que no apareciera aquí se pintaría igual que una sin ley.
    """
    por_ccaa = client.get("/api/cobertura").json()["por_ccaa"]

    con_marco = [c for c in por_ccaa if c["leyes_vigentes"] or c["sin_ley_autonomica"]]

    assert len(con_marco) == 17
