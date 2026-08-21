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
    InformeRevision,
    OrigenClasificacion,
    Semaforo,
)
from app.models.documento import Documento, EstadoPipeline, TipoDocumento
from app.models.fuente import AmbitoTerritorial, FormatoFuente, Fuente, TipoFuente
from app.models.norma import EstadoPrefiltro, Norma, VersionNorma
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

    def test_la_cadencia_agotada_no_deja_fuera_a_quien_sabe_la_contrasena(
        self, client: TestClient
    ) -> None:
        """El hallazgo del `revisor-seguridad` (2026-08-14), y por qué el orden es un control.

        Si el cubo se gastara **antes** de comprobar la contraseña, cualquiera podría cerrarle
        el panel al revisor sin credenciales y desde una sola dirección — o sea, anular el gate
        humano (regla de oro 4) desde fuera, usando el propio freno de fuerza bruta.
        """
        api_revision._cadencia = panel.CadenciaIntentos(intentos=1, ventana_segundos=600)
        assert client.post("/api/revision/sesion", json={"password": "mal"}).status_code == 401
        assert client.post("/api/revision/sesion", json={"password": "mal"}).status_code == 429

        # El cubo está a cero y la contraseña correcta entra igualmente.
        assert client.post("/api/revision/sesion", json={"password": PASSWORD}).status_code == 200

    def test_un_login_correcto_no_gasta_cadencia(self, client: TestClient) -> None:
        """Un día de revisión intensa no puede toparse con la defensa contra quien adivina."""
        api_revision._cadencia = panel.CadenciaIntentos(intentos=1, ventana_segundos=600)
        for _ in range(5):
            assert (
                client.post("/api/revision/sesion", json={"password": PASSWORD}).status_code == 200
            )
        assert api_revision._cadencia.fallos_en_la_ventana() == 0

    def test_las_respuestas_del_panel_no_se_almacenan_en_cache(self, client: TestClient) -> None:
        """Llevan evidencia y notas de revisión detrás de sesión; la API pública no."""
        respuesta = client.post("/api/revision/sesion", json={"password": PASSWORD})
        assert respuesta.headers["cache-control"] == "no-store"
        assert client.get("/api/revision/cola").headers["cache-control"] == "no-store"

    def test_al_cerrar_sesion_la_cookie_de_borrado_conserva_los_atributos(
        self, client: TestClient
    ) -> None:
        _entrar(client)
        cookie = client.delete("/api/revision/sesion").headers["set-cookie"]
        assert "Secure" in cookie and "HttpOnly" in cookie
        assert f"Path={api_revision.COOKIE_PATH}" in cookie

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

    def test_una_supresion_de_organo_del_ambito_si_entra(self, sesion_db: Session) -> None:
        """La segunda puerta del gate (ADR 0024).

        «Se suprime el Consejo LGTBI» no nombra ninguna norma de la watchlist —ese consejo lo
        creó un decreto que no está en ella— así que hasta hoy la detección se creaba y **moría
        sin que nadie la mirase**: desaparecía quien vigila la ley y era invisible.

        Sigue sin ser la puerta ancha que el ADR 0017 cerró: R-SUP-003 exige término directo y
        nombre de órgano **en la misma cláusula**, y medido antes de abrirla, cero de las 10
        detecciones de R-SUP-002 del corpus la cruzan.
        """
        norma = _sembrar(sesion_db)
        deteccion = sesion_db.scalar(select(Deteccion).where(Deteccion.norma_id == norma.id))
        assert deteccion is not None
        deteccion.regla_aplicada = "R-SUP-003"
        deteccion.evidencia_json = {
            "regla": "R-SUP-003",
            "normas_vigiladas": [],
            "organos_afectados": ["consejo"],
            "spans": [
                {"inicio": 0, "fin": 44, "fragmento": "Se suprime el Consejo Nacional LGTBI."}
            ],
        }
        sesion_db.commit()

        resumen = servicio.encolar(sesion_db)
        sesion_db.commit()

        assert (resumen.candidatas, resumen.encoladas) == (1, 1)

    def test_sin_norma_vigilada_ni_organo_sigue_fuera(self, sesion_db: Session) -> None:
        """Lo que el ADR 0017 cerró sigue cerrado: R-SUP-002 a secas no llena la cola de ruido."""
        norma = _sembrar(sesion_db)
        deteccion = sesion_db.scalar(select(Deteccion).where(Deteccion.norma_id == norma.id))
        assert deteccion is not None
        deteccion.regla_aplicada = "R-SUP-002"
        deteccion.evidencia_json = {
            "regla": "R-SUP-002",
            "normas_vigiladas": [],
            "organos_afectados": [],
            "spans": [{"inicio": 0, "fin": 26, "fragmento": "Se suprime el artículo 7."}],
        }
        sesion_db.commit()

        resumen = servicio.encolar(sesion_db)
        sesion_db.commit()

        assert (resumen.candidatas, resumen.encoladas) == (0, 0)

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


