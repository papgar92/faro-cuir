"""Poblar `version_norma`: el texto anterior de lo que se modifica. ADR 0018, CLAUDE.md 5 y 7.6.

Separado de `ingest/boe_consolidado.py` con el mismo criterio que `services/clasificacion.py`
frente a `pipeline/reglas.py`: allí vive qué es un cambio y cómo se lee del consolidado, aquí
vive qué hace ese cambio en la base de datos y con qué frenos sale a la red.

## Qué hace

Para cada norma con cuerpo archivado que declare en su `<analisis>` que **modifica o deroga**
una norma de `config/watchlist.json`, descarga el texto consolidado de la norma vigilada, lo
archiva (6.5) y guarda una fila de `version_norma` por bloque tocado, con el texto de antes y el
de después.

Hasta hoy el catálogo de reglas solo podía tener familias que no necesitan texto anterior
—supresión y derogación (7.6)— porque el BOE modificativo publica la redacción nueva y nunca la
vieja. Esto es lo que desbloquea el resto.

## Los tres controles que sostienen esta etapa

1. **La URL no la propone ningún documento.** Se compone con el identificador de la watchlist,
   que es un fichero versionado del repositorio, y `url_consolidado` revalida el formato antes
   de interpolarlo (6.10). Lo que el `<analisis>` de la norma del día aporta es *a cuál* de las
   entradas de la watchlist hay que mirar, nunca la dirección. Y la petición pasa igualmente por
   `url_guard` entero, allowlist incluida (ADR 0006).
2. **El consolidado se archiva antes de derivar nada de él.** `sha256` y sello, ruta derivada
   del hash, y cada fila de `version_norma` apunta al documento del que salió. Un diff que
   nadie pueda rebatir con el fichero delante no vale para el gate humano.
3. **Ni una línea de esto clasifica.** Ninguna fila dice si el cambio es bueno o malo; eso es
   del catálogo de reglas, con `regla_aplicada` y spans (7.6). Aquí solo se establece el hecho:
   antes decía esto, ahora dice esto otro.

## Sobre reintentar: la consolidación llega con retraso

El BOE tarda —de días a semanas— en meter una modificación dentro del texto consolidado de la
norma modificada. Por eso la cola es una consulta («¿ya hay filas de `version_norma` para esta
pareja?») y no un estado: una norma que hoy no tiene consolidado vuelve a intentarse mañana sin
que nadie tenga que acordarse. El coste de ese reintento está acotado por el tope y la pausa de
6.2, y las candidatas son pocas por definición — solo normas que tocan la watchlist, que en el
corpus medido son del orden de una entre cientos.

La contrapartida honesta: una norma cuya modificación **nunca** se consolide se reintenta cada
pasada, para siempre. Es una petición al día contra una fuente pública; la alternativa —marcarla
como agotada— haría que el sistema dejara de mirar justo lo que sí puede aparecer más tarde, que
es el modo de fallo que este proyecto no se permite.
"""

from __future__ import annotations

import datetime
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingest import boe_consolidado
from app.ingest.boe_consolidado import ConsolidadoError, NoConsolidado
from app.models.documento import Documento, EstadoPipeline, TipoDocumento
from app.models.norma import EstadoPrefiltro, Norma, VersionNorma
from app.pipeline import watchlist
from app.pipeline.watchlist import NormaVigilada
from app.security import hashing, url_guard, xml_safe
from app.security.url_guard import UrlGuardError
from app.security.xml_safe import XmlSafeError
from app.services.archivo import archivar
from app.services.cuerpo import leer_cuerpo

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResumenVersionado:
    """El embudo de esta etapa, con el mismo espíritu que `ResumenFase2`.

    `sin_consolidar` no se omite nunca aunque sea cero, y es la cifra que más se malinterpreta:
    significa "la fuente todavía no ha consolidado este cambio", que **no** es "esta norma no
    cambió nada". Sin ella, un resumen que diga "0 diffs" se lee como lo segundo.
    """

    candidatas: int
    consultadas: int
    con_diff: int
    filas: int
    sin_consolidar: int
    fallidas: int
    pendientes_restantes: int = 0
    # Cuántas versiones aportó cada norma vigilada. Es el desglose que dice si la watchlist está
    # viva o si siempre tira de la misma entrada, igual que `por_regla` en la clasificación.
    por_norma_afectada: dict[str, int] = field(default_factory=dict)


# Mismo conjunto que la cola del clasificador y por el mismo motivo: esta etapa está detrás del
# prefiltro y `descartada` significa fin. En la práctica todo lo que llega aquí es `relevante`
# —modificar una norma de la watchlist hace `relevante` a la norma por el eje referencial (7.3)—
# pero se escriben los dos estados explícitos para que un cambio futuro en el prefiltro no deje
# esta etapa mirando a un conjunto vacío sin que nadie lo note.
_COLA = (EstadoPrefiltro.RELEVANTE, EstadoPrefiltro.SOSPECHA)


