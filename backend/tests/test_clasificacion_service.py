"""Tests del servicio que aplica el catálogo de reglas y persiste el veredicto (etapa 4).

SQLite en memoria más un almacén real en `tmp_path`, mismo criterio que
`test_extraccion_service.py`: se prueba la lógica del servicio (¿a quién mira?, ¿qué escribe?,
¿es idempotente?), no el dialecto de la base de datos ni los patrones —eso está en
`test_reglas.py`.

El cuerpo archivado que se usa es el **recorte real** de `BOE-A-2024-10767`, el mismo fichero
que usa `test_reglas.py`. Que las dos capas se prueben contra el mismo documento del BOE es lo
que hace que un cambio en los patrones se vea aquí también.
"""

from __future__ import annotations

import datetime
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.deteccion import Clasificacion, Deteccion, OrigenClasificacion
from app.models.documento import Documento, EstadoPipeline, TipoDocumento
from app.models.fuente import AmbitoTerritorial, FormatoFuente, Fuente, TipoFuente
from app.models.norma import EstadoPrefiltro, Norma
from app.pipeline import reglas, watchlist
from app.pipeline.texto import VERSION_TEXTO_PLANO
from app.pipeline.watchlist import NormaVigilada, Watchlist
from app.security import hashing
from app.services import clasificacion as servicio
from app.services.archivo import archivar

CUERPO_REAL = (Path(__file__).parent / "fixtures" / "boe_a_2024_10767_recortado.xml").read_bytes()

# Un cuerpo sin ninguna supresión: modifica, que es el caso mayoritario del BOE.
CUERPO_SIN_SUPRESIONES = (
    b"<documento><metadatos><identificador>BOE-A-2023-0001</identificador></metadatos>"
    b"<texto><p>Uno. El art\xc3\xadculo 4 queda redactado como sigue: "
    b"\xc2\xabNueva redacci\xc3\xb3n del precepto.\xc2\xbb</p></texto></documento>"
)

LISTA = Watchlist(
    version="test",
    normas=(
        NormaVigilada(
            identificador="BOE-A-2016-6728",
            titulo="Ley 2/2016 de Identidad y Expresión de Género (Madrid)",
            nota="fixture",
            ambito="MD",
        ),
    ),
)


@pytest.fixture(autouse=True)
def watchlist_de_prueba(monkeypatch: pytest.MonkeyPatch) -> None:
    """La watchlist real vive en `config/` y puede reordenarse; aquí se fija una.

    Lo que se prueba es el servicio, no el contenido del fichero de configuración.
    """
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
    ident: str = "BOE-A-2024-10767",
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
        titulo=f"Ley que toca a {ident}",
        url_texto=f"https://www.boe.es/diario_boe/xml.php?id={ident}",
        documento_texto_id=cuerpo.id,
        prefiltro_estado=estado,
        prefiltro_terminos=[],
        prefiltro_evaluado_en=datetime.datetime.now(datetime.UTC),
    )
    session.add(norma)
    session.flush()
    return norma


