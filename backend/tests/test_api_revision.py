"""Tests del panel de revisión: la API del gate humano (regla de oro 4, ADR 0017).

SQLite en memoria y una app propia que monta solo este router. Lo segundo es deliberado: el
`app` real lleva el limitador de peticiones, que es global al proceso y compartido con los demás
tests de API, así que usarlo aquí haría que estos tests fallasen o no según el orden en que
corriera la suite. El cableado del router en la app real se comprueba aparte, inspeccionando las
rutas, y los middlewares tienen sus propios tests en `test_seguridad_http.py`.

La base de datos se sirve por `https://` porque la cookie de sesión es `Secure` y un cliente que
respete la norma no la devolvería por `http://`. Que el test tuviera que cambiar eso es, de por
sí, la comprobación de que el atributo está puesto.

Lo que se prueba aquí es lo que este proyecto no se puede permitir: que nadie apruebe una alerta
sin sesión, que no se pueda aprobar dos veces, que un `GET` no resuelva nada y que la fila de
`alerta` no aparezca por ningún otro camino.
"""

from __future__ import annotations

import datetime
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import revision as api_revision
from app.config import get_settings
from app.database import Base
from app.main import app as app_real
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
from app.models.norma import EstadoPrefiltro, Norma
from app.security import panel
from app.services import revision as servicio

PASSWORD = "contraseña del panel de revisión"
HASH = panel.generar_hash(PASSWORD)
CABECERA = {api_revision.CABECERA_PANEL: "1"}

EVIDENCIA = {
    "regla": "R-SUP-001",
    "version_reglas": "2026.08.14",
    "version_texto_plano": "2026.08.09",
    "normas_vigiladas": ["BOE-A-2016-6728"],
    "spans": [
        {"inicio": 100, "fin": 140, "fragmento": "Se suprime el artículo 7."},
        {"inicio": 200, "fin": 245, "fragmento": "Se suprime el título X."},
    ],
    "punteros_corroborados": ["art. 7"],
    "punteros_sin_corroborar": [],
    "clasificado_en": "2026-08-14T10:00:00+00:00",
}