def _cola(documento_id: int | None):  # type: ignore[no-untyped-def]
    consulta = select(Norma).where(
        Norma.documento_texto_id.is_not(None), Norma.prefiltro_estado.in_(_COLA)
    )
    if documento_id is not None:
        consulta = consulta.where(Norma.documento_id == documento_id)
    # Orden por `id` para que el tope por ejecución sea determinista, igual que en la fase 2.
    return consulta.order_by(Norma.id)


def _objetivos(
    norma: Norma, *, almacen_root: Path, lista: watchlist.Watchlist
) -> tuple[NormaVigilada, ...]:
    """Qué normas vigiladas toca esta norma, según su propio `<analisis>`.

    Se lee del cuerpo archivado y no de una columna porque el prefiltro guarda **qué ejes**
    dispararon, no qué normas tocó (7.2). Leer del almacén no cuesta red y mantiene esta etapa
    en el mismo régimen que el clasificador: se puede relanzar entera sin pedirle nada al BOE.

    `es_modificativa` es lo que separa «toca esta norma» de «la cita en el temario de una
    oposición», que es el falso positivo que el eje léxico produce a destajo. Una norma que solo
    la cite no tiene diff que traer.
    """
    cuerpo = leer_cuerpo(norma, almacen_root=almacen_root)
    if cuerpo is None:
        return ()
    objetivos: dict[str, NormaVigilada] = {}
    for referencia in cuerpo.referencias:
        if not referencia.es_modificativa:
            continue
        vigilada = lista.buscar(referencia.identificador)
        # `buscar` valida el formato y exige que esté en la watchlist. Lo que se guarda es la
        # entrada de la watchlist, **no la referencia**: a partir de aquí el identificador que
        # viaja es el nuestro, y el del documento no vuelve a usarse para nada (6.10).
        if vigilada is not None:
            objetivos.setdefault(vigilada.identificador, vigilada)
    return tuple(objetivos.values())


def _ya_versionada(session: Session, *, norma_id: int, afectada: str) -> bool:
    return (
        session.scalar(
            select(VersionNorma.id).where(
                VersionNorma.norma_id == norma_id, VersionNorma.norma_afectada == afectada
            )
        )
        is not None
    )


def _documento_consolidado(
    session: Session, *, fuente_id: int, identificador: str, digest: str, ruta: str
) -> Documento:
    """La fila de archivo del consolidado, creándola si hace falta.

    **El identificador lleva el hash del contenido**, y es la única fila de `documento` donde el
    identificador no es literalmente el que da la fuente. El motivo: el consolidado de una norma
    cambia cada vez que alguien la modifica, así que "BOE-A-2016-6728 consolidado" no nombra un
    documento sino una serie. Con el hash dentro, cada estado consolidado que hayamos visto es
    una fila distinta e inmutable —que es lo que pide 6.5— y volver a descargar el mismo estado
    reutiliza la fila en vez de duplicarla.
    """
    ident_archivo = f"{identificador}-consolidado-{digest[:12]}"
    existente = session.scalar(
        select(Documento).where(
            Documento.fuente_id == fuente_id,
            Documento.identificador_oficial == ident_archivo,
            Documento.tipo == TipoDocumento.CONSOLIDADO,
        )
    )
    if existente is not None:
        return existente
    documento = Documento(
        fuente_id=fuente_id,
        identificador_oficial=ident_archivo,
        # Cuándo lo vimos, no cuándo se publicó la norma: un consolidado no tiene fecha de
        # publicación propia, es un estado que la fuente mantiene. Confundirlas metería en
        # el archivo una fecha de publicación que nadie ha publicado (regla de oro 8).
        fecha_publicacion=datetime.date.today(),
        url_original=boe_consolidado.url_consolidado(identificador),
        sha256=digest,
        sello_tiempo=datetime.datetime.now(datetime.UTC),
        ruta_almacen=ruta,
        estado_pipeline=EstadoPipeline.INGERIDO,
        tipo=TipoDocumento.CONSOLIDADO,
    )
    session.add(documento)
    session.flush()
    return documento