class TestVeredictoPersistido:
    def test_crea_la_deteccion_con_su_regla_y_sus_spans(
        self, session: Session, sumario: Documento, tmp_path: Path
    ) -> None:
        """7.6: un veredicto sin regla ni evidencia no se puede auditar, así que no vale."""
        norma = _norma_con_cuerpo(session, sumario, tmp_path)
        session.commit()

        resumen = servicio.aplicar(session, almacen_root=tmp_path)

        assert (resumen.evaluadas, resumen.con_veredicto) == (1, 1)
        assert resumen.por_regla == {reglas.R_SUP_NORMA_VIGILADA: 1}

        deteccion = session.scalar(select(Deteccion))
        assert deteccion is not None
        assert deteccion.norma_id == norma.id
        assert deteccion.clasificacion is Clasificacion.RETROCESO
        assert deteccion.origen is OrigenClasificacion.DERIVADO_DIFF
        assert deteccion.regla_aplicada == reglas.R_SUP_NORMA_VIGILADA
        # Sin extracción del modelo: esta detección la sostiene el archivo (ADR 0016).
        assert deteccion.extraccion_json is None

        evidencia = deteccion.evidencia_json
        assert evidencia is not None
        assert len(evidencia["spans"]) == 12
        assert evidencia["version_reglas"] == reglas.VERSION_REGLAS
        assert evidencia["version_texto_plano"] == VERSION_TEXTO_PLANO
        assert evidencia["normas_vigiladas"] == ["BOE-A-2016-6728"]

    def test_actualiza_el_centinela_del_extractor_en_vez_de_crear_otra_fila(
        self, session: Session, sumario: Documento, tmp_path: Path
    ) -> None:
        """Dos veredictos para una norma serían dos verdades y ninguna forma de elegir."""
        norma = _norma_con_cuerpo(session, sumario, tmp_path)
        session.add(
            Deteccion(
                norma_id=norma.id,
                extraccion_json={"extraccion": {"articulos": []}, "punteros": 0},
                clasificacion=Clasificacion.INDETERMINADO,
                origen=OrigenClasificacion.HEURISTICA,
                regla_aplicada=None,
            )
        )
        session.commit()

        servicio.aplicar(session, almacen_root=tmp_path)

        detecciones = list(session.scalars(select(Deteccion)))
        assert len(detecciones) == 1
        assert detecciones[0].clasificacion is Clasificacion.RETROCESO
        assert detecciones[0].regla_aplicada == reglas.R_SUP_NORMA_VIGILADA
        # Lo que dijo el modelo no se pisa: son dos procedencias distintas y las dos se guardan.
        assert detecciones[0].extraccion_json is not None

    def test_sin_supresiones_no_escribe_ningun_veredicto(
        self, session: Session, sumario: Documento, tmp_path: Path
    ) -> None:
        """`None` no es `neutro`: el catálogo solo sabe de supresiones (regla de oro 8)."""
        _norma_con_cuerpo(
            session,
            sumario,
            tmp_path,
            ident="BOE-A-2023-0001",
            contenido=CUERPO_SIN_SUPRESIONES,
        )
        session.commit()

        resumen = servicio.aplicar(session, almacen_root=tmp_path)

        assert (resumen.evaluadas, resumen.con_veredicto) == (1, 0)
        assert session.scalar(select(Deteccion)) is None


