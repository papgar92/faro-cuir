"""Fase 2 de la ingesta: descarga y archiva el texto íntegro del día entero.

CLAUDE.md 7.1 y tarea 0.c. El **qué** lo decidió el ADR 0011 con números medidos —4,3 MB y
~10 s por día, 0 errores contra el BOE en 436 normas— y el **dónde** lo decidió el ADR 0015:
cada cuerpo es una fila más de `documento`, con `tipo='texto_norma'`, su `sha256` y su
`sello_tiempo`, y `norma.documento_texto_id` apunta a ella.

## Por qué se descarga todo y no solo lo que el prefiltro marca

Porque el título es lo que el redactor controla. Una norma que recorta un derecho puede
titularse «Orden por la que se modifican determinados aspectos organizativos», y sobre ese
título no hay vocabulario que valga. Descargar solo lo que el título delata convierte el
prefiltro en la puerta de entrada al sistema, y su falso negativo pasa a ser invisible: la
norma no aparece en ninguna métrica porque nadie llegó a mirarla nunca (7.1).

Con el día entero descargado, el prefiltro deja de decidir **qué se mira** y pasa a decidir
**qué entra en el LLM y en qué orden**. Un día de red cuesta 10 s; una extracción cuesta 133,9 s.
El caro es el modelo, y ahí es donde tiene sentido filtrar.

## Este módulo descarga y archiva. No evalúa.

La separación es del ADR 0015 y tiene una consecuencia práctica que justifica ella sola el
diseño: `services/prefiltro.py` lee el cuerpo **del almacén**, no de la red. Subir
`VERSION_VOCABULARIO` y relanzar `--reprefiltrar` reevalúa cientos de normas sin pedirle nada
al BOE. Si estuvieran acoplados, cada retoque del diccionario costaría otra descarga del día
entero, y el diccionario se retoca a menudo.
"""

from __future__ import annotations

import datetime
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.documento import Documento, EstadoPipeline, TipoDocumento
from app.models.norma import Norma
from app.security import hashing, url_guard
from app.security.url_guard import UrlGuardError
from app.services.archivo import archivar

logger = logging.getLogger(__name__)

# La API del BOE sirve el texto íntegro de cada disposición con la misma cabecera que el
# sumario. Verificado en la medición del ADR 0011 sobre 436 documentos reales.
_CABECERAS = {"Accept": "application/xml"}


@dataclass(frozen=True)
class ResumenFase2:
    """El embudo de la fase 2, con el mismo espíritu que `ResumenPrefiltro`.

    `pendientes_restantes` es la cifra que no se puede omitir: dice cuánto queda de cola
    después de aplicar el tope por ejecución. Sin ella, un resumen que diga "500 descargadas"
    se lee como "ya está" cuando puede quedar el triple esperando.
    """

    candidatas: int
    descargadas: int
    fallidas: int
    bytes_descargados: int
    pendientes_restantes: int


def _cola(documento_id: int | None, limite: int):  # type: ignore[no-untyped-def]
    """Normas cuyo cuerpo falta por archivar.

    **La cola es esta consulta y no un estado**, y es deliberado (ADR 0015): un estado nuevo
    habría que mantenerlo sincronizado con la realidad, y `documento_texto_id IS NULL` no puede
    desincronizarse de lo que describe — es literalmente "no hay cuerpo archivado".

    `url_texto IS NULL` se excluye aquí en vez de contarlo como fallo dentro del bucle: son
    ítems del sumario que no publican texto propio (una corrección de erratas que solo remite,
    típicamente). No es un error nuestro y no debe ensuciar el recuento de fallidas.

    Orden por `id` para que el tope por ejecución sea determinista: dos pasadas con la misma
    base de datos tienen que atacar la cola en el mismo orden, o "reejecutar no rehace trabajo"
    deja de ser comprobable.
    """
    consulta = select(Norma).where(
        Norma.documento_texto_id.is_(None),
        Norma.url_texto.is_not(None),
    )
    if documento_id is not None:
        consulta = consulta.where(Norma.documento_id == documento_id)
    return consulta.order_by(Norma.id).limit(limite)


def _contar_pendientes(session: Session, documento_id: int | None) -> int:
    consulta = select(Norma.id).where(
        Norma.documento_texto_id.is_(None),
        Norma.url_texto.is_not(None),
    )
    if documento_id is not None:
        consulta = consulta.where(Norma.documento_id == documento_id)
    return len(session.scalars(consulta).all())


def _documento_del_cuerpo(
    session: Session, *, fuente_id: int, identificador: str
) -> Documento | None:
    return session.scalar(
        select(Documento).where(
            Documento.fuente_id == fuente_id,
            Documento.identificador_oficial == identificador,
            Documento.tipo == TipoDocumento.TEXTO_NORMA,
        )
    )


