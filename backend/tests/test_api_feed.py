"""Tests del canal pull: el feed Atom (CLAUDE.md 6.4, ADR 0010).

Lo que se comprueba no es que `ElementTree` sepa serializar, sino las decisiones propias: que
solo salga lo aprobado, que el identificador de cada entrada sea estable, que la huella del
archivo viaje dentro (para poder comprobar sin volver a la web) y que **el feed no necesite ni
acepte nada que identifique a quien lo lee** — sin token, sin sesión, sin personalización.

El feed se parsea con `defusedxml` aunque lo hayamos generado nosotros: es lo que exige la 6.1
para cualquier XML, y usar el parser endurecido en los tests deja el ejemplo correcto escrito.
"""

from __future__ import annotations

import datetime
from collections.abc import Iterator

import pytest
from defusedxml.ElementTree import fromstring
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import feed as api_feed
from app.database import Base
from app.models.deteccion import ColaRevision, Deteccion, EstadoRevision
from app.models.norma import Norma
from app.pipeline import watchlist
from app.services import revision as servicio
from tests.test_api_alertas import LISTA, _norma_con_deteccion

ATOM = "{http://www.w3.org/2005/Atom}"


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
    aplicacion.include_router(api_feed.router)
    aplicacion.dependency_overrides[api_feed.get_session] = lambda: sesion_db
    with TestClient(aplicacion) as cliente:
        yield cliente


def _aprobar(sesion_db: Session, ident: str) -> None:
    deteccion = _norma_con_deteccion(sesion_db, ident=ident)
    sesion_db.add(ColaRevision(deteccion_id=deteccion.id, estado=EstadoRevision.PENDIENTE))
    sesion_db.commit()
    cola = sesion_db.scalar(select(ColaRevision).where(ColaRevision.deteccion_id == deteccion.id))
    assert cola is not None
    servicio.aprobar(sesion_db, cola.id)


def test_el_feed_es_atom_valido_y_se_declara_como_tal(
    client: TestClient, sesion_db: Session
) -> None:
    _aprobar(sesion_db, "BOE-A-2024-10767")

    respuesta = client.get("/api/alertas.xml")

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("application/atom+xml")
    raiz = fromstring(respuesta.content)
    assert raiz.tag == f"{ATOM}feed"
    assert raiz.findtext(f"{ATOM}title")
    assert raiz.findtext(f"{ATOM}updated")
    assert len(raiz.findall(f"{ATOM}entry")) == 1


def test_solo_sale_lo_aprobado(client: TestClient, sesion_db: Session) -> None:
    """El mismo control que la API web, y por el mismo motivo: se lee de `alerta`."""
    _norma_con_deteccion(sesion_db, ident="BOE-A-2024-0001", con_regla=False)
    pendiente = _norma_con_deteccion(sesion_db, ident="BOE-A-2024-0002")
    sesion_db.add(ColaRevision(deteccion_id=pendiente.id, estado=EstadoRevision.PENDIENTE))
    sesion_db.commit()
    _aprobar(sesion_db, "BOE-A-2024-10767")

    raiz = fromstring(client.get("/api/alertas.xml").content)

    titulos = [e.findtext(f"{ATOM}title") or "" for e in raiz.findall(f"{ATOM}entry")]
    assert len(titulos) == 1
    assert "BOE-A-2024-0002" not in " ".join(titulos)


def test_el_identificador_de_entrada_es_estable_y_no_es_una_url(
    client: TestClient, sesion_db: Session
) -> None:
    """Si el id cambiara —por ejemplo al cambiar de dominio— los lectores marcarían todo como
    nuevo otra vez. Por eso es una `tag:` URI y no la URL de nuestra web, que aún no existe."""
    _aprobar(sesion_db, "BOE-A-2024-10767")

    primero = fromstring(client.get("/api/alertas.xml").content)
    segundo = fromstring(client.get("/api/alertas.xml").content)

    ids = [
        raiz.find(f"{ATOM}entry").findtext(f"{ATOM}id")  # type: ignore[union-attr]
        for raiz in (primero, segundo)
    ]
    assert ids[0] == ids[1]
    assert ids[0] is not None and ids[0].startswith("tag:")


