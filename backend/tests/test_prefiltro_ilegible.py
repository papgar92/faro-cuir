"""El quinto estado del prefiltro: `ilegible`. ADR 0020.

Lo que se prueba aquí no es un valor nuevo en un enum, es que **una norma que el sistema no
puede analizar deja de confundirse con una que está en cola**. El caso real que lo motivó son
172 de las 264 normas del DOGC (65 % de la segunda fuente del proyecto): su texto está
descargado y archivado con su huella, y lo que el portal devolvió no es el XML de la norma sino
su página de error, con `<!DOCTYPE html>` dentro. `xml_safe` la rechaza y hace bien (6.1); el
problema era lo que pasaba después, que es nada.

La fixture es esa página de error de verdad, recortada. Un XML inventado con un DOCTYPE probaría
lo mismo del parser y no probaría lo importante: que el caso que se cuela en el archivo tiene
esta forma, y que llega con un HTTP 200.
"""

from __future__ import annotations

import datetime
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.documento import Documento, EstadoPipeline, TipoDocumento
from app.models.fuente import AmbitoTerritorial, FormatoFuente, Fuente, TipoFuente
from app.models.norma import EstadoPrefiltro, Norma
from app.pipeline import prefiltro
from app.pipeline.referencias import ReferenciaAnterior
from app.pipeline.watchlist import watchlist
from app.security import hashing
from app.services import prefiltro as servicio
from app.services.archivo import archivar
from app.services.cuerpo import CuerpoIlegible, leer_cuerpo

PAGINA_DE_ERROR = (
    Path(__file__).parent / "fixtures/dogc_pagina_de_error_recortada.html"
).read_bytes()

# Un cuerpo legible mínimo, para el contraste: la misma norma con XML de verdad no acaba
# `ilegible`. Sin este control el test pasaría igual con un prefiltro que marcara todo ilegible.
CUERPO_LEGIBLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<documento>
  <texto><p>Se modifica el protocolo de atencion a personas trans del sistema de salud.</p></texto>
