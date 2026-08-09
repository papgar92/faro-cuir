"""Tests de la fase 2: descarga y archivo del texto íntegro (tarea 0.c, ADR 0011 y 0015).

SQLite en memoria más un almacén real en `tmp_path`. El transporte HTTP se simula con
`httpx.MockTransport`, igual que en `test_ingesta_service.py`: el objetivo no es probar
`url_guard` (ya tiene su suite) sino que **este servicio lo usa de verdad y no se lo salta**.

Aquí viven los dos tests de la puerta HTTP que antes estaban en `test_extraccion_service.py`
—URL fuera de la allowlist y norma sin `url_texto`— porque aquí es donde se descarga ahora.
"""

from __future__ import annotations

import datetime
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.documento import Documento, EstadoPipeline, TipoDocumento
from app.models.fuente import AmbitoTerritorial, FormatoFuente, Fuente, TipoFuente
from app.models.norma import Norma
from app.security import hashing
from app.services import texto_integro as servicio

XML_CUERPO = (
    b"<documento><metadatos><identificador>BOE-A-1</identificador></metadatos>"
    b"<texto><p>Cuerpo de la disposicion.</p></texto></documento>"
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
def sumario(session: Session) -> Documento:
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


def _norma(sumario: Documento, ident: str, *, url: str | None) -> Norma:
    return Norma(
        documento_id=sumario.id,
        identificador_oficial=ident,
        titulo=f"Disposicion {ident}",
        url_texto=url,
    )


def _cliente(contenido: bytes, *, llamadas: list[str] | None = None) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if llamadas is not None:
            llamadas.append(str(request.url))
        return httpx.Response(200, content=contenido)

    return httpx.Client(transport=httpx.MockTransport(handler))


def _descargar(session: Session, almacen: Path, client: httpx.Client, **kwargs: object):  # type: ignore[no-untyped-def]
    # `pausa=0` en todos los tests: la pausa real es cortesía con el BOE (6.2) y aquí solo
    # serviría para que la suite tardara. Que exista y se aplique se prueba aparte.
    return servicio.descargar(
        session, almacen_root=almacen, pausa=0.0, limite=100, client=client, **kwargs
    )


class TestDescargaYArchiva:
    def test_archiva_el_cuerpo_y_lo_enlaza(
        self, session: Session, sumario: Documento, almacen: Path
    ) -> None:
        session.add(_norma(sumario, "BOE-A-1", url="https://www.boe.es/diario_boe/xml.php?id=A-1"))
        session.commit()

        resumen = _descargar(session, almacen, _cliente(XML_CUERPO))

        assert (resumen.candidatas, resumen.descargadas, resumen.fallidas) == (1, 1, 0)
        assert resumen.pendientes_restantes == 0

        norma = session.scalar(select(Norma))
        assert norma is not None and norma.documento_texto is not None
        cuerpo = norma.documento_texto
        # La garantía de 6.5, comprobada y no supuesta: el hash es el del byte exacto recibido
        # y el fichero está donde la fila dice que está.
        assert cuerpo.tipo is TipoDocumento.TEXTO_NORMA
        assert cuerpo.sha256 == hashing.sha256_hex(XML_CUERPO)
        assert cuerpo.sello_tiempo is not None
        assert (almacen / cuerpo.ruta_almacen).read_bytes() == XML_CUERPO
        # Hereda la fecha de publicación del sumario (hecho de la fuente) pero tiene su propio
        # sello (cuándo lo vimos). Son dos cosas distintas y 6.5 las necesita separadas.
        assert cuerpo.fecha_publicacion == sumario.fecha_publicacion

    def test_el_cuerpo_no_aparece_en_la_lista_de_sumarios(
        self, session: Session, sumario: Documento, almacen: Path
    ) -> None:
        """El discriminador existe para esto (ADR 0015): sin él la API listaría los cuerpos."""
        session.add(_norma(sumario, "BOE-A-1", url="https://www.boe.es/x.xml"))
        session.commit()
        _descargar(session, almacen, _cliente(XML_CUERPO))

        sumarios = session.scalars(
            select(Documento).where(Documento.tipo == TipoDocumento.SUMARIO)
        ).all()
        assert [d.identificador_oficial for d in sumarios] == ["BOE-S-2023-51"]

    def test_dos_normas_con_el_mismo_texto_comparten_fichero_y_no_fila(
        self, session: Session, sumario: Documento, almacen: Path
    ) -> None:
        """Deduplicación por hash: un fichero, dos filas con su propio sello cada una."""
        session.add_all(
            [
                _norma(sumario, "BOE-A-1", url="https://www.boe.es/a.xml"),
                _norma(sumario, "BOE-A-2", url="https://www.boe.es/b.xml"),
            ]
        )
        session.commit()

        _descargar(session, almacen, _cliente(XML_CUERPO))

        cuerpos = session.scalars(
            select(Documento).where(Documento.tipo == TipoDocumento.TEXTO_NORMA)
        ).all()
        assert len(cuerpos) == 2, "cada norma conserva su propia fila de archivo"
        assert len({c.ruta_almacen for c in cuerpos}) == 1, "mismo contenido, un solo fichero"


class TestIdempotencia:
    def test_la_segunda_pasada_no_pide_nada(
        self, session: Session, sumario: Documento, almacen: Path
    ) -> None:
        """El criterio de la tarea: reejecutar no rehace el trabajo.

        No se comprueba solo el recuento: se cuentan las **peticiones HTTP**. Un servicio que
        volviera a descargar y luego dedujera que ya estaba daría el mismo resumen y habría
        gastado otro día entero de peticiones contra el BOE.
        """
        session.add(_norma(sumario, "BOE-A-1", url="https://www.boe.es/x.xml"))
        session.commit()

        llamadas: list[str] = []
        primera = _descargar(session, almacen, _cliente(XML_CUERPO, llamadas=llamadas))
        segunda = _descargar(session, almacen, _cliente(XML_CUERPO, llamadas=llamadas))

        assert primera.descargadas == 1
        assert segunda.candidatas == 0 and segunda.descargadas == 0
        assert len(llamadas) == 1, "la segunda pasada no debe pedir nada"


class TestTopeYCola:
    def test_el_tope_por_ejecucion_deja_el_resto_en_cola(
        self, session: Session, sumario: Documento, almacen: Path
    ) -> None:
        """El tope de 6.2 es un tope, no una cuota: lo que no entra hoy sigue en cola."""
        session.add_all(
            [_norma(sumario, f"BOE-A-{i}", url=f"https://www.boe.es/{i}.xml") for i in range(5)]
        )
        session.commit()

        resumen = servicio.descargar(
            session,
            almacen_root=almacen,
            pausa=0.0,
            limite=2,
            client=_cliente(XML_CUERPO),
        )

        assert resumen.descargadas == 2
        assert resumen.pendientes_restantes == 3

    def test_una_norma_sin_url_no_entra_en_la_cola_ni_cuenta_como_fallo(
        self, session: Session, sumario: Documento, almacen: Path
    ) -> None:
        """Un ítem que no publica texto propio no es error nuestro: no ensucia el embudo."""
        session.add(_norma(sumario, "BOE-A-1", url=None))
        session.commit()

        resumen = _descargar(session, almacen, _cliente(XML_CUERPO))

        assert resumen == servicio.ResumenFase2(
            candidatas=0, descargadas=0, fallidas=0, bytes_descargados=0, pendientes_restantes=0
        )


class TestPuertaHTTP:
    def test_url_fuera_de_la_allowlist_no_archiva_nada(
        self, session: Session, sumario: Documento, almacen: Path
    ) -> None:
        """El sumario no elige a qué host nos conectamos (ADR 0006): esto es SSRF, no un 404."""
        session.add(_norma(sumario, "BOE-A-1", url="https://evil.example.com/x.xml"))
        session.commit()

        resumen = _descargar(session, almacen, _cliente(XML_CUERPO))

        assert (resumen.descargadas, resumen.fallidas) == (0, 1)
        cuerpos = select(Documento).where(Documento.tipo == TipoDocumento.TEXTO_NORMA)
        assert session.scalar(cuerpos) is None
        norma = session.scalar(select(Norma))
        assert norma is not None and norma.documento_texto_id is None

    def test_un_fallo_deja_la_norma_en_cola_para_la_proxima_pasada(
        self, session: Session, sumario: Documento, almacen: Path
    ) -> None:
        """Todo el reintento que hace falta: no marcar nada y volver a salir en la cola."""
        session.add(_norma(sumario, "BOE-A-1", url="https://evil.example.com/x.xml"))
        session.commit()

        resumen = _descargar(session, almacen, _cliente(XML_CUERPO))

        assert resumen.pendientes_restantes == 1