class TestDiffEnElPanel:
    """Quien aprueba tiene que ver lo que se va a publicar. ADR 0018 + auditoría del 16/08."""

    def _versionar(self, session: Session, norma: Norma) -> None:
        consolidado = Documento(
            fuente_id=norma.documento.fuente_id,
            identificador_oficial="BOE-A-2016-6728-consolidado-abc123abc123",
            fecha_publicacion=datetime.date(2026, 8, 16),
            url_original=(
                "https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/BOE-A-2016-6728"
            ),
            sha256="c" * 64,
            sello_tiempo=datetime.datetime.now(datetime.UTC),
            ruta_almacen="cc/dd/consolidado.xml",
            estado_pipeline=EstadoPipeline.INGERIDO,
            tipo=TipoDocumento.CONSOLIDADO,
        )
        session.add(consolidado)
        session.flush()
        session.add(
            VersionNorma(
                norma_id=norma.id,
                norma_afectada="BOE-A-2016-6728",
                bloque="a4",
                articulo="Artículo 4",
                documento_consolidado_id=consolidado.id,
                texto_anterior="Reconocimiento del derecho a la identidad de género.",
                texto_nuevo="Reconocimiento del respeto a la libertad de las personas.",
                ordinal=1,
                version_derivacion="2026.08.15.1",
            )
        )
        session.commit()

    def test_la_cola_trae_las_dos_redacciones(self, client: TestClient, sesion_db: Session) -> None:
        norma = _sembrar(sesion_db)
        self._versionar(sesion_db, norma)
        servicio.encolar(sesion_db)
        sesion_db.commit()
        _entrar(client)

        item = client.get("/api/revision/cola").json()[0]

        assert len(item["cambios"]) == 1
        assert "identidad de género" in item["cambios"][0]["texto_anterior"]
        assert item["cambios"][0]["consolidado_sha256"] == "c" * 64

    def test_el_panel_ve_tambien_lo_archivado_despues_de_clasificar(
        self, client: TestClient, sesion_db: Session
    ) -> None:
        """Aquí NO se filtra por fecha, y es lo contrario que en el canal público.

        La persona que mira esta pantalla es el gate: si solo viera lo anterior a la
        clasificación, aprobaría a ciegas justo el material que llegó tarde — que es el caso
        normal, porque el BOE consolida con semanas de retraso.
        """
        norma = _sembrar(sesion_db)
        servicio.encolar(sesion_db)
        sesion_db.commit()
        # El versionado llega DESPUÉS de encolar, como en la vida real.
        self._versionar(sesion_db, norma)
        _entrar(client)

        item = client.get("/api/revision/cola").json()[0]

        assert len(item["cambios"]) == 1