def poblar(
    session: Session,
    *,
    almacen_root: Path,
    pausa: float,
    limite: int,
    documento_id: int | None = None,
    client: httpx.Client | None = None,
) -> ResumenVersionado:
    """Trae el texto anterior de lo que cada norma modificó y lo guarda como `version_norma`.

    Idempotente: la cola son las parejas (norma, norma vigilada) sin filas de versión, así que
    una segunda pasada sobre lo mismo no pide nada. `commit` por pareja, igual que la fase 2:
    una pasada larga que falle al final no puede tirar peticiones ya gastadas contra el BOE.
    """
    lista = watchlist.watchlist()
    normas = list(session.scalars(_cola(documento_id)))

    candidatas = consultadas = con_diff = filas = sin_consolidar = fallidas = 0
    por_afectada: dict[str, int] = {}
    pendientes = 0

    for norma in normas:
        for vigilada in _objetivos(norma, almacen_root=almacen_root, lista=lista):
            if _ya_versionada(session, norma_id=norma.id, afectada=vigilada.identificador):
                continue
            candidatas += 1
            if consultadas >= limite:
                # Tope por ejecución (6.2). Lo que no entra hoy sigue en cola y entra mañana:
                # la cola es una consulta, no un estado que haya que reponer.
                pendientes += 1
                continue

            if consultadas and pausa:
                time.sleep(pausa)
            consultadas += 1

            try:
                contenido = url_guard.fetch(
                    boe_consolidado.url_consolidado(vigilada.identificador),
                    headers=boe_consolidado.CABECERAS,
                    client=client,
                )
                raiz = xml_safe.parse(contenido)
                boe_consolidado.comprobar_respuesta(raiz)
            except NoConsolidado as exc:
                # No es un fallo: la fuente no consolida todo, y lo que consolida lo hace tarde.
                logger.info(
                    "Sin texto consolidado de %s (la modifica %s): %s. Se reintentará.",
                    vigilada.identificador,
                    norma.identificador_oficial,
                    exc,
                )
                sin_consolidar += 1
                continue
            except UrlGuardError as exc:
                logger.error(
                    "CONTROL DE SEGURIDAD al descargar el consolidado de %s: %s: %s",
                    vigilada.identificador,
                    type(exc).__name__,
                    exc,
                )
                fallidas += 1
                continue
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    # El mismo caso de arriba, contestado con el código HTTP en vez de con el
                    # bloque `<status>`. La fuente usa las dos formas y significan lo mismo.
                    logger.info(
                        "No hay consolidado publicado de %s (404). Se reintentará.",
                        vigilada.identificador,
                    )
                    sin_consolidar += 1
                    continue
                logger.warning(
                    "No se pudo descargar el consolidado de %s: %s", vigilada.identificador, exc
                )
                fallidas += 1
                continue
            except httpx.HTTPError as exc:
                logger.warning(
                    "No se pudo descargar el consolidado de %s: %s: %s",
                    vigilada.identificador,
                    type(exc).__name__,
                    exc,
                )
                fallidas += 1
                continue
            except (XmlSafeError, ConsolidadoError) as exc:
                logger.error(
                    "Consolidado de %s inservible: %s: %s",
                    vigilada.identificador,
                    type(exc).__name__,
                    exc,
                )
                fallidas += 1
                continue

            bloques = boe_consolidado.extraer_bloques(raiz)
            cambios = boe_consolidado.cambios_de(bloques, norma.identificador_oficial)
            if not cambios:
                # El consolidado existe pero todavía no incorpora esta modificación. Es el caso
                # normal los primeros días tras la publicación, y se cuenta con los otros "sin
                # consolidar" porque para quien lea el log significan exactamente lo mismo:
                # falta la mitad del hecho y hay que volver a mirar.
                logger.info(
                    "El consolidado de %s aún no recoge la modificación de %s. Se reintentará.",
                    vigilada.identificador,
                    norma.identificador_oficial,
                )
                sin_consolidar += 1
                continue

            # Se archiva **antes** de derivar nada: la evidencia primero, la conclusión después.
            # `archivar` escribe en una ruta derivada del hash (6.3), así que rearchivar el mismo
            # contenido es reescribir el mismo fichero con lo mismo — idempotente y barato.
            digest = hashing.sha256_hex(contenido)
            ruta = archivar(contenido, digest, almacen_root=almacen_root)
            documento = _documento_consolidado(
                session,
                fuente_id=norma.documento.fuente_id,
                identificador=vigilada.identificador,
                digest=digest,
                ruta=ruta,
            )

            for ordinal, cambio in enumerate(cambios, start=1):
                session.add(
                    VersionNorma(
                        norma_id=norma.id,
                        norma_afectada=vigilada.identificador,
                        bloque=cambio.bloque or None,
                        documento_consolidado_id=documento.id,
                        articulo=cambio.titulo or None,
                        texto_anterior=cambio.texto_anterior,
                        texto_nuevo=cambio.texto_nuevo,
                        fecha_vigencia=cambio.fecha_vigencia,
                        ordinal=ordinal,
                        version_derivacion=boe_consolidado.VERSION_CONSOLIDADO,
                        # `version_anterior_id` queda a NULL y no es un olvido: encadenaría
                        # versiones sucesivas del **mismo** bloque, y aquí cada fila es un
                        # bloque distinto tocado por la misma norma. El encadenamiento tendrá
                        # sentido el día que una segunda norma vuelva a tocar el mismo bloque.
                    )
                )
            session.commit()

            con_diff += 1
            filas += len(cambios)
            por_afectada[vigilada.identificador] = por_afectada.get(
                vigilada.identificador, 0
            ) + len(cambios)

    return ResumenVersionado(
        candidatas=candidatas,
        consultadas=consultadas,
        con_diff=con_diff,
        filas=filas,
        sin_consolidar=sin_consolidar,
        fallidas=fallidas,
        pendientes_restantes=pendientes,
        por_norma_afectada=por_afectada,
    )
