"""Tests del servicio de ingesta: archivado en disco e idempotencia.

Se usa un SQLite en memoria en vez del Postgres real. Lo que se prueba aquí es la lógica del
servicio (¿archiva bien?, ¿duplica al reintentar?), no el dialecto de la base de datos; con
SQLite la suite corre en cualquier sitio sin levantar contenedores. La restricción única que
respalda la idempotencia sí se verifica contra Postgres de verdad: la crea la migración y el
job de CI aplica `alembic upgrade head` sobre un Postgres 16 antes de lanzar pytest.
"""

from __future__ import annotations

import datetime
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.documento import Documento, EstadoPipeline
from app.models.fuente import AmbitoTerritorial, FormatoFuente, Fuente, TipoFuente
from app.security import hashing
from app.services import ingesta

FIXTURES = Path(__file__).parent / "fixtures"
FECHA = datetime.date(2024, 12, 19)


@pytest.fixture
def sumario_crudo() -> bytes:
    return (FIXTURES / "boe_sumario_20241219_recortado.xml").read_bytes()


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    fabrica = sessionmaker(bind=engine)
    with fabrica() as sesion:
        yield sesion
    engine.dispose()


@pytest.fixture
def fuente_boe(session: Session) -> Fuente:
    fuente = Fuente(
        nombre="Boletín Oficial del Estado",
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
    session.commit()
    return fuente


def cliente_que_sirve(contenido: bytes, contador: list[int] | None = None) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if contador is not None:
            contador.append(1)
        return httpx.Response(200, content=contenido)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_ingiere_y_archiva_el_sumario(
    session: Session, fuente_boe: Fuente, sumario_crudo: bytes, tmp_path: Path
) -> None:
    with cliente_que_sirve(sumario_crudo) as client:
        (resultado,) = ingesta.ingerir_sumario_boe(
            session, fuente_id=fuente_boe.id, fecha=FECHA, almacen_root=tmp_path, client=client
        )

    assert resultado.creado is True
    assert resultado.sha256 == hashing.sha256_hex(sumario_crudo)

    documento = session.get(Documento, resultado.documento_id)
    assert documento is not None
    assert documento.identificador_oficial == "BOE-S-2024-305"
    assert documento.fecha_publicacion == FECHA
    assert documento.estado_pipeline is EstadoPipeline.INGERIDO
    assert documento.url_original.endswith("/20241219")


def test_lo_archivado_es_byte_a_byte_lo_que_se_descargo(
    session: Session, fuente_boe: Fuente, sumario_crudo: bytes, tmp_path: Path
) -> None:
    """La propiedad de la que depende el archivo verificable de la seccion 6.5."""
    with cliente_que_sirve(sumario_crudo) as client:
        (resultado,) = ingesta.ingerir_sumario_boe(
            session, fuente_id=fuente_boe.id, fecha=FECHA, almacen_root=tmp_path, client=client
        )

    archivado = (tmp_path / resultado.ruta_almacen).read_bytes()
    assert archivado == sumario_crudo
    assert hashing.sha256_hex(archivado) == resultado.sha256


def test_la_ruta_en_disco_se_deriva_del_hash(
    session: Session, fuente_boe: Fuente, sumario_crudo: bytes, tmp_path: Path
) -> None:
    """Ni el titulo ni el identificador de la fuente aparecen en la ruta (seccion 6.3)."""
    with cliente_que_sirve(sumario_crudo) as client:
        (resultado,) = ingesta.ingerir_sumario_boe(
            session, fuente_id=fuente_boe.id, fecha=FECHA, almacen_root=tmp_path, client=client
        )

    digest = resultado.sha256
    assert resultado.ruta_almacen == f"{digest[:2]}/{digest[2:4]}/{digest}.xml"
    assert "BOE-S-2024-305" not in resultado.ruta_almacen


def test_reingerir_la_misma_fecha_no_duplica(
    session: Session, fuente_boe: Fuente, sumario_crudo: bytes, tmp_path: Path
) -> None:
    """Idempotencia: es lo que permite que el cron reintente sin miedo (CLAUDE.md seccion 3)."""
    with cliente_que_sirve(sumario_crudo) as client:
        (primera,) = ingesta.ingerir_sumario_boe(
            session, fuente_id=fuente_boe.id, fecha=FECHA, almacen_root=tmp_path, client=client
        )
        (segunda,) = ingesta.ingerir_sumario_boe(
            session, fuente_id=fuente_boe.id, fecha=FECHA, almacen_root=tmp_path, client=client
        )

    assert primera.creado is True
    assert segunda.creado is False
    assert segunda.documento_id == primera.documento_id
    assert session.scalar(select(func.count()).select_from(Documento)) == 1


def test_no_reescribe_un_fichero_ya_archivado(
    session: Session, fuente_boe: Fuente, sumario_crudo: bytes, tmp_path: Path
) -> None:
    """Mismo hash es mismo contenido: reescribir solo anadiria riesgo de dejarlo a medias."""
    with cliente_que_sirve(sumario_crudo) as client:
        (resultado,) = ingesta.ingerir_sumario_boe(
            session, fuente_id=fuente_boe.id, fecha=FECHA, almacen_root=tmp_path, client=client
        )
        destino = tmp_path / resultado.ruta_almacen
        mtime_inicial = destino.stat().st_mtime_ns

        ingesta.ingerir_sumario_boe(
            session, fuente_id=fuente_boe.id, fecha=FECHA, almacen_root=tmp_path, client=client
        )

    assert destino.stat().st_mtime_ns == mtime_inicial


def test_no_deja_ficheros_temporales_en_el_almacen(
    session: Session, fuente_boe: Fuente, sumario_crudo: bytes, tmp_path: Path
) -> None:
    with cliente_que_sirve(sumario_crudo) as client:
        ingesta.ingerir_sumario_boe(
            session, fuente_id=fuente_boe.id, fecha=FECHA, almacen_root=tmp_path, client=client
        )

    assert list(tmp_path.rglob("*.tmp")) == []


def test_un_sumario_de_otra_fecha_no_se_archiva(
    session: Session, fuente_boe: Fuente, sumario_crudo: bytes, tmp_path: Path
) -> None:
    """Si el contenido no es del dia que pedimos, se para antes de tocar disco ni base de datos."""
    from app.ingest.boe import SumarioInvalido

    with cliente_que_sirve(sumario_crudo) as client, pytest.raises(SumarioInvalido):
        ingesta.ingerir_sumario_boe(
            session,
            fuente_id=fuente_boe.id,
            fecha=datetime.date(2024, 12, 18),
            almacen_root=tmp_path,
            client=client,
        )

    assert session.scalar(select(func.count()).select_from(Documento)) == 0
    assert list(tmp_path.rglob("*.xml")) == []


# --- Un día puede traer más de un boletín (ADR 0035) ----------------------------------------
#
# Esta es la prueba que justifica que `ingerir_sumario_*` devuelva una tupla en las seis fuentes.
# Sin ella, el cambio de firma parece burocracia; con ella se ve lo que compra.

_CALENDARIO_DOBLE = (
    "<script>var diasHabilitados = ['20260504'];"
    "var enlaces = [['s26_0080.shtml','s26_0081.shtml']];</script>"
).encode("iso-8859-1")

_SUMARIO_ORDINARIO = b"""<SUMARIO>
<BOPVSumarioSeccion>OTRAS DISPOSICIONES</BOPVSumarioSeccion>
<BOPVSumarioOrganismo>DEPARTAMENTO DE SALUD</BOPVSumarioOrganismo>
<BOPVSumarioTitulo>ORDEN de convocatoria ordinaria.</BOPVSumarioTitulo>
<BOPVSumarioOrden>1800</BOPVSumarioOrden>
</SUMARIO>"""

# El extraordinario real del 2026-05-04: una sola norma, del maximo rango, en disposiciones
# generales. Es la forma que tiene lo que sale con prisa.
_SUMARIO_EXTRAORDINARIO = b"""<SUMARIO>
<BOPVSumarioSeccion>DISPOSICIONES GENERALES</BOPVSumarioSeccion>
<BOPVSumarioOrganismo>LEHENDAKARITZA</BOPVSumarioOrganismo>
<BOPVSumarioTitulo>DECRETO 2/2026, de 4 de mayo, del lehendakari.</BOPVSumarioTitulo>
<BOPVSumarioOrden>1825</BOPVSumarioOrden>
</SUMARIO>"""


@pytest.fixture
def fuente_bopv(session: Session) -> Fuente:
    fuente = Fuente(
        nombre="Boletín Oficial del País Vasco",
        tipo=TipoFuente.BOLETIN_AUTONOMICO,
        ambito_territorial=AmbitoTerritorial.AUTONOMICO,
        ccaa="País Vasco",
        ccaa_codigo="PV",
        formato=FormatoFuente.API,
        url_base="https://www.euskadi.eus/bopv2/datos/",
        licencia_reutil=None,
        activa=True,
    )
    session.add(fuente)
    session.commit()
    return fuente


def test_las_dos_ediciones_de_un_dia_se_archivan_las_dos(
    session: Session, fuente_bopv: Fuente, tmp_path: Path
) -> None:
    """El 4 de mayo de 2026 el BOPV publicó dos boletines. Los dos tienen que quedar archivados.

    Quedarse con el primero perdería el extraordinario **en silencio**: no falla nada, no aparece
    en ninguna métrica, y la norma simplemente no existe para el sistema. Es el modo de fallo que
    la 6.9.6 describe y que este proyecto no se permite.
    """
    respuestas = {
        "092026.shtml": _CALENDARIO_DOBLE,
        "052026.shtml": _CALENDARIO_DOBLE,
        "s26_0080.xml": _SUMARIO_ORDINARIO,
        "s26_0081.xml": _SUMARIO_EXTRAORDINARIO,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        for sufijo, cuerpo in respuestas.items():
            if request.url.path.endswith(sufijo):
                return httpx.Response(200, content=cuerpo)
        raise AssertionError(f"URL inesperada: {request.url}")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        resultados = ingesta.ingerir_sumario_bopv(
            session,
            fuente_id=fuente_bopv.id,
            fecha=datetime.date(2026, 5, 4),
            almacen_root=tmp_path,
            client=client,
        )

    assert len(resultados) == 2
    assert [r.sumario.identificador for r in resultados] == [
        "BOPV-S-20260504-0080",
        "BOPV-S-20260504-0081",
    ]
    # Dos filas de documento, no una: si el identificador no llevara la edición, la segunda se
    # daría por ya ingerida y no se archivaría nunca.
    assert session.scalar(select(func.count()).select_from(Documento)) == 2
    # Y la norma del extraordinario está, que es de lo que va todo esto.
    extraordinario = resultados[1].sumario
    assert extraordinario.items[0].identificador == "BOPV-D-20260504-1825"
    assert extraordinario.items[0].seccion_nombre == "DISPOSICIONES GENERALES"