class TestSoloEntraLoQueSenalaUnaNormaVigilada:
    """El gate humano se vacía por dentro si se le llena de ruido (7.7, medido el 2026-08-17).

    R-SUP-002 —supresión sin norma vigilada identificada— produjo 10 ítems reales y una persona
    descartó los 10, mientras las reglas que sí señalan una norma de la watchlist iban 3 de 3
    aprobadas. Quien revisaba abría la norma, la leía entera buscando el recorte y no lo
    encontraba, porque no lo había.
    """

    def _deteccion(self, session: Session, *, vigiladas: list[str]) -> Deteccion:
        norma = _sembrar(session)
        deteccion = session.scalar(select(Deteccion).where(Deteccion.norma_id == norma.id))
        assert deteccion is not None
        deteccion.evidencia_json = {**EVIDENCIA, "normas_vigiladas": vigiladas}
        session.commit()
        return deteccion

    def test_un_veredicto_sin_norma_vigilada_no_llega_a_la_cola(self, sesion_db: Session) -> None:
        self._deteccion(sesion_db, vigiladas=[])

        resumen = servicio.encolar(sesion_db)
        sesion_db.commit()

        assert (resumen.candidatas, resumen.encoladas) == (0, 0)
        assert sesion_db.scalar(select(ColaRevision)) is None

    def test_pero_la_deteccion_sigue_existiendo_con_su_regla(self, sesion_db: Session) -> None:
        """No se pierde recall: lo que no se encola sigue archivado, contable y consultable."""
        deteccion = self._deteccion(sesion_db, vigiladas=[])

        servicio.encolar(sesion_db)
        sesion_db.commit()

        vivo = sesion_db.scalar(select(Deteccion).where(Deteccion.id == deteccion.id))
        assert vivo is not None and vivo.regla_aplicada == "R-SUP-001"

    def test_el_que_senala_una_norma_vigilada_si_entra(self, sesion_db: Session) -> None:
        self._deteccion(sesion_db, vigiladas=["BOE-A-2016-6728"])

        resumen = servicio.encolar(sesion_db)
        sesion_db.commit()

        assert (resumen.candidatas, resumen.encoladas) == (1, 1)


class TestInformeDeApoyo:
    """El dosier del ADR 0025 en la cola, y lo que la API garantiza sobre él."""

    def _con_informe(self, sesion_db: Session, **campos: object) -> None:
        norma = _sembrar(sesion_db)
        deteccion = sesion_db.scalar(select(Deteccion).where(Deteccion.norma_id == norma.id))
        assert deteccion is not None
        servicio.encolar(sesion_db)
        item = sesion_db.scalar(
            select(ColaRevision).where(ColaRevision.deteccion_id == deteccion.id)
        )
        assert item is not None
        base: dict[str, object] = {
            "semaforo": Semaforo.ALERTA,
            "resumen": "Ata el acceso a un diagnóstico que solo cumple una pareja heterosexual.",
            "recomendacion": "A alerta, con signo retroceso.",
            "refutacion": "Que la redacción anterior ya exigiera lo mismo.",
            "citas": [{"texto": "Se aplicarán a las personas…", "apartado": "5.3.8.1.a)"}],
            "corroboraciones": [],
            "generado_por": "agente jurista-lgtbi",
        }
        base.update(campos)
        sesion_db.add(InformeRevision(cola_revision_id=item.id, **base))
        sesion_db.commit()

    def test_la_cola_trae_el_informe_con_su_refutacion(
        self, client: TestClient, sesion_db: Session
    ) -> None:
        """`refutacion` viaja siempre: es lo que permite llevarle la contraria al informe.

        Si algún día se cayera del contrato, la interfaz enseñaría una recomendación sin con qué
        rebatirla, que es exactamente el sello de goma que el ADR 0025 evita.
        """
        self._con_informe(sesion_db)
        _entrar(client)

        (item,) = client.get("/api/revision/cola").json()

        assert item["informe"]["semaforo"] == "alerta"
        assert item["informe"]["refutacion"]
        assert item["informe"]["generado_por"] == "agente jurista-lgtbi"

    def test_el_informe_no_toca_la_clasificacion_de_la_regla(
        self, client: TestClient, sesion_db: Session
    ) -> None:
        """La prueba de que la separación del ADR 0025 es real y no nominal.

        El informe recomienda alerta con signo retroceso; la detección sembrada es lo que las
        reglas dijeron. Que convivan sin pisarse es el ADR 0004 intacto: si un día el informe
        escribiera `clasificacion`, este test se pondría rojo.
        """
        self._con_informe(sesion_db)
        _entrar(client)

        (item,) = client.get("/api/revision/cola").json()

        assert item["informe"]["semaforo"] == "alerta"
        assert item["clasificacion"] == "retroceso"
        assert item["origen"] == "derivado_diff"

    def test_un_item_sin_informe_lo_dice_con_null(
        self, client: TestClient, sesion_db: Session
    ) -> None:
        """Es el estado normal: los informes se importan a mano y no existen para todo."""
        _sembrar(sesion_db)
        servicio.encolar(sesion_db)
        sesion_db.commit()
        _entrar(client)

        (item,) = client.get("/api/revision/cola").json()

        assert item["informe"] is None
