"""Tests de la API publica de solo lectura.

Se monta la app contra un SQLite en memoria sobreescribiendo la dependencia de sesion, asi
que no hace falta Postgres. Lo que se comprueba no es que FastAPI sepa serializar, sino las
decisiones propias: que no se filtren campos internos, que la paginacion tenga tope y que la
API siga sin exponer escrituras.
"""

from __future__ import annotations

import datetime
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.documentos import get_session
from app.database import Base
from app.main import app
from app.models.fuente import AmbitoTerritorial, FormatoFuente, Fuente, TipoFuente
from app.services import ingesta
from app.services import prefiltro as servicio_prefiltro

FIXTURES = Path(__file__).parent / "fixtures"
FECHA = datetime.date(2024, 12, 19)


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    # El TestClient atiende las peticiones en otro hilo, y una base SQLite en memoria vive
    # dentro de una conexion: con el pool por defecto, cada hilo abriria la suya y veria una
    # base vacia. StaticPool mantiene una unica conexion compartida, y check_same_thread=False
    # permite usarla desde el hilo del servidor. Solo aplica a los tests.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    fabrica = sessionmaker(bind=engine)

    with fabrica() as sesion:
        fuente = Fuente(
            nombre="Boletín Oficial del Estado",
            tipo=TipoFuente.BOE,
            # El BOE es la fuente estatal. NOT NULL sin valor por defecto a propósito
            # (ADR 0014): un ámbito por defecto colaría un territorio inventado.
            ambito_territorial=AmbitoTerritorial.ESTATAL,
            ccaa=None,
            formato=FormatoFuente.API,
            url_base="https://www.boe.es/datosabiertos/api/boe/sumario/",
            licencia_reutil=None,
            activa=True,
        )
        sesion.add(fuente)
        sesion.commit()

        contenido = (FIXTURES / "boe_sumario_20241219_recortado.xml").read_bytes()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=contenido)

        with httpx.Client(transport=httpx.MockTransport(handler)) as http:
            ingesta.ingerir_sumario_boe(
                sesion, fuente_id=fuente.id, fecha=FECHA, almacen_root=tmp_path, client=http
            )

    def _session_de_prueba() -> Iterator[Session]:
        with fabrica() as sesion:
            yield sesion

    app.dependency_overrides[get_session] = _session_de_prueba
    with TestClient(app) as cliente:
        yield cliente
    app.dependency_overrides.clear()
    engine.dispose()


def test_lista_los_documentos_ingeridos(client: TestClient) -> None:
    respuesta = client.get("/api/documentos")
    assert respuesta.status_code == 200
    (documento,) = respuesta.json()
    assert documento["identificador_oficial"] == "BOE-S-2024-305"
    assert documento["fecha_publicacion"] == "2024-12-19"


def test_publica_la_huella_para_que_el_archivo_sea_comprobable(client: TestClient) -> None:
    """El sha256 se expone a proposito (6.5): quien reciba una alerta debe poder verificar
    por su cuenta que el contenido archivado es el que se publico."""
    (documento,) = client.get("/api/documentos").json()
    assert len(documento["sha256"]) == 64
    assert documento["sello_tiempo"]


def test_no_expone_la_ruta_interna_del_almacen(client: TestClient) -> None:
    """Publicar rutas del sistema de ficheros del servidor solo regala informacion."""
    (documento,) = client.get("/api/documentos").json()
    assert "ruta_almacen" not in documento


def test_el_detalle_incluye_las_normas(client: TestClient) -> None:
    documento_id = client.get("/api/documentos").json()[0]["id"]
    detalle = client.get(f"/api/documentos/{documento_id}").json()

    assert len(detalle["normas"]) == 2
    norma = next(n for n in detalle["normas"] if n["identificador_oficial"] == "BOE-A-2024-26484")
    assert norma["titulo"].startswith("Orden HAC/1432/2024")
    assert norma["organo_emisor"] == "MINISTERIO DE HACIENDA"
    # Nulos hasta que el extractor procese el texto completo: no se deducen del titulo.
    assert norma["rango"] is None
    assert norma["ambito"] is None


