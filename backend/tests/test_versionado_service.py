"""Tests del servicio que puebla `version_norma` (ADR 0018).

SQLite en memoria, almacén real en `tmp_path` y el transporte HTTP simulado con
`httpx.MockTransport`, igual que en `test_texto_integro.py`: el objetivo no es probar
`url_guard` —tiene su propia suite— sino que **este servicio lo usa de verdad y no se lo salta**,
y que la URL que pide es la de la watchlist y no la que trae el documento (6.10).

El caso de todos los tests es el real: `BOE-A-2024-10767`, la reforma madrileña de 2023, cuyo
`<analisis>` archivado declara que MODIFICA `BOE-A-2016-6728`.
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
from app.models.norma import EstadoPrefiltro, Norma, VersionNorma
from app.pipeline import watchlist
from app.pipeline.watchlist import NormaVigilada, Watchlist
from app.security import hashing
from app.services import versionado as servicio
from app.services.archivo import archivar

FIXTURES = Path(__file__).parent / "fixtures"
CUERPO_REAL = (FIXTURES / "boe_a_2024_10767_recortado.xml").read_bytes()
CONSOLIDADO = (FIXTURES / "boe_a_2016_6728_consolidado_recortado.xml").read_bytes()
REFORMA = "BOE-A-2024-10767"
VIGILADA = "BOE-A-2016-6728"

LISTA = Watchlist(
    version="test",
    normas=(
        NormaVigilada(
            identificador=VIGILADA,
            titulo="Ley 2/2016 de Identidad y Expresión de Género (Madrid)",
            nota="fixture",
            ambito="MD",
        ),
    ),
)


@pytest.fixture(autouse=True)
def watchlist_de_prueba(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(watchlist, "watchlist", lambda: LISTA)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    fabrica = sessionmaker(bind=engine)
    with fabrica() as sesion:
        yield sesion
    engine.dispose()


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
    documento = Documento(
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
    session.add(documento)
    session.flush()
    return documento


def _norma_con_cuerpo(
    session: Session,
    sumario: Documento,
    almacen: Path,
    *,
    ident: str = REFORMA,
    contenido: bytes = CUERPO_REAL,
    estado: EstadoPrefiltro = EstadoPrefiltro.RELEVANTE,
) -> Norma:
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
    norma = Norma(
        documento_id=sumario.id,
        identificador_oficial=ident,
        titulo=f"Ley que modifica a {VIGILADA}",
        url_texto=f"https://www.boe.es/diario_boe/xml.php?id={ident}",
        documento_texto_id=cuerpo.id,
        prefiltro_estado=estado,
        prefiltro_terminos=[],
        prefiltro_evaluado_en=datetime.datetime.now(datetime.UTC),
    )
    session.add(norma)
    session.flush()
    return norma


def _cliente(
    respuesta: bytes | httpx.Response = CONSOLIDADO, *, llamadas: list[str] | None = None
) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if llamadas is not None:
            # El *host* de la URL es la IP, no el nombre: `url_guard` clava la petición a la IP
            # ya validada y manda el nombre en `Host` (defensa contra DNS rebinding). Se
            # registra la pareja que de verdad define el destino.
            llamadas.append(f"{request.headers.get('host')}{request.url.path}")
        if isinstance(respuesta, httpx.Response):
            return respuesta
        return httpx.Response(200, content=respuesta)

    return httpx.Client(transport=httpx.MockTransport(handler))


def _poblar(session: Session, almacen: Path, client: httpx.Client, **kwargs: object):  # type: ignore[no-untyped-def]
    # `pausa=0`: la pausa real es cortesía con el BOE (6.2) y aquí solo haría lenta la suite.
    return servicio.poblar(
        session, almacen_root=almacen, pausa=0.0, limite=10, client=client, **kwargs
    )


class TestDiffPersistido:
    def test_guarda_una_version_por_bloque_tocado(
        self, session: Session, sumario: Documento, tmp_path: Path
    ) -> None:
        """El hecho que el proyecto no podía establecer hasta hoy: qué decía antes."""
        norma = _norma_con_cuerpo(session, sumario, tmp_path)
        session.commit()

        resumen = _poblar(session, tmp_path, _cliente())

        assert (resumen.candidatas, resumen.consultadas, resumen.con_diff) == (1, 1, 1)
        assert (resumen.filas, resumen.sin_consolidar, resumen.fallidas) == (2, 0, 0)
        assert resumen.por_norma_afectada == {VIGILADA: 2}

        versiones = session.scalars(select(VersionNorma).order_by(VersionNorma.ordinal)).all()
        assert [v.bloque for v in versiones] == ["a4", "a7"]
        assert all(v.norma_id == norma.id for v in versiones)
        assert all(v.norma_afectada == VIGILADA for v in versiones)
        assert versiones[0].texto_anterior is not None
        assert "identidad de género libremente manifestada" in versiones[0].texto_anterior
        assert "personas transexuales" in (versiones[0].texto_nuevo or "")
        assert versiones[0].fecha_vigencia == datetime.date(2023, 12, 30)
        assert versiones[0].version_derivacion

    def test_archiva_el_consolidado_con_su_huella_y_lo_enlaza(
        self, session: Session, sumario: Documento, tmp_path: Path
    ) -> None:
        """6.5: un diff sin la evidencia archivada detrás no se puede rebatir."""
        _norma_con_cuerpo(session, sumario, tmp_path)
        session.commit()

        _poblar(session, tmp_path, _cliente())

        archivo = session.scalar(
            select(Documento).where(Documento.tipo == TipoDocumento.CONSOLIDADO)
        )
        assert archivo is not None
        assert archivo.sha256 == hashing.sha256_hex(CONSOLIDADO)
        assert archivo.identificador_oficial.startswith(f"{VIGILADA}-consolidado-")
        assert (tmp_path / archivo.ruta_almacen).read_bytes() == CONSOLIDADO

        version = session.scalar(select(VersionNorma))
        assert version is not None and version.documento_consolidado_id == archivo.id

    def test_no_clasifica_nada(self, session: Session, sumario: Documento, tmp_path: Path) -> None:
        """Esta etapa establece el hecho; el veredicto es del catálogo de reglas (7.6)."""
        _norma_con_cuerpo(session, sumario, tmp_path)
        session.commit()

        _poblar(session, tmp_path, _cliente())

        from app.models.deteccion import Deteccion

        assert session.scalars(select(Deteccion)).all() == []


class TestIdempotencia:
    def test_una_segunda_pasada_no_pide_nada_ni_duplica(
        self, session: Session, sumario: Documento, tmp_path: Path
    ) -> None:
        _norma_con_cuerpo(session, sumario, tmp_path)
        session.commit()
        llamadas: list[str] = []

        _poblar(session, tmp_path, _cliente(llamadas=llamadas))
        segunda = _poblar(session, tmp_path, _cliente(llamadas=llamadas))

        assert len(llamadas) == 1
        assert (segunda.candidatas, segunda.consultadas, segunda.filas) == (0, 0, 0)
        assert len(session.scalars(select(VersionNorma)).all()) == 2


class TestPuertaHttp:
    def test_pide_la_url_de_la_watchlist_no_la_del_documento(
        self, session: Session, sumario: Documento, tmp_path: Path
    ) -> None:
        """6.10: el `<analisis>` elige a qué entrada mirar, nunca compone la dirección."""
        _norma_con_cuerpo(session, sumario, tmp_path)
        session.commit()
        llamadas: list[str] = []

        _poblar(session, tmp_path, _cliente(llamadas=llamadas))

        assert llamadas == [f"www.boe.es/datosabiertos/api/legislacion-consolidada/id/{VIGILADA}"]

    def test_un_404_es_sin_consolidar_y_no_un_fallo(
        self, session: Session, sumario: Documento, tmp_path: Path
    ) -> None:
        """La fuente consolida con retraso: 'todavía no' no puede contarse como avería."""
        _norma_con_cuerpo(session, sumario, tmp_path)
        session.commit()

        resumen = _poblar(session, tmp_path, _cliente(httpx.Response(404, content=b"")))

        assert (resumen.sin_consolidar, resumen.fallidas, resumen.filas) == (1, 0, 0)
        assert session.scalars(select(VersionNorma)).all() == []

    def test_un_consolidado_que_aun_no_recoge_el_cambio_no_escribe_nada(
        self, session: Session, sumario: Documento, tmp_path: Path
    ) -> None:
        sin_la_reforma = CONSOLIDADO.replace(REFORMA.encode(), b"BOE-A-1999-00001")
        _norma_con_cuerpo(session, sumario, tmp_path)
        session.commit()

        resumen = _poblar(session, tmp_path, _cliente(sin_la_reforma))

        assert (resumen.sin_consolidar, resumen.con_diff) == (1, 0)
        assert session.scalars(select(Documento).where(Documento.tipo == "consolidado")).all() == []

    def test_una_respuesta_ilegible_falla_sin_escribir(
        self, session: Session, sumario: Documento, tmp_path: Path
    ) -> None:
        _norma_con_cuerpo(session, sumario, tmp_path)
        session.commit()

        resumen = _poblar(session, tmp_path, _cliente(b"esto no es XML"))

        assert (resumen.fallidas, resumen.filas) == (1, 0)
        assert session.scalars(select(VersionNorma)).all() == []


class TestCola:
    def test_una_norma_que_solo_cita_la_watchlist_no_sale_a_la_red(
        self, session: Session, sumario: Documento, tmp_path: Path
    ) -> None:
        """`CITA` no es `MODIFICA`: es el falso positivo que produce el eje léxico a destajo."""
        citadora = CUERPO_REAL.replace(b"<palabra codigo=", b"<palabra ignorada=").replace(
            b"MODIFICA", b"CITA"
        )
        _norma_con_cuerpo(session, sumario, tmp_path, ident="BOE-A-2024-99999", contenido=citadora)
        session.commit()
        llamadas: list[str] = []

        resumen = _poblar(session, tmp_path, _cliente(llamadas=llamadas))

        assert llamadas == []
        assert (resumen.candidatas, resumen.filas) == (0, 0)

    def test_una_norma_descartada_por_el_prefiltro_no_entra(
        self, session: Session, sumario: Documento, tmp_path: Path
    ) -> None:
        _norma_con_cuerpo(session, sumario, tmp_path, estado=EstadoPrefiltro.DESCARTADA)
        session.commit()

        resumen = _poblar(session, tmp_path, _cliente())

        assert (resumen.candidatas, resumen.consultadas) == (0, 0)

    def test_el_tope_por_ejecucion_deja_el_resto_en_cola(
        self, session: Session, sumario: Documento, tmp_path: Path
    ) -> None:
        """Un tope, no una cuota: lo que no entra hoy sigue en cola y entra mañana."""
        _norma_con_cuerpo(session, sumario, tmp_path)
        _norma_con_cuerpo(session, sumario, tmp_path, ident="BOE-A-2024-10768")
        session.commit()

        resumen = servicio.poblar(
            session, almacen_root=tmp_path, pausa=0.0, limite=1, client=_cliente()
        )

        assert (resumen.candidatas, resumen.consultadas) == (2, 1)
        assert resumen.pendientes_restantes == 1


class TestColaNoSeMuereDeHambre:
    """Hallazgo 1 (ALTO) de la auditoría del 2026-08-16.

    El tope por ejecución se aplicaba sobre una cola ordenada por `id`, y las parejas
    irresolubles —una derogación total no produce diff nunca— tienen los `id` más bajos por ser
    las más antiguas. Veinte de ellas y el versionado deja de mirar lo nuevo **diciendo en el
    resumen que ha consultado veinte**, que es peor que no mirar: es no mirar y decir que sí.
    """

    def test_lo_nunca_intentado_va_antes_que_lo_ya_intentado(
        self, session: Session, sumario: Documento, tmp_path: Path
    ) -> None:
        vieja = _norma_con_cuerpo(session, sumario, tmp_path, ident="BOE-A-2024-00001")
        nueva = _norma_con_cuerpo(session, sumario, tmp_path, ident="BOE-A-2024-99999")
        # La vieja ya se intentó (y no dio diff: es el caso de la derogación total).
        vieja.versionado_intentado_en = datetime.datetime.now(datetime.UTC)
        vieja.versionado_intentos = 7
        session.commit()
        llamadas: list[str] = []

        # Tope de uno: solo cabe una pareja en esta pasada.
        servicio.poblar(
            session,
            almacen_root=tmp_path,
            pausa=0.0,
            limite=1,
            client=_cliente(llamadas=llamadas),
        )

        # La que se consulta es la nueva, aunque su `id` sea mayor.
        assert len(llamadas) == 1
        assert nueva.versionado_intentos == 1
        assert vieja.versionado_intentos == 7

    def test_el_intento_se_marca_aunque_la_descarga_falle(
        self, session: Session, sumario: Documento, tmp_path: Path
    ) -> None:
        """Si no se marcara, una pareja que falla siempre se quedaría fija en cabeza de la cola."""
        norma = _norma_con_cuerpo(session, sumario, tmp_path)
        session.commit()

        _poblar(session, tmp_path, _cliente(httpx.Response(500, content=b"")))

        assert norma.versionado_intentos == 1
        assert norma.versionado_intentado_en is not None