def descargar(
    session: Session,
    *,
    almacen_root: Path,
    pausa: float,
    limite: int,
    documento_id: int | None = None,
    client: httpx.Client | None = None,
) -> ResumenFase2:
    """Descarga, archiva y enlaza el cuerpo de cada norma que aún no lo tenga.

    Idempotente por construcción: la cola son las normas sin `documento_texto_id`, así que una
    segunda pasada sobre lo mismo encuentra la cola vacía y no pide nada. Un fallo a mitad no
    obliga a repetir lo anterior — se hace `commit` por norma justamente para eso: con 250
    normas por día y una pausa entre cada una, una pasada dura minutos, y perder el trabajo de
    todas por un fallo en la última sería tirar tiempo y peticiones ya gastadas contra el BOE.
    """
    normas = list(session.scalars(_cola(documento_id, limite)))
    descargadas = fallidas = total_bytes = 0

    for indice, norma in enumerate(normas):
        # Cortesía con la fuente y freno propio (6.2). Va **antes** de cada petición salvo la
        # primera: dormir antes de empezar solo retrasaría el arranque sin proteger a nadie.
        if indice and pausa:
            time.sleep(pausa)

        try:
            # `url_texto` viene del sumario, no lo escribimos nosotros: pasa por `url_guard`
            # entero, allowlist incluida (ADR 0006). Es lo contrario de la excepción de
            # `llm/ollama.py`, que sí es una URL nuestra.
            contenido = url_guard.fetch(norma.url_texto or "", headers=_CABECERAS, client=client)
        except UrlGuardError as exc:
            logger.error(
                "CONTROL DE SEGURIDAD al descargar el cuerpo de %s: %s: %s",
                norma.identificador_oficial,
                type(exc).__name__,
                exc,
            )
            fallidas += 1
            continue
        except httpx.HTTPError as exc:
            # Fallo de red rutinario. No se marca nada en la fila: la norma sigue sin
            # `documento_texto_id`, así que vuelve a salir en la cola de la próxima pasada.
            # Esa es toda la lógica de reintento que hace falta.
            logger.warning(
                "No se pudo descargar el cuerpo de %s: %s: %s",
                norma.identificador_oficial,
                type(exc).__name__,
                exc,
            )
            fallidas += 1
            continue

        digest = hashing.sha256_hex(contenido)
        ruta_relativa = archivar(contenido, digest, almacen_root=almacen_root)

        sumario = norma.documento
        documento = _documento_del_cuerpo(
            session, fuente_id=sumario.fuente_id, identificador=norma.identificador_oficial
        )
        if documento is None:
            documento = Documento(
                fuente_id=sumario.fuente_id,
                identificador_oficial=norma.identificador_oficial,
                # La del sumario del que salió: es la fecha en que se publicó, y es un hecho
                # de la fuente. La fecha en que lo vimos nosotros es `sello_tiempo`, y son dos
                # cosas distintas que la 6.5 necesita por separado.
                fecha_publicacion=sumario.fecha_publicacion,
                url_original=norma.url_texto or "",
                sha256=digest,
                sello_tiempo=datetime.datetime.now(datetime.UTC),
                ruta_almacen=ruta_relativa,
                # El estado del pipeline lo lleva la `norma`, no su cuerpo (ADR 0015).
                # Duplicarlo aquí crearía dos verdades sobre lo mismo.
                estado_pipeline=EstadoPipeline.INGERIDO,
                tipo=TipoDocumento.TEXTO_NORMA,
            )
            session.add(documento)
            try:
                session.flush()
            except IntegrityError:
                # Dos pasadas solapadas pueden cruzar las dos el SELECT de arriba. La
                # restricción única de la tabla es la que decide; aquí solo se recoge quién
                # ganó. Mismo criterio que `services/ingesta.py`.
                session.rollback()
                documento = _documento_del_cuerpo(
                    session,
                    fuente_id=sumario.fuente_id,
                    identificador=norma.identificador_oficial,
                )
                if documento is None:
                    raise
                norma = session.get(Norma, norma.id) or norma

        norma.documento_texto_id = documento.id
        # Un commit por norma: una pasada del día entero dura minutos y perder lo ya
        # descargado por un fallo tardío significa volver a pedírselo al BOE.
        session.commit()

        descargadas += 1
        total_bytes += len(contenido)

    return ResumenFase2(
        candidatas=len(normas),
        descargadas=descargadas,
        fallidas=fallidas,
        bytes_descargados=total_bytes,
        pendientes_restantes=_contar_pendientes(session, documento_id),
    )