def test_documento_inexistente_da_404(client: TestClient) -> None:
    assert client.get("/api/documentos/99999").status_code == 404


def test_filtra_por_fecha(client: TestClient) -> None:
    assert len(client.get("/api/documentos", params={"fecha": "2024-12-19"}).json()) == 1
    assert client.get("/api/documentos", params={"fecha": "2024-12-20"}).json() == []


def test_el_tamano_de_pagina_lo_decide_el_servidor(client: TestClient) -> None:
    """API publica sin auth: sin tope, un ?limite=1000000 es una denegacion de servicio gratis."""
    assert client.get("/api/documentos", params={"limite": 101}).status_code == 422
    assert client.get("/api/documentos", params={"limite": 0}).status_code == 422
    assert client.get("/api/documentos", params={"desplazamiento": -1}).status_code == 422


def test_la_api_publica_no_expone_ninguna_escritura(client: TestClient) -> None:
    """Lo que modifica el estado es el worker y el panel de revision, que va con autenticacion.

    El panel (`/api/revision`, ADR 0017) es la **unica** excepcion y esta escrita aqui como
    excepcion nombrada, no como un `<=` relajado: si manana aparece un POST en cualquier otro
    sitio de la API publica, este test tiene que ponerse rojo. Que se pusiera rojo al montar el
    panel es exactamente para lo que estaba.
    """
    rutas = app.openapi()["paths"]
    metodos = {
        metodo.upper()
        for camino, ruta in rutas.items()
        for metodo in ruta
        if not camino.startswith("/api/revision")
    }
    assert metodos <= {"GET"}, f"la API expone metodos de escritura: {metodos - {'GET'}}"


def test_publica_el_estado_del_prefiltro(client: TestClient) -> None:
    """El embudo se expone a proposito (ADR 0007).

    Un filtro que decide en silencio que se mira y que no es justo lo que este proyecto
    denuncia en la administracion; el nuestro tiene que poder auditarse desde fuera.
    """
    documento_id = client.get("/api/documentos").json()[0]["id"]
    normas = client.get(f"/api/documentos/{documento_id}").json()["normas"]

    # La fixture solo ingiere, no pasa el prefiltro: las normas estan sin evaluar.
    for norma in normas:
        assert norma["prefiltro_estado"] == "pendiente"
        # None, no lista vacia: "sin evaluar" no es lo mismo que "evaluada y sin coincidencias".
        assert norma["prefiltro_terminos"] is None


def test_el_prefiltro_aplicado_se_ve_en_la_api(client: TestClient, tmp_path: Path) -> None:
    documento_id = client.get("/api/documentos").json()[0]["id"]

    with next(app.dependency_overrides[get_session]()) as sesion:  # type: ignore[misc]
        # Las normas de esta fixture no tienen cuerpo archivado, así que el prefiltro no llega
        # a abrir el almacén; `tmp_path` está aquí para satisfacer la firma, no porque se lea.
        servicio_prefiltro.aplicar(sesion, almacen_root=tmp_path, documento_id=documento_id)

    normas = client.get(f"/api/documentos/{documento_id}").json()["normas"]
    for norma in normas:
        # Los cuatro estados de CLAUDE.md 7.2. `descartada` ya no puede salir de una pasada
        # sobre el sumario (7.1), pero se admite aqui porque la API tiene que poder publicarlo
        # cuando el worker evalue sobre el texto integro (tarea 0.c).
        assert norma["prefiltro_estado"] in {"pendiente", "sospecha", "relevante", "descartada"}
        # Ya evaluadas: lista (vacia si no disparo nada), nunca None.
        assert isinstance(norma["prefiltro_terminos"], list)