</documento>
"""


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
        nombre="Diari Oficial de la Generalitat de Catalunya",
        tipo=TipoFuente.BOLETIN_AUTONOMICO,
        ambito_territorial=AmbitoTerritorial.AUTONOMICO,
        ccaa="Catalunya",
        ccaa_codigo="CT",
        formato=FormatoFuente.API,
        url_base="https://analisi.transparenciacatalunya.cat/resource/n6hn-rmy7.json",
        licencia_reutil=None,
        activa=True,
    )
    session.add(fuente)
    session.flush()
    documento = Documento(
        fuente_id=fuente.id,
        identificador_oficial="DOGC-S-2024-10-16",
        fecha_publicacion=datetime.date(2024, 10, 16),
        url_original="https://analisi.transparenciacatalunya.cat/resource/n6hn-rmy7.json",
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
    ident: str = "DOGC-24291044",
    titulo: str = "ORDEN por la que se aprueban las bases de una linea de subvenciones.",
    contenido: bytes = PAGINA_DE_ERROR,
) -> Norma:
    """Una norma del DOGC con su cuerpo ya archivado, tal como lo deja la fase 2.

    El cuerpo se archiva de verdad en `almacen` porque el objeto de estos tests es el camino
    completo —del disco al estado persistido— y un doble del almacén se saltaría justo la parte
    donde estaba el fallo.
    """
    digest = hashing.sha256_hex(contenido)
    ruta = archivar(contenido, digest, almacen_root=almacen)
    cuerpo = Documento(
        fuente_id=sumario.fuente_id,
        identificador_oficial=ident,
        fecha_publicacion=sumario.fecha_publicacion,
        url_original=f"https://portaljuridic.gencat.cat/eli/es-ct/o/{ident}/dof/spa/xml",
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
        titulo=titulo,
        url_texto=cuerpo.url_original,
        documento_texto_id=cuerpo.id,
    )
    session.add(norma)
    session.flush()
    return norma


class TestLeerCuerpo:
    """`leer_cuerpo` tiene que distinguir «no hay cuerpo» de «hay cuerpo y no se puede leer»."""

    def test_sin_cuerpo_archivado_devuelve_none(
        self, session: Session, sumario: Documento, tmp_path: Path
    ) -> None:
        norma = Norma(
            documento_id=sumario.id, identificador_oficial="DOGC-24291045", titulo="Orden"
        )
        session.add(norma)
        session.flush()

        assert leer_cuerpo(norma, almacen_root=tmp_path) is None

    def test_una_pagina_de_error_archivada_levanta_cuerpo_ilegible(
        self, session: Session, sumario: Documento, tmp_path: Path
    ) -> None:
        """El motivo real (`DtdForbidden`) viaja en `__cause__` y no se pierde por el camino."""
        norma = _norma_con_cuerpo(session, sumario, tmp_path)

        with pytest.raises(CuerpoIlegible) as excinfo:
            leer_cuerpo(norma, almacen_root=tmp_path)

        assert type(excinfo.value.__cause__).__name__ == "DtdForbidden"

    def test_un_cuerpo_legible_sigue_devolviendo_su_texto(
        self, session: Session, sumario: Documento, tmp_path: Path
    ) -> None:
        norma = _norma_con_cuerpo(session, sumario, tmp_path, contenido=CUERPO_LEGIBLE)

        cuerpo = leer_cuerpo(norma, almacen_root=tmp_path)

        assert cuerpo is not None
        assert "personas trans" in cuerpo.texto


class TestDecisionDelPrefiltro:
    """La decisión vive en `pipeline/prefiltro.py`, así que se prueba sin base de datos."""

    def test_cuerpo_ilegible_manda_por_encima_de_cualquier_senal_del_titulo(self) -> None:
        """Incluso con el título más fuerte posible: no hay nada que decidir.

        Es la parte contraintuitiva del ADR 0020 y por eso tiene test propio. Un título lleno de
        vocabulario daría `relevante` y metería la norma en la cola del extractor, que lee el
        cuerpo **del almacén**: sumaría un fallo por pasada para siempre y prometería un trabajo
        que nadie puede hacer.
        """
        resultado = prefiltro.evaluar(
            "Orden sobre la atencion sanitaria a personas trans y la identidad de genero",
            cuerpo_ilegible=True,
        )

        assert resultado.estado is EstadoPrefiltro.ILEGIBLE
        assert not resultado.entra_en_la_cola

    def test_conserva_los_terminos_del_titulo(self) -> None:
        """Son la única pista para saber por dónde empezar a recuperarlas a mano."""
        resultado = prefiltro.evaluar(
            "Orden sobre la atencion sanitaria a personas trans", cuerpo_ilegible=True
        )

        assert "personas trans" in resultado.terminos

    def test_no_se_confunde_con_un_texto_vacio(self) -> None:
        """Un cuerpo vacío es «no dice nada» y se descarta; ilegible es «no sabemos qué dice».

        Son conclusiones opuestas sobre la misma norma, y por eso `cuerpo_ilegible` es un
        parámetro y no un `texto_integro=""`.
        """
        vacio = prefiltro.evaluar("Orden de organizacion interna", texto_integro="")
        ilegible = prefiltro.evaluar("Orden de organizacion interna", cuerpo_ilegible=True)

        assert vacio.estado is EstadoPrefiltro.DESCARTADA
        assert ilegible.estado is EstadoPrefiltro.ILEGIBLE

    def test_gana_al_eje_referencial(self) -> None:
        """Caso imposible hoy y fijado a propósito.

        Las referencias salen del `<analisis>`, que vive dentro del documento que no se ha
        podido parsear, así que hoy no pueden coexistir. Si algún día llegaran de otro sitio, el
        estado tiene que seguir siendo `ilegible`: sin cuerpo legible no hay diff que construir
        ni regla que aplicar, y `relevante` prometería una cobertura inexistente.
        """
        lista = watchlist()
        vigilada = lista.normas[0].identificador
        resultado = prefiltro.evaluar(
            "Orden que modifica una norma vigilada",
            referencias=(ReferenciaAnterior(vigilada, "MODIFICA", "el art. 1"),),
            lista=lista,
            cuerpo_ilegible=True,
        )

        assert resultado.estado is EstadoPrefiltro.ILEGIBLE


class TestEstadoPersistido:
    def test_la_norma_queda_ilegible_y_el_embudo_la_cuenta(
        self, session: Session, sumario: Documento, tmp_path: Path
    ) -> None:
        norma = _norma_con_cuerpo(session, sumario, tmp_path)
        session.commit()

        resumen = servicio.aplicar(session, almacen_root=tmp_path)

        assert resumen.ilegibles == 1
        # Y **no** cuenta como pendiente: eso es lo que pasaba antes del ADR 0020, y era
        # indistinguible de «esperando su texto íntegro».
        assert resumen.pendientes == 0
        session.refresh(norma)
        assert norma.prefiltro_estado is EstadoPrefiltro.ILEGIBLE

    def test_no_cuenta_como_evaluada_sobre_texto_integro(
        self, session: Session, sumario: Documento, tmp_path: Path
    ) -> None:
        """La salvedad que acompaña a cualquier cifra de cobertura (7.8) no se puede inflar.

        Contarla aquí diría «esta norma se evaluó sobre su texto íntegro» de una norma cuyo texto
        nadie ha leído, que es la afirmación más peligrosa que este proyecto puede hacer.
        """
        _norma_con_cuerpo(session, sumario, tmp_path)
        session.commit()

        resumen = servicio.aplicar(session, almacen_root=tmp_path)

        assert resumen.sobre_texto_integro == 0

    def test_se_reintenta_en_la_pasada_siguiente(
        self, session: Session, sumario: Documento, tmp_path: Path
    ) -> None:
        """El reintento es deliberado, y es lo único que la recupera sola.

        `prefiltro_version_texto` se queda a NULL, así que la norma sigue en la cola de
        reevaluación. Marcarla como evaluada la dejaría congelada como ilegible aunque su cuerpo
        se volviera legible —otro formato, o un fallo del almacén ya resuelto—, y entonces el
        estado nuevo sería una lápida en vez de una lista de trabajo.
        """
        norma = _norma_con_cuerpo(session, sumario, tmp_path)
        session.commit()
        servicio.aplicar(session, almacen_root=tmp_path)

        session.refresh(norma)
        assert norma.prefiltro_version_texto is None
        assert servicio.aplicar(session, almacen_root=tmp_path).ilegibles == 1

    def test_se_recupera_sola_cuando_el_cuerpo_pasa_a_ser_legible(
        self, session: Session, sumario: Documento, tmp_path: Path
    ) -> None:
        """La otra cara del reintento, y la razón de que exista: esto tiene que poder salir.

        Se simula lo que haría una descarga en otro formato: el mismo `documento` de texto pasa a
        apuntar a un fichero legible. Sin el reintento de la prueba anterior, esta norma se
        quedaría `ilegible` para siempre con el texto bueno ya en el disco.
        """
        norma = _norma_con_cuerpo(session, sumario, tmp_path)
        session.commit()
        servicio.aplicar(session, almacen_root=tmp_path)

        digest = hashing.sha256_hex(CUERPO_LEGIBLE)
        norma.documento_texto.ruta_almacen = archivar(CUERPO_LEGIBLE, digest, almacen_root=tmp_path)
        norma.documento_texto.sha256 = digest
        session.commit()

        resumen = servicio.aplicar(session, almacen_root=tmp_path)

        assert resumen.ilegibles == 0
        session.refresh(norma)
        # Se pregunta por la cola y no por `relevante`: el estado exacto lo decide el umbral de
        # 7.3, que está sin validar y puede moverse. Lo que este test fija es que la norma pasa a
        # estar vigilada de verdad, no en qué peldaño.
        assert norma.prefiltro_estado.entra_en_la_cola_del_extractor
        assert norma.prefiltro_version_texto is not None

    def test_una_norma_sin_cuerpo_sigue_quedando_pendiente(
        self, session: Session, sumario: Documento, tmp_path: Path
    ) -> None:
        """El estado nuevo no puede haberse comido el viejo: son dos huecos distintos.

        `pendiente` es «falta descargarlo» e `ilegible` es «está descargado y no se puede leer».
        Confundirlos en la otra dirección volvería a esconder la cola de la fase 2.
        """
        norma = Norma(
            documento_id=sumario.id,
            identificador_oficial="DOGC-24291046",
            titulo="Orden de organizacion interna",
            url_texto="https://portaljuridic.gencat.cat/eli/es-ct/o/x/dof/spa/xml",
        )
        session.add(norma)
        session.commit()

        resumen = servicio.aplicar(session, almacen_root=tmp_path)

        assert (resumen.pendientes, resumen.ilegibles) == (1, 0)
        session.refresh(norma)
        assert norma.prefiltro_estado is EstadoPrefiltro.PENDIENTE
