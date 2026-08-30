"""El barrido del prefiltro confirma por lotes, y por qué eso no es un detalle de rendimiento.

Hasta el 2026-08-23 `aplicar` cargaba todas las normas de golpe y hacía **un solo `commit()` al
final**. Con las 436 normas del corpus original era correcto. Con 69.388 dejó de serlo, y el
fallo se vio en una ejecución real: media hora de barrido en la que la base de datos no cambiaba
ni una fila, indistinguible desde fuera de un proceso colgado, y en la que un Ctrl+C habría
tirado el trabajo entero porque no había confirmación parcial que rescatar.

Aquí se fija lo que arregla eso y —sobre todo— **la trampa que el arreglo evita**. La forma
obvia de paginar es «pide otra vez las que falten hasta que no falte ninguna», y en este
servicio eso no termina nunca: una norma `ilegible` deja `prefiltro_version_texto` a NULL a
propósito (ADR 0020) para que la pasada siguiente vuelva a intentarla, así que **jamás deja de
cumplir la condición de `_pendientes`**. Sin el test, alguien simplifica la paginación por `id`
a esa versión más corta y el worker se queda dando vueltas sobre las mismas normas.
"""

from __future__ import annotations

import datetime
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.documento import Documento, EstadoPipeline, TipoDocumento
from app.models.fuente import AmbitoTerritorial, FormatoFuente, Fuente, TipoFuente
from app.models.norma import EstadoPrefiltro, Norma
from app.security import hashing
from app.services import prefiltro as servicio
from app.services.archivo import archivar

# Ilegible por el mismo motivo que las 172 del DOGC: `xml_safe` rechaza el DOCTYPE (6.1). El
# número al final cambia el sha256 de cada cuerpo, que es lo que los hace ficheros distintos.
ILEGIBLE = "<!DOCTYPE html><html><body>Error {n}</body></html>"

LEGIBLE = (
    '<?xml version="1.0" encoding="UTF-8"?><documento><texto>'
    "<p>Convocatoria {n} de ayudas a la rehabilitacion de fachadas.</p>"
    "</texto></documento>"
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
        url_original=fuente.url_base,
        sha256="0" * 64,
        sello_tiempo=datetime.datetime.now(datetime.UTC),
        ruta_almacen="00/00/" + "0" * 64 + ".xml",
        estado_pipeline=EstadoPipeline.INGERIDO,
        tipo=TipoDocumento.SUMARIO,
    )
    session.add(documento)
    session.flush()
    return documento


def _poblar(
    session: Session,
    sumario: Documento,
    almacen: Path,
    *,
    cuantas: int,
    plantilla: str,
    desde: int = 0,
) -> None:
    """`cuantas` normas con su cuerpo archivado de verdad, como lo deja la fase 2."""
    for i in range(cuantas):
        n = desde + i
        contenido = plantilla.format(n=n).encode()
        digest = hashing.sha256_hex(contenido)
        cuerpo = Documento(
            fuente_id=sumario.fuente_id,
            identificador_oficial=f"DOGC-9{n:05d}",
            fecha_publicacion=sumario.fecha_publicacion,
            url_original=f"https://portaljuridic.gencat.cat/eli/es-ct/o/9{n:05d}/dof/spa/xml",
            sha256=digest,
            sello_tiempo=datetime.datetime.now(datetime.UTC),
            ruta_almacen=archivar(contenido, digest, almacen_root=almacen),
            estado_pipeline=EstadoPipeline.INGERIDO,
            tipo=TipoDocumento.TEXTO_NORMA,
        )
        session.add(cuerpo)
        session.flush()
        session.add(
            Norma(
                documento_id=sumario.id,
                identificador_oficial=f"DOGC-9{n:05d}",
                titulo=f"Anuncio {n} de licitacion de obra publica.",
                url_texto=cuerpo.url_original,
                documento_texto_id=cuerpo.id,
            )
        )
    session.flush()


class TestNoSeRepiteNingunaNorma:
    """El barrido termina y toca cada norma una vez, aunque queden `ilegible`."""

    def test_las_ilegibles_no_provocan_un_barrido_infinito(
        self,
        session: Session,
        sumario: Documento,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Este es el test que sujeta el diseño; ver el docstring del módulo.

        Con 12 normas ilegibles y lotes de 5 hacen falta tres vueltas, así que la paginación se
        ejerce de verdad. Si `_por_lotes` volviera a preguntar «las que falten» en vez de
        avanzar por `id`, esto no terminaría: las 12 siguen cumpliendo la condición después de
        evaluarse.
        """
        monkeypatch.setattr(servicio, "LOTE", 5)
        _poblar(session, sumario, tmp_path, cuantas=12, plantilla=ILEGIBLE)

        resumen = servicio.aplicar(session, almacen_root=tmp_path)

        # `evaluadas == 12` es la mitad del aserto: si se repitieran serían 17, 22, o el test
        # no habría llegado hasta aquí.
        assert resumen.evaluadas == 12
        assert resumen.ilegibles == 12
        estados = set(session.scalars(select(Norma.prefiltro_estado)))
        assert estados == {EstadoPrefiltro.ILEGIBLE}

    def test_una_segunda_pasada_reintenta_las_ilegibles_y_solo_esas(
        self,
        session: Session,
        sumario: Documento,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """El reintento del ADR 0020 sigue vivo: en la pasada siguiente, no dentro de la misma.

        Es la otra cara del test anterior y por eso van juntos. Evitar el bucle no puede
        conseguirse marcando las ilegibles como evaluadas, porque eso las congelaría en ese
        estado para siempre y es justo lo que el ADR 0020 prohíbe.
        """
        monkeypatch.setattr(servicio, "LOTE", 5)
        _poblar(session, sumario, tmp_path, cuantas=6, plantilla=ILEGIBLE)
        _poblar(session, sumario, tmp_path, cuantas=6, plantilla=LEGIBLE, desde=100)
        servicio.aplicar(session, almacen_root=tmp_path)

        segunda = servicio.aplicar(session, almacen_root=tmp_path)

        # Las 6 legibles quedaron evaluadas y no vuelven; las 6 ilegibles sí.
        assert segunda.evaluadas == 6
        assert segunda.ilegibles == 6


class TestLoConfirmadoSobreviveALaInterrupcion:
    """Lo que motivó el cambio: un corte a mitad no puede tirar el barrido entero."""

    def test_los_lotes_ya_cerrados_persisten_si_el_barrido_revienta(
        self,
        session: Session,
        sumario: Documento,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(servicio, "LOTE", 5)
        _poblar(session, sumario, tmp_path, cuantas=12, plantilla=LEGIBLE)
        session.commit()

        original = servicio.leer_cuerpo
        vistas = {"n": 0}

        def revienta_en_la_octava(norma: Norma, **kwargs: object) -> object:
            vistas["n"] += 1
            if vistas["n"] == 8:
                raise KeyboardInterrupt("como un Ctrl+C a mitad del barrido")
            return original(norma, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(servicio, "leer_cuerpo", revienta_en_la_octava)

        with pytest.raises(KeyboardInterrupt):
            servicio.aplicar(session, almacen_root=tmp_path)

        # Lo que la transacción viva tenía a medias se va; lo confirmado, no.
        session.rollback()
        evaluadas = session.scalars(select(Norma).where(Norma.prefiltro_version.is_not(None))).all()
        # El primer lote de 5 se confirmó antes de llegar a la octava norma. Con el commit
        # único del diseño anterior esto sería 0, que es exactamente el trabajo que se perdía.
        assert len(evaluadas) == 5
