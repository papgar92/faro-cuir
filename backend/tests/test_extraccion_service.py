"""Tests del servicio que descarga, extrae y persiste la etapa 2 del pipeline.

SQLite en memoria, mismo criterio que `test_prefiltro_service.py` y `test_ingesta_service.py`:
se prueba la lógica del servicio (¿a quién descarga?, ¿qué guarda?, ¿es idempotente?, ¿qué
pasa si algo falla?), no el dialecto de la base de datos. El transporte HTTP se simula con
`httpx.MockTransport`, igual que en `test_ingesta_service.py` — el objetivo no es probar
`url_guard` ni `xml_safe` (ya tienen su propia suite), sino que este servicio los usa de
verdad y no se los salta.
"""

from __future__ import annotations

import datetime
import json
from collections.abc import Iterator
from xml.etree.ElementTree import fromstring

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.llm.provider import ProveedorGuionizado
from app.models.deteccion import Clasificacion, Deteccion, OrigenClasificacion
from app.models.documento import Documento, EstadoPipeline
from app.models.fuente import FormatoFuente, Fuente, TipoFuente
from app.models.norma import EstadoPrefiltro, Norma
from app.services import extraccion as servicio

EXTRACCION_VALIDA = {
    "norma_afectada": "Ley 4/2023",
    "organo_emisor": "Jefatura del Estado",
    "ambito": "sanitario",
    "articulos": [
        {
            "identificador": "art. 19",
            "texto_anterior": "texto anterior",
            "texto_nuevo": "texto nuevo",
        }
    ],
}

# Forma real del BOE (verificada contra BOE-A-2023-5366): metadatos + análisis + cuerpo.
XML_NORMA = (
    b"<documento><metadatos><identificador>BOE-A-2023-5366</identificador></metadatos>"
    b"<analisis><anterior><texto>ruido de metadatos</texto></anterior></analisis>"
    b"<texto><p>Contenido real de la disposicion.</p></texto></documento>"
)


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


def _norma_relevante(documento: Documento, ident: str, *, url_texto: str | None) -> Norma:
    return Norma(
        documento_id=documento.id,
        identificador_oficial=ident,
        titulo=f"Ley de {ident}",
        url_texto=url_texto,
        prefiltro_estado=EstadoPrefiltro.RELEVANTE,
        prefiltro_terminos=["lgtbi"],
        prefiltro_version="2026.08.06",
        prefiltro_evaluado_en=datetime.datetime.now(datetime.UTC),
    )


def _cliente_que_sirve(contenido: bytes) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=contenido)

    return httpx.Client(transport=httpx.MockTransport(handler))


def _proveedor(respuestas: list[str]) -> ProveedorGuionizado:
    return ProveedorGuionizado(respuestas, modelo="modelo-test")


class TestExtraccionFeliz:
    def test_extrae_y_persiste_una_norma_relevante(
        self, session: Session, documento: Documento
    ) -> None:
        session.add(
            _norma_relevante(documento, "BOE-A-2023-5366", url_texto="https://www.boe.es/x.xml")
        )
        session.commit()

        resumen = servicio.aplicar(
            session,
            _proveedor([json.dumps(EXTRACCION_VALIDA)]),
            documento_id=documento.id,
            client=_cliente_que_sirve(XML_NORMA),
        )

        assert (resumen.evaluadas, resumen.extraidas, resumen.fallidas) == (1, 1, 0)

        deteccion = session.scalar(select(Deteccion))
        assert deteccion is not None
        assert deteccion.clasificacion is Clasificacion.INDETERMINADO
        assert deteccion.origen is OrigenClasificacion.HEURISTICA
        assert deteccion.regla_aplicada is None
        assert deteccion.extraccion_json is not None
        assert deteccion.extraccion_json["extraccion"]["norma_afectada"] == "Ley 4/2023"
        assert deteccion.extraccion_json["modelo"] == "modelo-test"
        assert deteccion.extraccion_json["version_prompt"]

    def test_es_idempotente(self, session: Session, documento: Documento) -> None:
        session.add(_norma_relevante(documento, "BOE-A-1", url_texto="https://www.boe.es/x.xml"))
        session.commit()

        primera = servicio.aplicar(
            session,
            _proveedor([json.dumps(EXTRACCION_VALIDA)]),
            documento_id=documento.id,
            client=_cliente_que_sirve(XML_NORMA),
        )
        segunda = servicio.aplicar(
            session,
            _proveedor([json.dumps(EXTRACCION_VALIDA)]),
            documento_id=documento.id,
            client=_cliente_que_sirve(XML_NORMA),
        )

        assert primera.extraidas == 1
        assert segunda.evaluadas == 0
        assert session.scalar(select(Deteccion.id).limit(2).offset(1)) is None