class TestColaEIdempotencia:
    def test_la_segunda_pasada_no_evalua_nada(
        self, session: Session, sumario: Documento, tmp_path: Path
    ) -> None:
        _norma_con_cuerpo(session, sumario, tmp_path)
        session.commit()

        servicio.aplicar(session, almacen_root=tmp_path)
        segunda = servicio.aplicar(session, almacen_root=tmp_path)

        assert segunda.evaluadas == 0

    def test_una_norma_sin_veredicto_tambien_queda_marcada_como_evaluada(
        self, session: Session, sumario: Documento, tmp_path: Path
    ) -> None:
        """Es el caso mayoritario, y el que rompería la idempotencia si no se registrara.

        Sin `reglas_evaluado_en`, "no disparó ninguna regla" y "no se ha mirado" serían el mismo
        hueco, y cada pasada volvería a leer y parsear del almacén todos los cuerpos que no
        contienen supresiones — que son casi todos.
        """
        norma = _norma_con_cuerpo(
            session,
            sumario,
            tmp_path,
            ident="BOE-A-2023-0001",
            contenido=CUERPO_SIN_SUPRESIONES,
        )
        session.commit()

        servicio.aplicar(session, almacen_root=tmp_path)
        session.refresh(norma)

        assert norma.reglas_version == reglas.VERSION_REGLAS
        assert norma.reglas_version_texto == VERSION_TEXTO_PLANO
        assert norma.reglas_evaluado_en is not None
        assert servicio.aplicar(session, almacen_root=tmp_path).evaluadas == 0

    def test_subir_la_version_del_catalogo_obliga_a_reevaluar(
        self, session: Session, sumario: Documento, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sin esto, tocar una regla solo afectaría a las normas futuras."""
        _norma_con_cuerpo(session, sumario, tmp_path)
        session.commit()
        servicio.aplicar(session, almacen_root=tmp_path)

        monkeypatch.setattr(reglas, "VERSION_REGLAS", "9999.99.99")
        assert servicio.aplicar(session, almacen_root=tmp_path).evaluadas == 1

    def test_una_norma_descartada_por_el_prefiltro_no_entra(
        self, session: Session, sumario: Documento, tmp_path: Path
    ) -> None:
        """El clasificador está detrás del prefiltro: `descartada` significa fin (sección 7)."""
        _norma_con_cuerpo(session, sumario, tmp_path, estado=EstadoPrefiltro.DESCARTADA)
        session.commit()

        assert servicio.aplicar(session, almacen_root=tmp_path).evaluadas == 0

    def test_una_sospecha_si_entra(
        self, session: Session, sumario: Documento, tmp_path: Path
    ) -> None:
        """`sospecha` es "no he sabido descartarla", no "descartada" (7.2)."""
        _norma_con_cuerpo(session, sumario, tmp_path, estado=EstadoPrefiltro.SOSPECHA)
        session.commit()

        assert servicio.aplicar(session, almacen_root=tmp_path).con_veredicto == 1

    def test_un_cuerpo_que_no_esta_en_el_almacen_no_se_da_por_evaluado(
        self, session: Session, sumario: Documento, tmp_path: Path
    ) -> None:
        """Si el fallo es del almacén y no del documento, la próxima pasada tiene que reintentar."""
        norma = _norma_con_cuerpo(session, sumario, tmp_path)
        session.commit()
        (tmp_path / norma.documento_texto.ruta_almacen).unlink()

        resumen = servicio.aplicar(session, almacen_root=tmp_path)

        assert (resumen.evaluadas, resumen.con_veredicto, resumen.ilegibles) == (1, 0, 1)
        session.refresh(norma)
        assert norma.reglas_evaluado_en is None


class TestPunteros:
    def test_los_punteros_de_la_extraccion_alimentan_el_diagnostico(
        self, session: Session, sumario: Documento, tmp_path: Path
    ) -> None:
        """Se leen del JSON persistido, y **no deciden nada** (ADR 0016, regla de oro 10)."""
        norma = _norma_con_cuerpo(session, sumario, tmp_path)
        session.add(
            Deteccion(
                norma_id=norma.id,
                extraccion_json={
                    "extraccion": {
                        "articulos": [
                            {"identificador": "art. 24"},
                            {"identificador": "art. 999"},
                            {"identificador": "art. 4", "texto_nuevo": "nueva redacción"},
                        ]
                    }
                },
                clasificacion=Clasificacion.INDETERMINADO,
                origen=OrigenClasificacion.HEURISTICA,
            )
        )
        session.commit()

        servicio.aplicar(session, almacen_root=tmp_path)

        evidencia = session.scalar(select(Deteccion)).evidencia_json
        assert evidencia is not None
        assert evidencia["punteros_corroborados"] == ["art. 24"]
        assert evidencia["punteros_sin_corroborar"] == ["art. 999"]

    def test_una_extraccion_con_otra_forma_no_tumba_la_clasificacion(
        self, session: Session, sumario: Documento, tmp_path: Path
    ) -> None:
        """El diagnóstico es tolerante: la fila pudo escribirla otra versión del extractor."""
        norma = _norma_con_cuerpo(session, sumario, tmp_path)
        session.add(
            Deteccion(
                norma_id=norma.id,
                extraccion_json={"formato": "viejo"},
                clasificacion=Clasificacion.INDETERMINADO,
                origen=OrigenClasificacion.HEURISTICA,
            )
        )
        session.commit()

        resumen = servicio.aplicar(session, almacen_root=tmp_path)

        assert resumen.con_veredicto == 1


def test_un_veredicto_obsoleto_no_se_retira_solo(
    session: Session, sumario: Documento, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Una detección es rastro de auditoría: no se borra en silencio, se avisa.

    Un sistema que retira sin decirlo conclusiones que ya emitió hace exactamente lo que este
    proyecto documenta de las desindexaciones administrativas (6.5).
    """
    norma = _norma_con_cuerpo(session, sumario, tmp_path)
    session.commit()
    servicio.aplicar(session, almacen_root=tmp_path)

    # El catálogo cambia y deja de encontrar nada donde antes encontraba. Se anulan los dos
    # detectores que ve este documento y no solo el de supresiones: la reforma madrileña real
    # también reescribe preceptos, así que desde R-MOD-001 (ADR 0018) seguiría teniendo
    # veredicto y el test estaría comprobando otra cosa sin decirlo.
    monkeypatch.setattr(reglas, "VERSION_REGLAS", "9999.99.99")
    monkeypatch.setattr(reglas, "supresiones", lambda texto: ())
    monkeypatch.setattr(reglas, "modificaciones", lambda texto: ())

    resumen = servicio.aplicar(session, almacen_root=tmp_path)

    assert resumen.obsoletos == 1
    deteccion = session.scalar(select(Deteccion).where(Deteccion.norma_id == norma.id))
    assert deteccion is not None
    assert deteccion.regla_aplicada == reglas.R_SUP_NORMA_VIGILADA