@pytest.fixture(autouse=True)
def panel_configurado(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Contraseña del panel y estado limpio de sesiones y cadencia en cada test."""
    monkeypatch.setattr(get_settings(), "panel_password_hash", HASH)
    api_revision._sesiones.cerrar_todas()
    api_revision._cadencia = panel.CadenciaIntentos(intentos=10, ventana_segundos=60)
    yield
    api_revision._sesiones.cerrar_todas()


def _sembrar(session: Session, *, con_regla: bool = True) -> Norma:
    """Un documento, su norma y una detección. Con regla = veredicto; sin ella = centinela."""
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

    indice = session.query(Norma).count()
    ident = f"BOE-A-2024-1076{indice}"
    sumario = session.scalar(select(Documento).where(Documento.tipo == TipoDocumento.SUMARIO))
    if sumario is None:
        sumario = Documento(
            fuente_id=fuente.id,
            identificador_oficial="BOE-S-2024-130",
            fecha_publicacion=datetime.date(2024, 5, 29),
            url_original="https://www.boe.es/datosabiertos/api/boe/sumario/20240529",
            sha256="0" * 64,
            sello_tiempo=datetime.datetime.now(datetime.UTC),
            ruta_almacen="00/00/" + "0" * 64 + ".xml",
            estado_pipeline=EstadoPipeline.INGERIDO,
            tipo=TipoDocumento.SUMARIO,
        )
        session.add(sumario)
        session.flush()

    cuerpo = Documento(
        fuente_id=fuente.id,
        identificador_oficial=ident,
        fecha_publicacion=sumario.fecha_publicacion,
        url_original=f"https://www.boe.es/diario_boe/xml.php?id={ident}",
        sha256=f"{indice:064d}",
        sello_tiempo=datetime.datetime.now(datetime.UTC),
        ruta_almacen=f"{indice:02d}/00/{indice:064d}.xml",
        estado_pipeline=EstadoPipeline.INGERIDO,
        tipo=TipoDocumento.TEXTO_NORMA,
    )
    session.add(cuerpo)
    session.flush()

    norma = Norma(
        documento_id=sumario.id,
        identificador_oficial=ident,
        titulo="Ley por la que se modifica la Ley 2/2016",
        url_texto=f"https://www.boe.es/diario_boe/xml.php?id={ident}",
        documento_texto_id=cuerpo.id,
        prefiltro_estado=EstadoPrefiltro.RELEVANTE,
        prefiltro_terminos=["lgtbi"],
        prefiltro_ejes=["lexico", "referencial"],
        prefiltro_evaluado_en=datetime.datetime.now(datetime.UTC),
    )
    session.add(norma)
    session.flush()

    session.add(
        Deteccion(
            norma_id=norma.id,
            extraccion_json=None,
            clasificacion=Clasificacion.RETROCESO if con_regla else Clasificacion.INDETERMINADO,
            origen=(
                OrigenClasificacion.DERIVADO_DIFF if con_regla else OrigenClasificacion.HEURISTICA
            ),
            regla_aplicada="R-SUP-001" if con_regla else None,
            evidencia_json=EVIDENCIA if con_regla else None,
            severidad=4 if con_regla else 1,
            confianza=0.8 if con_regla else 0.0,
        )
    )
    session.commit()
    return norma


@pytest.fixture
def sesion_db(tmp_path: Path) -> Iterator[Session]:
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
    aplicacion.include_router(api_revision.router)
    aplicacion.dependency_overrides[api_revision.get_session] = lambda: sesion_db
    # https:// y no http:// porque la cookie de sesión es `Secure`. Ver la cabecera del módulo.
    with TestClient(aplicacion, base_url="https://testserver") as cliente:
        yield cliente


def _entrar(client: TestClient) -> None:
    respuesta = client.post("/api/revision/sesion", json={"password": PASSWORD})
    assert respuesta.status_code == 200


class TestSesion:
    def test_la_contrasena_correcta_abre_sesion_y_la_cookie_va_blindada(
        self, client: TestClient
    ) -> None:
        respuesta = client.post("/api/revision/sesion", json={"password": PASSWORD})

        assert respuesta.status_code == 200
        assert "caduca_en" in respuesta.json()
        cookie = respuesta.headers["set-cookie"]
        # Los tres atributos que evitan tres ataques distintos: XSS leyendo la sesión, la
        # sesión viajando en claro y un formulario de otro sitio mandándola.
        assert "HttpOnly" in cookie
        assert "Secure" in cookie
        assert "SameSite=strict" in cookie
        assert f"Path={api_revision.COOKIE_PATH}" in cookie

    def test_el_token_no_viaja_en_el_cuerpo(self, client: TestClient) -> None:
        """Si estuviera en el JSON, un script de la página podría leerlo y `HttpOnly` sobraría."""
        cuerpo = client.post("/api/revision/sesion", json={"password": PASSWORD}).json()
        token = client.cookies[api_revision.COOKIE_SESION]
        assert token not in str(cuerpo)

    def test_la_contrasena_incorrecta_no_abre_nada(self, client: TestClient) -> None:
        respuesta = client.post("/api/revision/sesion", json={"password": "otra cosa"})
        assert respuesta.status_code == 401
        assert api_revision.COOKIE_SESION not in respuesta.cookies

    def test_sin_hash_configurado_el_panel_no_abre(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Falla cerrado (500 de configuración), nunca abierto."""
        monkeypatch.setattr(get_settings(), "panel_password_hash", None)
        with pytest.raises(panel.PanelNoConfigurado):
            client.post("/api/revision/sesion", json={"password": PASSWORD})

    def test_la_cadencia_corta_la_fuerza_bruta(self, client: TestClient) -> None:
        api_revision._cadencia = panel.CadenciaIntentos(intentos=3, ventana_segundos=60)
        codigos = [
            client.post("/api/revision/sesion", json={"password": "mal"}).status_code
            for _ in range(4)
        ]
        assert codigos == [401, 401, 401, 429]

    def test_cerrar_sesion_invalida_el_token_en_el_servidor(self, client: TestClient) -> None:
        """Borrar la cookie del navegador sin invalidar el token sería teatro."""
        _entrar(client)
        token = client.cookies[api_revision.COOKIE_SESION]
        assert client.delete("/api/revision/sesion").status_code == 204
        assert not api_revision._sesiones.es_valida(token)

    def test_comprobar_sesion_responde_204_o_401(self, client: TestClient) -> None:
        assert client.get("/api/revision/sesion").status_code == 401
        _entrar(client)
        assert client.get("/api/revision/sesion").status_code == 204


class TestSinSesionNoSeToca:
    @pytest.mark.parametrize(
        ("metodo", "ruta"),
        [
            ("get", "/api/revision/cola"),
            ("get", "/api/revision/cola/1"),
            ("post", "/api/revision/cola/1/aprobar"),
            ("post", "/api/revision/cola/1/descartar"),
        ],
    )
    def test_todo_pide_sesion(self, client: TestClient, metodo: str, ruta: str) -> None:
        respuesta = getattr(client, metodo)(ruta, headers=CABECERA)
        assert respuesta.status_code == 401

    def test_sin_sesion_no_se_emite_ninguna_alerta(
        self, client: TestClient, sesion_db: Session
    ) -> None:
        """La comprobación que de verdad importa: el 401 no basta si además escribió algo."""
        _sembrar(sesion_db)
        servicio.encolar(sesion_db)
        sesion_db.commit()
        item = sesion_db.scalar(select(ColaRevision))
        assert item is not None

        client.post(f"/api/revision/cola/{item.id}/aprobar", headers=CABECERA)

        assert sesion_db.scalar(select(Alerta)) is None
        assert item.estado is EstadoRevision.PENDIENTE


class TestCola:
    def test_lista_lo_pendiente_con_su_evidencia(
        self, client: TestClient, sesion_db: Session
    ) -> None:
        _sembrar(sesion_db)
        servicio.encolar(sesion_db)
        sesion_db.commit()
        _entrar(client)

        items = client.get("/api/revision/cola").json()

        assert len(items) == 1
        item = items[0]
        assert item["clasificacion"] == "retroceso"
        assert item["regla_aplicada"] == "R-SUP-001"
        assert item["normas_vigiladas"] == ["BOE-A-2016-6728"]
        # Los spans llegan con offsets **y** fragmento: el fragmento es para leerlo y los
        # offsets para comprobarlo contra el texto archivado (7.5).
        assert [(s["inicio"], s["fin"]) for s in item["spans"]] == [(100, 140), (200, 245)]
        assert item["texto_archivado"]["sha256"]
        assert item["norma"]["identificador_oficial"].startswith("BOE-A-")

    def test_el_centinela_del_extractor_no_entra_en_la_cola(
        self, client: TestClient, sesion_db: Session
    ) -> None:
        """ADR 0009: una detección sin regla no es un veredicto, y encolarla vaciaría el gate."""
        _sembrar(sesion_db, con_regla=False)
        resumen = servicio.encolar(sesion_db)
        sesion_db.commit()

        assert (resumen.candidatas, resumen.encoladas) == (0, 0)
        _entrar(client)
        assert client.get("/api/revision/cola").json() == []

    def test_encolar_es_idempotente(self, sesion_db: Session) -> None:
        _sembrar(sesion_db)
        assert servicio.encolar(sesion_db).encoladas == 1
        sesion_db.commit()
        assert servicio.encolar(sesion_db).encoladas == 0
        sesion_db.commit()
        assert len(sesion_db.scalars(select(ColaRevision)).all()) == 1

    def test_no_se_publica_lo_que_dijo_el_modelo(
        self, client: TestClient, sesion_db: Session
    ) -> None:
        """El panel enseña el archivo y la evidencia, no la prosa del LLM (reglas de oro 3 y 10)."""
        _sembrar(sesion_db)
        servicio.encolar(sesion_db)
        sesion_db.commit()
        _entrar(client)

        item = client.get("/api/revision/cola").json()[0]

        assert "extraccion_json" not in item
        assert item["tiene_extraccion"] is False
        assert item["punteros_corroborados"] == 1


class TestResolver:
    @pytest.fixture
    def item_id(self, client: TestClient, sesion_db: Session) -> int:
        _sembrar(sesion_db)
        servicio.encolar(sesion_db)
        sesion_db.commit()
        _entrar(client)
        item = sesion_db.scalar(select(ColaRevision))
        assert item is not None
        return item.id

    def test_aprobar_emite_la_alerta(
        self, client: TestClient, sesion_db: Session, item_id: int
    ) -> None:
        respuesta = client.post(
            f"/api/revision/cola/{item_id}/aprobar",
            headers=CABECERA,
            json={"nota": "Verificado contra el BOE."},
        )

        assert respuesta.status_code == 200
        assert respuesta.json()["estado"] == "aprobada"
        alerta = sesion_db.scalar(select(Alerta))
        assert alerta is not None
        deteccion = sesion_db.scalar(select(Deteccion))
        assert deteccion is not None and deteccion.revisada is True
        assert alerta.deteccion_id == deteccion.id

    def test_descartar_no_emite_alerta_y_conserva_la_deteccion(
        self, client: TestClient, sesion_db: Session, item_id: int
    ) -> None:
        respuesta = client.post(f"/api/revision/cola/{item_id}/descartar", headers=CABECERA)

        assert respuesta.status_code == 200
        assert respuesta.json()["estado"] == "descartada"
        assert sesion_db.scalar(select(Alerta)) is None
        # El rastro no se borra: la detección sigue ahí con su regla y su evidencia.
        deteccion = sesion_db.scalar(select(Deteccion))
        assert deteccion is not None and deteccion.regla_aplicada == "R-SUP-001"

    def test_no_se_resuelve_dos_veces(
        self, client: TestClient, sesion_db: Session, item_id: int
    ) -> None:
        """Reabrir el gate sería poder emitir dos veces la misma alerta."""
        client.post(f"/api/revision/cola/{item_id}/aprobar", headers=CABECERA)
        segunda = client.post(f"/api/revision/cola/{item_id}/aprobar", headers=CABECERA)

        assert segunda.status_code == 409
        assert len(sesion_db.scalars(select(Alerta)).all()) == 1

    def test_sin_la_cabecera_del_panel_no_se_resuelve(
        self, client: TestClient, sesion_db: Session, item_id: int
    ) -> None:
        """Cinturón sobre los tirantes del `SameSite=Strict`: control anti-CSRF."""
        respuesta = client.post(f"/api/revision/cola/{item_id}/aprobar")

        assert respuesta.status_code == 403
        assert sesion_db.scalar(select(Alerta)) is None

    def test_un_get_no_resuelve_nada(self, client: TestClient, item_id: int) -> None:
        """Un precargador de enlaces o una etiqueta <img> no pueden aprobar una alerta."""
        assert client.get(f"/api/revision/cola/{item_id}/aprobar").status_code == 405

    def test_item_inexistente_da_404(self, client: TestClient, item_id: int) -> None:
        assert client.post("/api/revision/cola/9999/aprobar", headers=CABECERA).status_code == 404

    def test_la_nota_tiene_tope(self, client: TestClient, item_id: int) -> None:
        respuesta = client.post(
            f"/api/revision/cola/{item_id}/aprobar",
            headers=CABECERA,
            json={"nota": "x" * (servicio.MAX_NOTA + 1)},
        )
        assert respuesta.status_code == 422

    def test_lo_resuelto_sale_de_la_cola_pendiente(
        self, client: TestClient, sesion_db: Session, item_id: int
    ) -> None:
        client.post(f"/api/revision/cola/{item_id}/aprobar", headers=CABECERA)

        assert client.get("/api/revision/cola").json() == []
        aprobadas = client.get("/api/revision/cola", params={"estado": "aprobada"}).json()
        assert [item["id"] for item in aprobadas] == [item_id]


class TestCableado:
    """Se mira el contrato publicado (OpenAPI) y no `app.routes`.

    Es lo que ve quien consume la API, y además sobrevive a que FastAPI cambie cómo representa
    internamente un router incluido — cosa que ya ha pasado en esta versión.
    """

    def test_el_router_esta_montado_en_la_app_real(self) -> None:
        rutas = app_real.openapi()["paths"]
        assert set(rutas["/api/revision/cola/{cola_id}/aprobar"]) == {"post"}
        assert set(rutas["/api/revision/cola/{cola_id}/descartar"]) == {"post"}
        assert set(rutas["/api/revision/cola"]) == {"get"}

    def test_la_api_publica_sigue_sin_escrituras(self) -> None:
        """El panel escribe; el resto de la API, no. Es la frase de `api/documentos.py`."""
        for camino, metodos in app_real.openapi()["paths"].items():
            if camino.startswith("/api") and not camino.startswith("/api/revision"):
                assert set(metodos) == {"get"}, camino
