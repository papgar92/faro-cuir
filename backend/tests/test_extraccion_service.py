"""Tests del servicio que extrae hechos del texto ya archivado (etapa 3 del pipeline).

SQLite en memoria más un almacén real en `tmp_path`, mismo criterio que
`test_prefiltro_service.py`: se prueba la lógica del servicio (¿a quién mira?, ¿qué guarda?,
¿es idempotente?, ¿qué pasa si algo falla?), no el dialecto de la base de datos.

**Estos tests cambiaron de naturaleza con el ADR 0015.** Antes simulaban HTTP con
`httpx.MockTransport` porque este servicio descargaba el cuerpo de cada norma; ahora lo lee del
almacén, donde lo dejó la fase 2. Los dos tests que comprobaban la puerta HTTP —URL fuera de la
allowlist, norma sin `url_texto`— ya no aplican aquí y **no se han borrado sin más**: viven
ahora en `test_texto_integro.py`, que es donde vive la descarga. Borrar un test de seguridad
porque el código se movió es cómo se pierde la cobertura de un control sin que nadie lo note.
"""

from __future__ import annotations

import datetime
import json
from collections.abc import Iterator
from pathlib import Path
from xml.etree.ElementTree import fromstring

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.llm.provider import ProveedorGuionizado
from app.models.deteccion import Clasificacion, Deteccion, OrigenClasificacion
from app.models.documento import Documento, EstadoPipeline, TipoDocumento
from app.models.fuente import AmbitoTerritorial, FormatoFuente, Fuente, TipoFuente
from app.models.norma import EstadoPrefiltro, Norma
from app.pipeline.texto import texto_plano
from app.security import hashing
from app.services import extraccion as servicio
from app.services.archivo import archivar

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
def almacen(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def documento(session: Session) -> Documento:
    fuente = Fuente(
        nombre="BOE",
        tipo=TipoFuente.BOE,
        # El BOE es la fuente estatal. NOT NULL sin valor por defecto a propósito
        # (ADR 0014): un ámbito por defecto colaría un territorio inventado en silencio.
        ambito_territorial=AmbitoTerritorial.ESTATAL,
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
        tipo=TipoDocumento.SUMARIO,
    )
    session.add(doc)
    session.flush()
    return doc


def _cuerpo_archivado(
    session: Session, sumario: Documento, ident: str, contenido: bytes, almacen: Path
) -> Documento:
    """Deja un cuerpo en el almacén y su fila en `documento`, como haría la fase 2."""
    digest = hashing.sha256_hex(contenido)
    ruta = archivar(contenido, digest, almacen_root=almacen)
    cuerpo = Documento(
        fuente_id=sumario.fuente_id,
        identificador_oficial=ident,
        fecha_publicacion=sumario.fecha_publicacion,
        url_original=f"https://www.boe.es/diario_boe/xml.php?id={ident}",
        sha256=digest,
        sello_tiempo=datetime.datetime.now(datetime.UTC),
        ruta_almacen=ruta,
        estado_pipeline=EstadoPipeline.INGERIDO,
        tipo=TipoDocumento.TEXTO_NORMA,
    )
    session.add(cuerpo)
    session.flush()
    return cuerpo


def _norma_relevante(documento: Documento, ident: str, *, cuerpo: Documento | None) -> Norma:
    return Norma(
        documento_id=documento.id,
        identificador_oficial=ident,
        titulo=f"Ley de {ident}",
        url_texto=f"https://www.boe.es/diario_boe/xml.php?id={ident}",
        documento_texto_id=cuerpo.id if cuerpo is not None else None,
        prefiltro_estado=EstadoPrefiltro.RELEVANTE,
        prefiltro_terminos=["lgtbi"],
        prefiltro_version="2026.08.06",
        prefiltro_evaluado_en=datetime.datetime.now(datetime.UTC),
    )


def _proveedor(respuestas: list[str]) -> ProveedorGuionizado:
    return ProveedorGuionizado(respuestas, modelo="modelo-test")


class TestExtraccionFeliz:
    def test_extrae_y_persiste_una_norma_relevante(
        self, session: Session, documento: Documento, almacen: Path
    ) -> None:
        cuerpo = _cuerpo_archivado(session, documento, "BOE-A-2023-5366", XML_NORMA, almacen)
        session.add(_norma_relevante(documento, "BOE-A-2023-5366", cuerpo=cuerpo))
        session.commit()

        resumen = servicio.aplicar(
            session,
            _proveedor([json.dumps(EXTRACCION_VALIDA)]),
            almacen_root=almacen,
            documento_id=documento.id,
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

    def test_lo_que_ve_el_llm_es_el_texto_archivado(
        self, session: Session, documento: Documento, almacen: Path
    ) -> None:
        """La precondición de 7.5, como test y no como comentario.

        Si el LLM viera una segunda descarga en vez del archivado, citar su salida contra el
        archivo sería una coincidencia y no una garantía. Aquí se comprueba de la única forma
        que lo demuestra: se archiva un contenido y se mira qué texto recibió el proveedor.
        """
        cuerpo = _cuerpo_archivado(session, documento, "BOE-A-1", XML_NORMA, almacen)
        session.add(_norma_relevante(documento, "BOE-A-1", cuerpo=cuerpo))
        session.commit()

        proveedor = _proveedor([json.dumps(EXTRACCION_VALIDA)])
        servicio.aplicar(session, proveedor, almacen_root=almacen, documento_id=documento.id)

        enviado = " ".join(contenido for _, contenido in proveedor.llamadas)
        assert "Contenido real de la disposicion." in enviado
        assert "ruido de metadatos" not in enviado, "el <analisis> no debe llegar al modelo"

    def test_es_idempotente(self, session: Session, documento: Documento, almacen: Path) -> None:
        cuerpo = _cuerpo_archivado(session, documento, "BOE-A-1", XML_NORMA, almacen)
        session.add(_norma_relevante(documento, "BOE-A-1", cuerpo=cuerpo))
        session.commit()

        primera = servicio.aplicar(
            session,
            _proveedor([json.dumps(EXTRACCION_VALIDA)]),
            almacen_root=almacen,
            documento_id=documento.id,
        )
        segunda = servicio.aplicar(
            session,
            _proveedor([json.dumps(EXTRACCION_VALIDA)]),
            almacen_root=almacen,
            documento_id=documento.id,
        )

        assert primera.extraidas == 1
        assert segunda.evaluadas == 0
        assert session.scalar(select(Deteccion.id).limit(2).offset(1)) is None


class TestNoSeTocaLoQueNoToca:
    def test_ignora_normas_no_relevantes(
        self, session: Session, documento: Documento, almacen: Path
    ) -> None:
        cuerpo_a = _cuerpo_archivado(session, documento, "BOE-A-1", XML_NORMA, almacen)
        cuerpo_b = _cuerpo_archivado(
            session, documento, "BOE-A-2", XML_NORMA + b"<!--b-->", almacen
        )
        pendiente = Norma(
            documento_id=documento.id,
            identificador_oficial="BOE-A-1",
            titulo="Orden del modelo 190",
            url_texto="https://www.boe.es/x.xml",
            documento_texto_id=cuerpo_a.id,
        )
        descartada = _norma_relevante(documento, "BOE-A-2", cuerpo=cuerpo_b)
        descartada.prefiltro_estado = EstadoPrefiltro.DESCARTADA
        session.add_all([pendiente, descartada])
        session.commit()

        resumen = servicio.aplicar(
            session, _proveedor([]), almacen_root=almacen, documento_id=documento.id
        )

        assert resumen == servicio.ResumenExtraccion(evaluadas=0, extraidas=0, fallidas=0)
        assert session.scalar(select(Deteccion)) is None

    def test_sin_cuerpo_archivado_no_entra_en_la_cola(
        self, session: Session, documento: Documento, almacen: Path
    ) -> None:
        """Una norma relevante sin cuerpo **no es un fallo de extracción**: le falta la fase 2.

        Se cuenta como cero evaluadas y no como una fallida a propósito. Un embudo que cuenta
        como fracaso lo que aún no se ha intentado infla las fallidas con trabajo pendiente, y
        entonces la cifra deja de servir para detectar fallos de verdad.
        """
        session.add(_norma_relevante(documento, "BOE-A-1", cuerpo=None))
        session.commit()

        resumen = servicio.aplicar(
            session, _proveedor([]), almacen_root=almacen, documento_id=documento.id
        )

        assert resumen == servicio.ResumenExtraccion(evaluadas=0, extraidas=0, fallidas=0)
        assert session.scalar(select(Deteccion)) is None

    def test_solo_toca_el_documento_indicado(
        self, session: Session, documento: Documento, almacen: Path
    ) -> None:
        otro = Documento(
            fuente_id=documento.fuente_id,
            identificador_oficial="BOE-S-2024-305",
            fecha_publicacion=datetime.date(2024, 12, 19),
            url_original="https://www.boe.es/datosabiertos/api/boe/sumario/20241219",
            sha256="1" * 64,
            sello_tiempo=datetime.datetime.now(datetime.UTC),
            ruta_almacen="11/11/" + "1" * 64 + ".xml",
            estado_pipeline=EstadoPipeline.INGERIDO,
            tipo=TipoDocumento.SUMARIO,
        )
        session.add(otro)
        session.flush()
        cuerpo_a = _cuerpo_archivado(session, documento, "BOE-A-1", XML_NORMA, almacen)
        cuerpo_b = _cuerpo_archivado(session, otro, "BOE-A-2", XML_NORMA + b"<!--b-->", almacen)
        session.add_all(
            [
                _norma_relevante(documento, "BOE-A-1", cuerpo=cuerpo_a),
                _norma_relevante(otro, "BOE-A-2", cuerpo=cuerpo_b),
            ]
        )
        session.commit()

        resumen = servicio.aplicar(
            session,
            _proveedor([json.dumps(EXTRACCION_VALIDA)]),
            almacen_root=almacen,
            documento_id=documento.id,
        )

        assert resumen.evaluadas == 1
        sin_tocar = session.scalar(select(Norma).where(Norma.identificador_oficial == "BOE-A-2"))
        assert sin_tocar is not None
        assert session.scalar(select(Deteccion).where(Deteccion.norma_id == sin_tocar.id)) is None


class TestFallosNoCreanFila:
    """Descartar, nunca interpretar (CLAUDE.md 6.7) — y aquí, nunca dejar una fila a medias."""

    def test_extraccion_invalida_no_crea_fila(
        self, session: Session, documento: Documento, almacen: Path
    ) -> None:
        """Un veredicto colado (inyección o alucinación) se descarta; no aterriza en ningún lado."""
        cuerpo = _cuerpo_archivado(session, documento, "BOE-A-1", XML_NORMA, almacen)
        session.add(_norma_relevante(documento, "BOE-A-1", cuerpo=cuerpo))
        session.commit()

        manipulada = json.dumps({**EXTRACCION_VALIDA, "clasificacion": "retroceso"})
        resumen = servicio.aplicar(
            session, _proveedor([manipulada]), almacen_root=almacen, documento_id=documento.id
        )

        assert (resumen.evaluadas, resumen.extraidas, resumen.fallidas) == (1, 0, 1)
        assert session.scalar(select(Deteccion)) is None

    def test_xml_malformado_no_crea_fila(
        self, session: Session, documento: Documento, almacen: Path
    ) -> None:
        """Archivarlo no lo hace confiable: el XML del almacén también pasa por `xml_safe`."""
        cuerpo = _cuerpo_archivado(session, documento, "BOE-A-1", b"<no-cierra>", almacen)
        session.add(_norma_relevante(documento, "BOE-A-1", cuerpo=cuerpo))
        session.commit()

        resumen = servicio.aplicar(
            session, _proveedor([]), almacen_root=almacen, documento_id=documento.id
        )

        assert (resumen.evaluadas, resumen.extraidas, resumen.fallidas) == (1, 0, 1)
        assert session.scalar(select(Deteccion)) is None

    def test_cuerpo_que_falta_en_el_almacen_no_crea_fila(
        self, session: Session, documento: Documento, almacen: Path
    ) -> None:
        """La fila promete un fichero que no está: es un archivo incompleto, no una extracción.

        Tiene que contarse y registrarse, no pasar de largo. Es la única señal de que el
        almacén y la base de datos han dejado de estar de acuerdo, y esa discrepancia rompe la
        garantía de 6.5 mucho antes de que nadie intente verificar un hash.
        """
        cuerpo = _cuerpo_archivado(session, documento, "BOE-A-1", XML_NORMA, almacen)
        session.add(_norma_relevante(documento, "BOE-A-1", cuerpo=cuerpo))
        session.commit()
        (almacen / cuerpo.ruta_almacen).unlink()

        resumen = servicio.aplicar(
            session, _proveedor([]), almacen_root=almacen, documento_id=documento.id
        )

        assert (resumen.evaluadas, resumen.extraidas, resumen.fallidas) == (1, 0, 1)
        assert session.scalar(select(Deteccion)) is None


class TestTextoPlano:
    """Vive aquí porque el extractor es su consumidor principal; el módulo es `pipeline/texto`."""

    def test_prefiere_el_elemento_texto_sobre_el_resto_del_arbol(self) -> None:
        """Estructura real del BOE: <analisis> es ruido de metadatos, <texto> es el cuerpo."""
        raiz = fromstring(
            "<documento>"
            "<analisis><anterior><texto>ruido de metadatos</texto></anterior></analisis>"
            "<texto><p>cuerpo real de la norma</p></texto>"
            "</documento>"
        )
        assert texto_plano(raiz) == "cuerpo real de la norma"

    def test_sin_elemento_texto_cae_al_arbol_completo(self) -> None:
        raiz = fromstring("<a>uno <b>dos</b> <c>tres</c></a>")
        assert texto_plano(raiz) == "uno dos tres"


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