class TestNoSeTocaLoQueNoToca:
    def test_ignora_normas_no_relevantes(self, session: Session, documento: Documento) -> None:
        pendiente = Norma(
            documento_id=documento.id,
            identificador_oficial="BOE-A-1",
            titulo="Orden del modelo 190",
            url_texto="https://www.boe.es/x.xml",
        )
        descartada = _norma_relevante(documento, "BOE-A-2", url_texto="https://www.boe.es/y.xml")
        descartada.prefiltro_estado = EstadoPrefiltro.DESCARTADA
        session.add_all([pendiente, descartada])
        session.commit()

        resumen = servicio.aplicar(session, _proveedor([]), documento_id=documento.id)

        assert resumen == servicio.ResumenExtraccion(evaluadas=0, extraidas=0, fallidas=0)
        assert session.scalar(select(Deteccion)) is None

    def test_solo_toca_el_documento_indicado(self, session: Session, documento: Documento) -> None:
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
                _norma_relevante(documento, "BOE-A-1", url_texto="https://www.boe.es/x.xml"),
                _norma_relevante(otro, "BOE-A-2", url_texto="https://www.boe.es/y.xml"),
            ]
        )
        session.commit()

        resumen = servicio.aplicar(
            session,
            _proveedor([json.dumps(EXTRACCION_VALIDA)]),
            documento_id=documento.id,
            client=_cliente_que_sirve(XML_NORMA),
        )

        assert resumen.evaluadas == 1
        sin_tocar = session.scalar(select(Norma).where(Norma.identificador_oficial == "BOE-A-2"))
        assert sin_tocar is not None
        assert session.scalar(select(Deteccion).where(Deteccion.norma_id == sin_tocar.id)) is None


class TestFallosNoCreanFila:
    """Descartar, nunca interpretar (CLAUDE.md 6.7) — y aquí, nunca dejar una fila a medias."""

    def test_sin_url_texto_no_crea_fila(self, session: Session, documento: Documento) -> None:
        session.add(_norma_relevante(documento, "BOE-A-1", url_texto=None))
        session.commit()

        resumen = servicio.aplicar(session, _proveedor([]), documento_id=documento.id)

        assert (resumen.evaluadas, resumen.extraidas, resumen.fallidas) == (1, 0, 1)
        assert session.scalar(select(Deteccion)) is None

    def test_url_fuera_de_la_allowlist_no_crea_fila(
        self, session: Session, documento: Documento
    ) -> None:
        """El sumario no elige a qué host nos conectamos (ADR 0006): esto es SSRF, no un 404."""
        session.add(
            _norma_relevante(documento, "BOE-A-1", url_texto="https://evil.example.com/x.xml")
        )
        session.commit()

        resumen = servicio.aplicar(session, _proveedor([]), documento_id=documento.id)

        assert (resumen.evaluadas, resumen.extraidas, resumen.fallidas) == (1, 0, 1)
        assert session.scalar(select(Deteccion)) is None

    def test_extraccion_invalida_no_crea_fila(self, session: Session, documento: Documento) -> None:
        """Un veredicto colado (inyección o alucinación) se descarta; no aterriza en ningún lado."""
        session.add(_norma_relevante(documento, "BOE-A-1", url_texto="https://www.boe.es/x.xml"))
        session.commit()

        manipulada = json.dumps({**EXTRACCION_VALIDA, "clasificacion": "retroceso"})
        resumen = servicio.aplicar(
            session,
            _proveedor([manipulada]),
            documento_id=documento.id,
            client=_cliente_que_sirve(XML_NORMA),
        )

        assert (resumen.evaluadas, resumen.extraidas, resumen.fallidas) == (1, 0, 1)
        assert session.scalar(select(Deteccion)) is None

    def test_xml_malformado_no_crea_fila(self, session: Session, documento: Documento) -> None:
        session.add(_norma_relevante(documento, "BOE-A-1", url_texto="https://www.boe.es/x.xml"))
        session.commit()

        resumen = servicio.aplicar(
            session,
            _proveedor([]),
            documento_id=documento.id,
            client=_cliente_que_sirve(b"<no-cierra>"),
        )

        assert (resumen.evaluadas, resumen.extraidas, resumen.fallidas) == (1, 0, 1)
        assert session.scalar(select(Deteccion)) is None


class TestTextoPlano:
    def test_prefiere_el_elemento_texto_sobre_el_resto_del_arbol(self) -> None:
        """Estructura real del BOE: <analisis> es ruido de metadatos, <texto> es el cuerpo."""
        raiz = fromstring(
            "<documento>"
            "<analisis><anterior><texto>ruido de metadatos</texto></anterior></analisis>"
            "<texto><p>cuerpo real de la norma</p></texto>"
            "</documento>"
        )
        assert servicio._texto_plano(raiz) == "cuerpo real de la norma"

    def test_sin_elemento_texto_cae_al_arbol_completo(self) -> None:
        raiz = fromstring("<a>uno <b>dos</b> <c>tres</c></a>")
        assert servicio._texto_plano(raiz) == "uno dos tres"


class TestRecortar:
    def test_no_toca_lo_que_ya_cabe(self) -> None:
        assert servicio._recortar("corto", identificador="BOE-A-1") == "corto"

    def test_recorta_al_tope_de_caracteres_y_lo_avisa(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        largo = "x" * (servicio.MAX_CARACTERES_DOCUMENTO + 500)
        with caplog.at_level("WARNING"):
            recortado = servicio._recortar(largo, identificador="BOE-A-2023-5366")

        assert len(recortado) == servicio.MAX_CARACTERES_DOCUMENTO
        assert "BOE-A-2023-5366" in caplog.text