def test_la_entrada_lleva_la_evidencia_y_la_huella(client: TestClient, sesion_db: Session) -> None:
    """Quien lo recibe por un lector tiene que poder comprobarlo sin volver a nuestra web."""
    _aprobar(sesion_db, "BOE-A-2024-10767")

    raiz = fromstring(client.get("/api/alertas.xml").content)
    entrada = raiz.find(f"{ATOM}entry")
    assert entrada is not None
    contenido = entrada.findtext(f"{ATOM}content") or ""

    assert "Se suprime el artículo 7." in contenido
    assert "sha256" in contenido
    assert "R-SUP-001" in contenido
    # Y dice que hubo una persona: es la diferencia entre este proyecto y un raspador.
    assert "aprobado una persona" in contenido


def test_el_contenido_va_como_texto_y_no_como_marcado(
    client: TestClient, sesion_db: Session
) -> None:
    """Nada de lo que sale de un boletín se declara HTML: no hay nada que maquetar y sí que
    perder si el cliente de alguien lo interpreta."""
    _aprobar(sesion_db, "BOE-A-2024-10767")

    raiz = fromstring(client.get("/api/alertas.xml").content)
    entrada = raiz.find(f"{ATOM}entry")
    assert entrada is not None
    assert entrada.find(f"{ATOM}content").get("type") == "text"  # type: ignore[union-attr]


def test_un_feed_vacio_sigue_siendo_un_feed(client: TestClient) -> None:
    """Sin alertas aprobadas, el canal responde 200 con cero entradas.

    No es un caso raro: es el estado normal de un día en el que nada pasó el gate, y un lector
    que reciba un 404 o un error lo trataría como una avería del sitio.
    """
    respuesta = client.get("/api/alertas.xml")

    assert respuesta.status_code == 200
    raiz = fromstring(respuesta.content)
    assert raiz.findall(f"{ATOM}entry") == []
    assert raiz.findtext(f"{ATOM}updated")


def test_no_publica_ni_la_extraccion_del_modelo_ni_la_nota_de_revision(
    client: TestClient, sesion_db: Session
) -> None:
    deteccion = _norma_con_deteccion(sesion_db, ident="BOE-A-2024-10767")
    sesion_db.add(ColaRevision(deteccion_id=deteccion.id, estado=EstadoRevision.PENDIENTE))
    sesion_db.commit()
    cola = sesion_db.scalar(select(ColaRevision))
    assert cola is not None
    servicio.aprobar(sesion_db, cola.id, nota="Nota interna del revisor.")

    cuerpo = client.get("/api/alertas.xml").text

    assert "qwen" not in cuerpo
    assert "Nota interna" not in cuerpo


def test_el_titulo_de_la_norma_se_escapa(client: TestClient, sesion_db: Session) -> None:
    """El BOE publica títulos con `&` y comillas a diario. Componer el XML a mano rompería."""
    deteccion = _norma_con_deteccion(sesion_db, ident="BOE-A-2024-10767")
    norma = sesion_db.get(Norma, deteccion.norma_id)
    assert norma is not None
    norma.titulo = 'Ley de <educación> & "convivencia"'
    sesion_db.add(ColaRevision(deteccion_id=deteccion.id, estado=EstadoRevision.PENDIENTE))
    sesion_db.commit()
    cola = sesion_db.scalar(select(ColaRevision))
    assert cola is not None
    servicio.aprobar(sesion_db, cola.id)

    respuesta = client.get("/api/alertas.xml")

    # Se parsea sin error (lo importante) y el título vuelve intacto tras desescapar.
    raiz = fromstring(respuesta.content)
    entrada = raiz.find(f"{ATOM}entry")
    assert entrada is not None
    assert 'Ley de <educación> & "convivencia"' in (entrada.findtext(f"{ATOM}title") or "")
    assert b"<educaci" not in respuesta.content.split(b"<title>")[2]


def test_el_feed_tiene_tope_de_entradas(client: TestClient, sesion_db: Session) -> None:
    """Un feed que crece sin tope acaba siendo una descarga grande pedida cada quince minutos."""
    for indice in range(api_feed.MAXIMO_ENTRADAS + 3):
        _aprobar(sesion_db, f"BOE-A-2024-{indice:05d}")

    raiz = fromstring(client.get("/api/alertas.xml").content)

    assert len(raiz.findall(f"{ATOM}entry")) == api_feed.MAXIMO_ENTRADAS


