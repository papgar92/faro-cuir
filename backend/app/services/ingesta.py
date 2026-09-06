"""Persistencia de lo ingerido: convierte un sumario descargado en filas y ficheros.

Separado de `ingest/boe.py` a propósito. Ahí vive lo que es específico de cada fuente
(cómo se descarga y cómo se lee su XML); aquí vive lo que es igual para las 18: calcular la
huella, archivar el contenido crudo y crear la fila de `documento` sin duplicar.

**Todas devuelven una tupla de resultados, aunque cuatro de las seis solo puedan devolver uno.**
El BOPV publica **dos ediciones el mismo día** cinco veces en 33 meses medidos (ADR 0035), y un
boletín extraordinario es exactamente donde cae una disposición con prisa. La firma es uniforme y
no un caso especial del BOPV porque «un día trae uno o más boletines» es una propiedad del
dominio, no de una fuente: el BOJA también publica extraordinarios, y el día que se integre no
tendrá que cambiar esta interfaz para no perderlos.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ingest import boa, bocm, bocyl, boe, bon, bopv, dogc
from app.ingest.boe import Sumario
from app.models.documento import Documento, EstadoPipeline, TipoDocumento
from app.models.norma import Norma
from app.security import hashing
from app.services.archivo import archivar


@dataclass(frozen=True)
class ResultadoIngesta:
    documento_id: int
    sumario: Sumario
    sha256: str
    ruta_almacen: str
    # False cuando el sumario ya estaba ingerido. Es el caso normal al reintentar, no un
    # error: el worker es idempotente por diseño (CLAUDE.md sección 3).
    creado: bool
    # Cuántas normas nuevas se registraron. En una reingesta limpia será 0.
    normas_creadas: int


def _buscar_documento(session: Session, *, fuente_id: int, identificador: str) -> Documento | None:
    return session.scalar(
        select(Documento).where(
            Documento.fuente_id == fuente_id,
            Documento.identificador_oficial == identificador,
        )
    )


def _sincronizar_normas(session: Session, *, documento_id: int, sumario: Sumario) -> int:
    """Registra como `norma` los items del sumario que aún no estén.

    Se comparan los identificadores ya guardados contra los del sumario en vez de intentar
    insertar y capturar el error: así una ingesta que se quedó a medias (documento guardado
    pero normas no) se completa al reintentar, en vez de darse por buena porque el documento
    ya existía.
    """
    ya_guardados = set(
        session.scalars(
            select(Norma.identificador_oficial).where(Norma.documento_id == documento_id)
        ).all()
    )

    nuevas = [
        Norma(
            documento_id=documento_id,
            identificador_oficial=item.identificador,
            titulo=item.titulo,
            url_texto=item.url_xml,
            # El departamento del sumario es el órgano que emite: es dato real de la fuente,
            # no una deducción. `rango` y `ambito` se quedan en NULL a propósito — del título
            # no se pueden saber sin leer el texto completo, y rellenarlos a ojo sería
            # justamente lo que prohíbe la regla de oro 8.
            organo_emisor=item.departamento or None,
        )
        for item in sumario.items
        if item.identificador not in ya_guardados
    ]

    session.add_all(nuevas)
    return len(nuevas)


def ingerir_sumario_boe(
    session: Session,
    *,
    fuente_id: int,
    fecha: datetime.date,
    almacen_root: Path,
    client: httpx.Client | None = None,
) -> tuple[ResultadoIngesta, ...]:
    """Descarga, archiva y registra el sumario del BOE de una fecha, con sus normas.

    Idempotente: volver a lanzarlo sobre una fecha ya ingerida no duplica nada.
    """
    contenido = boe.descargar_sumario(fecha, client=client)
    sumario = boe.parsear_sumario(contenido, fecha_esperada=fecha)
    return (
        _archivar_y_registrar(
            session,
            fuente_id=fuente_id,
            sumario=sumario,
            contenido=contenido,
            url_original=boe.url_sumario(fecha),
            almacen_root=almacen_root,
        ),
    )


def ingerir_sumario_dogc(
    session: Session,
    *,
    fuente_id: int,
    fecha: datetime.date,
    almacen_root: Path,
    client: httpx.Client | None = None,
) -> tuple[ResultadoIngesta, ...]:
    """Lo mismo para el DOGC (ADR 0019), segunda fuente y primera autonómica.

    Comparte todo lo que va después de parsear —archivo con huella, alta del documento,
    sincronización de normas— porque el archivo (6.5) y la idempotencia no pueden depender de
    qué boletín sea: dos implementaciones de esto serían dos garantías distintas.
    """
    contenido = dogc.descargar_sumario(fecha, client=client)
    sumario = dogc.parsear_sumario(contenido, fecha)
    return (
        _archivar_y_registrar(
            session,
            fuente_id=fuente_id,
            sumario=sumario,
            contenido=contenido,
            url_original=dogc.url_sumario(fecha),
            almacen_root=almacen_root,
        ),
    )


def ingerir_sumario_boa(
    session: Session,
    *,
    fuente_id: int,
    fecha: datetime.date,
    almacen_root: Path,
    client: httpx.Client | None = None,
) -> tuple[ResultadoIngesta, ...]:
    """Lo mismo para el BOA (ADR 0028), tercera fuente y segunda autonómica.

    Comparte con las otras dos todo lo que va después de parsear, por el mismo motivo: el
    archivo (6.5) y la idempotencia no pueden depender de qué boletín sea.
    """
    contenido = boa.descargar_sumario(fecha, client=client)
    sumario = boa.parsear_sumario(contenido, fecha)
    return (
        _archivar_y_registrar(
            session,
            fuente_id=fuente_id,
            sumario=sumario,
            contenido=contenido,
            url_original=boa.url_sumario(fecha),
            almacen_root=almacen_root,
        ),
    )


def ingerir_sumario_bocyl(
    session: Session,
    *,
    fuente_id: int,
    fecha: datetime.date,
    almacen_root: Path,
    client: httpx.Client | None = None,
) -> tuple[ResultadoIngesta, ...]:
    """Lo mismo para el BOCYL (ADR 0029), cuarta fuente y tercera autonómica.

    Comparte con las otras tres todo lo que va después de parsear: el archivo (6.5) y la
    idempotencia no pueden depender de qué boletín sea.
    """
    contenido = bocyl.descargar_sumario(fecha, client=client)
    sumario = bocyl.parsear_sumario(contenido, fecha)
    return (
        _archivar_y_registrar(
            session,
            fuente_id=fuente_id,
            sumario=sumario,
            contenido=contenido,
            url_original=bocyl.url_sumario(fecha),
            almacen_root=almacen_root,
        ),
    )


def ingerir_sumario_bocm(
    session: Session,
    *,
    fuente_id: int,
    fecha: datetime.date,
    almacen_root: Path,
    client: httpx.Client | None = None,
) -> tuple[ResultadoIngesta, ...]:
    """Lo mismo para el BOCM (ADR 0034), quinta fuente y cuarta autonómica.

    Comparte con las otras cuatro todo lo que va después de parsear: el archivo (6.5) y la
    idempotencia no pueden depender de qué boletín sea.
    """
    contenido = bocm.descargar_sumario(fecha, client=client)
    sumario = bocm.parsear_sumario(contenido, fecha)
    return (
        _archivar_y_registrar(
            session,
            fuente_id=fuente_id,
            sumario=sumario,
            contenido=contenido,
            url_original=bocm.url_sumario(fecha),
            almacen_root=almacen_root,
        ),
    )


def ingerir_sumario_bopv(
    session: Session,
    *,
    fuente_id: int,
    fecha: datetime.date,
    almacen_root: Path,
    client: httpx.Client | None = None,
) -> tuple[ResultadoIngesta, ...]:
    """Lo mismo para el BOPV (ADR 0035), sexta fuente y quinta autonómica.

    **La única que puede devolver más de un resultado**, y por eso la firma de todas es una
    tupla: un día del BOPV puede traer dos ediciones, y quedarse con la primera perdería un
    boletín extraordinario entero en silencio. El calendario del mes —una petición de 1,5 KB—
    dice cuántas hay antes de pedir ninguna.
    """
    ediciones = bopv.resolver_ediciones(fecha, client=client)
    resultados = []
    for edicion in ediciones:
        contenido = bopv.descargar_sumario(fecha, edicion, client=client)
        sumario = bopv.parsear_sumario(contenido, fecha, edicion)
        resultados.append(
            _archivar_y_registrar(
                session,
                fuente_id=fuente_id,
                sumario=sumario,
                contenido=contenido,
                url_original=bopv.url_sumario(fecha, edicion),
                almacen_root=almacen_root,
            )
        )
    return tuple(resultados)


def ingerir_sumario_bon(
    session: Session,
    *,
    fuente_id: int,
    fecha: datetime.date,
    almacen_root: Path,
    client: httpx.Client | None = None,
) -> tuple[ResultadoIngesta, ...]:
    """Lo mismo para el BON (ADR 0036), séptima fuente y sexta autonómica.

    La segunda que puede devolver más de un resultado: Navarra también publica extraordinarios
    el mismo día (los boletines 253 y 254 son los dos del 16 de diciembre de 2024).

    **Y la más cara de resolver**: el BON no publica calendario y su búsqueda por fecha miente,
    así que la fecha se resuelve por bisección sobre el número de boletín, leyendo la cabecera
    que declara cada candidato. Hasta `bon.MAX_SONDEOS` peticiones por día.
    """
    numeros = bon.resolver_ediciones(fecha, client=client)
    resultados = []
    for numero in numeros:
        contenido = bon.descargar_sumario(fecha, numero, client=client)
        sumario = bon.parsear_sumario(contenido, fecha, numero)
        resultados.append(
            _archivar_y_registrar(
                session,
                fuente_id=fuente_id,
                sumario=sumario,
                contenido=contenido,
                url_original=bon.url_sumario(fecha.year, numero),
                almacen_root=almacen_root,
            )
        )
    return tuple(resultados)


def _archivar_y_registrar(
    session: Session,
    *,
    fuente_id: int,
    sumario: boe.Sumario,
    contenido: bytes,
    url_original: str,
    almacen_root: Path,
) -> ResultadoIngesta:
    """Lo que es igual para toda fuente: huella, sello, alta y normas. Idempotente."""
    digest = hashing.sha256_hex(contenido)
    ruta_relativa = archivar(contenido, digest, almacen_root=almacen_root)

    documento = _buscar_documento(session, fuente_id=fuente_id, identificador=sumario.identificador)
    creado = False

    if documento is None:
        documento = Documento(
            fuente_id=fuente_id,
            identificador_oficial=sumario.identificador,
            fecha_publicacion=sumario.fecha_publicacion,
            url_original=url_original,
            sha256=digest,
            # Cuándo lo vimos nosotros, en UTC explícito. Junto al sha256 es lo que sostiene
            # la afirmación "el día X esto decía exactamente esto" (CLAUDE.md 6.5).
            sello_tiempo=datetime.datetime.now(datetime.UTC),
            ruta_almacen=ruta_relativa,
            estado_pipeline=EstadoPipeline.INGERIDO,
            # Explícito aunque sea el valor por defecto: desde el ADR 0015 `documento` tiene
            # dos clases de fila y dar por supuesta la propia es cómo se acaba archivando un
            # cuerpo con el tipo equivocado.
            tipo=TipoDocumento.SUMARIO,
        )
        session.add(documento)
        try:
            session.flush()
            creado = True
        except IntegrityError:
            # Dos ejecuciones del cron solapadas pueden pasar las dos por el SELECT de arriba
            # antes de que ninguna inserte. La restricción única de la tabla es la que decide
            # de verdad; aquí solo se recoge el resultado de esa carrera.
            session.rollback()
            documento = _buscar_documento(
                session, fuente_id=fuente_id, identificador=sumario.identificador
            )
            if documento is None:
                raise

    normas_creadas = _sincronizar_normas(session, documento_id=documento.id, sumario=sumario)
    session.commit()

    return ResultadoIngesta(
        documento_id=documento.id,
        sumario=sumario,
        sha256=documento.sha256,
        ruta_almacen=documento.ruta_almacen,
        creado=creado,
        normas_creadas=normas_creadas,
    )