def test_no_acepta_nada_que_identifique_a_quien_lee(client: TestClient, sesion_db: Session) -> None:
    """El canal pull existe para no saber quién está al otro lado (6.4).

    Un feed por suscriptor —con token en la URL— sería una lista de suscriptores con otro
    nombre. Aquí un parámetro extra no cambia nada y no hay ruta con token.
    """
    _aprobar(sesion_db, "BOE-A-2024-10767")

    normal = client.get("/api/alertas.xml").content
    con_token = client.get("/api/alertas.xml?token=alguien").content

    assert normal.replace(b"?token=alguien", b"") == con_token.replace(b"?token=alguien", b"")
    assert client.get("/api/alertas.xml/alguien").status_code == 404


def test_ordena_por_fecha_del_boletin(client: TestClient, sesion_db: Session) -> None:
    for ident, fecha in (
        ("BOE-A-2023-0001", datetime.date(2023, 3, 1)),
        ("BOE-A-2024-0001", datetime.date(2024, 5, 29)),
    ):
        deteccion = _norma_con_deteccion(sesion_db, ident=ident, fecha=fecha)
        sesion_db.add(ColaRevision(deteccion_id=deteccion.id, estado=EstadoRevision.PENDIENTE))
        sesion_db.commit()
    for ident in ("BOE-A-2023-0001", "BOE-A-2024-0001"):
        norma = sesion_db.scalar(select(Norma).where(Norma.identificador_oficial == ident))
        assert norma is not None
        deteccion_fila = sesion_db.scalar(select(Deteccion).where(Deteccion.norma_id == norma.id))
        assert deteccion_fila is not None
        cola = sesion_db.scalar(
            select(ColaRevision).where(ColaRevision.deteccion_id == deteccion_fila.id)
        )
        assert cola is not None
        servicio.aprobar(sesion_db, cola.id)

    raiz = fromstring(client.get("/api/alertas.xml").content)
    contenidos = [e.findtext(f"{ATOM}content") or "" for e in raiz.findall(f"{ATOM}entry")]

    assert "2024-05-29" in contenidos[0]
    assert "2023-03-01" in contenidos[1]


def test_el_feed_de_hallazgos_avisa_en_el_titulo_de_cada_entrada(
    client: TestClient, sesion_db: Session
) -> None:
    """El aviso va en el título, no en una categoría, y ese es todo el diseño de este feed.

    Un hallazgo no lo ha revisado nadie. En la web eso se dice con una banda de color arriba de la
    tarjeta, pero **un feed se lee en un agregador**: colores, categorías y etiquetas se pierden
    por el camino, y lo único que sobrevive a cualquier lector es el título. Si el aviso viviera
    solo en `<category>`, un hallazgo llegaría al lector indistinguible de una alerta revisada.

    Por eso este test comprueba el título y no la categoría: la categoría es un extra, el título
    es el control.
    """
    respuesta = client.get("/api/hallazgos.xml")

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("application/atom+xml")
    cuerpo = respuesta.text
    # El subtítulo del feed lo dice también, para quien mire la cabecera del canal.
    assert "SIN revisar" in cuerpo
    assert "NO los ha revisado ninguna persona" in cuerpo
    # Y cada entrada que haya lo lleva delante del título de la norma.
    for titulo in _titulos(cuerpo):
        assert titulo.startswith("SIN REVISAR · "), (
            f"Una entrada del feed de hallazgos no avisa en su título: {titulo!r}. En un "
            "agregador, el título es lo único que no se pierde."
        )


def _titulos(cuerpo: str) -> list[str]:
    """Los títulos de las `<entry>`, sin el del propio feed."""
    from xml.etree.ElementTree import fromstring

    ATOM_NS = "{http://www.w3.org/2005/Atom}"
    raiz = fromstring(cuerpo)
    return [
        (entrada.findtext(f"{ATOM_NS}title") or "") for entrada in raiz.findall(f"{ATOM_NS}entry")
    ]
