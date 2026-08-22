"""Recupera por PDF las normas cuyo cuerpo archivado el pipeline no puede leer. ADR 0026.

## Qué problema resuelve

El DOGC publica muchas normas **solo en PDF**. Su endpoint `/dof/spa/xml` devuelve para esas la
página de error del portal, así que se archivaba un HTML de error con nombre `.xml` y el prefiltro
lo marcaba `ilegible` (ADR 0020). Al 2026-08-22 eran **228 normas**, y esa cifra crecía con cada
día ingerido.

Lo que faltaba **no era OCR**. Medido antes de escribir una línea: un PDF del DOGC trae 59
referencias de fuente, 18 bloques de texto y **cero imágenes**, y su capa de texto da 8.295
caracteres limpios de un fichero de 795 KB. Estaba ahí; nadie había mirado.

## Por qué es una pasada aparte y no un `try/except` en la descarga

Tres razones, y la tercera es la que decide:

1. **`texto_integro.descargar` no parsea.** Archiva bytes y sigue; quien descubre que algo es
   ilegible es el prefiltro, mucho después. Meter aquí la detección obligaría a parsear en la
   descarga y a duplicar la lógica de `cuerpo`.
2. **Hay 228 ya archivadas.** Un arreglo en la ingesta solo serviría para lo que entre a partir de
   ahora, y el problema es sobre todo el pasado.
3. **El archivo es inmutable** (6.5). Esto **no sustituye** el documento anterior: archiva el PDF
   como un documento nuevo, con su propia huella y su propio sello, y reapunta la norma. Lo que
   se descargó aquel día sigue estando y sigue pudiendo demostrarse — incluso siendo una página
   de error, que es un hecho sobre la fuente y merece conservarse.

## Lo que NO hace

No inventa la URL del PDF a partir de nada nuestro: la deriva de `url_texto`, que vino del sumario
oficial, y la vuelve a pasar entera por `url_guard` (6.2). Y si el PDF resulta no tener capa de
texto, **se abstiene y lo cuenta aparte** (`sin_texto`): ese es el único caso que algún día
justificaría un OCR, y para saber si merece la pena hay que poder contarlo, no suponerlo.
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
from app.models.norma import EstadoPrefiltro, Norma
from app.security import hashing, pdf_safe, url_guard
from app.security.pdf_safe import PdfSafeError, SinCapaDeTexto
from app.security.url_guard import UrlGuardError
from app.services.archivo import archivar

logger = logging.getLogger(__name__)

_CABECERAS = {"Accept": "application/pdf", "User-Agent": "FaroCuir/1.0 (vigilancia normativa)"}


@dataclass(frozen=True)
class ResumenRecuperacion:
    """Qué se recuperó y qué no. `sin_texto` no se omite nunca aunque sea cero.

    Es la cifra que decide si el OCR llegará a hacer falta algún día. Mientras sea cero, no hace
    falta; el día que no lo sea, hay un número que enseñar en su ADR en vez de una intuición.
    """

    intentadas: int
    recuperadas: int
    sin_texto: int
    fallidas: int


def _url_pdf(url_texto: str) -> str | None:
    """La URL del PDF a partir de la del XML.

    Solo para el patrón del DOGC (`.../dof/spa/xml` → `.../dof/spa/pdf`). Devuelve `None` para
    cualquier otra cosa **en vez de intentar algo genérico**: construir URLs a base de suponer es
    la forma de acabar pidiéndole a una fuente rutas que no existen, y cada fuente nueva debe
    declarar su patrón aquí a conciencia.
    """
    if url_texto.endswith("/dof/spa/xml"):
        return url_texto[: -len("xml")] + "pdf"
    return None


def recuperar(
    session: Session,
    *,
    almacen_root: Path,
    pausa: float,
    limite: int,
    client: httpx.Client | None = None,
) -> ResumenRecuperacion:
    """Reintenta por PDF las normas marcadas `ilegible`.

    Idempotente: al recuperar una norma, su estado deja de ser `ilegible`, así que la siguiente
    pasada ya no la ve. Lo que falla se queda como está y vuelve a salir — misma lógica de
    reintento que el resto del worker, sin banderas ni contadores de intentos.
    """
    normas = list(
        session.scalars(
            select(Norma)
            .where(Norma.prefiltro_estado == EstadoPrefiltro.ILEGIBLE)
            .where(Norma.url_texto.is_not(None))
            .order_by(Norma.id)
            .limit(limite)
        )
    )
    intentadas = recuperadas = sin_texto = fallidas = 0

    for indice, norma in enumerate(normas):
        url = _url_pdf(norma.url_texto or "")
        if url is None:
            # No sabemos derivar el PDF de esta fuente. No es un fallo suyo ni nuestro: es que
            # esta ruta todavía no cubre ese boletín. No se cuenta como intento.
            continue

        intentadas += 1
        if indice and pausa:
            time.sleep(pausa)

        try:
            contenido = url_guard.fetch(url, headers=_CABECERAS, client=client)
        except UrlGuardError as exc:
            logger.error(
                "CONTROL DE SEGURIDAD al recuperar el PDF de %s: %s: %s",
                norma.identificador_oficial,
                type(exc).__name__,
                exc,
            )
            fallidas += 1
            continue
        except httpx.HTTPError as exc:
            logger.warning(
                "No se pudo descargar el PDF de %s: %s: %s",
                norma.identificador_oficial,
                type(exc).__name__,
                exc,
            )
            fallidas += 1
            continue

        # Se extrae ANTES de archivar: archivar un PDF que después no se puede leer dejaría a la
        # norma apuntando a un cuerpo tan ilegible como el anterior, con el trabajo hecho dos
        # veces y la cifra de recuperadas mintiendo.
        try:
            pdf_safe.extraer_texto(contenido)
        except SinCapaDeTexto:
            # El caso del OCR. Se cuenta aparte y **la norma se deja como está**: sigue
            # `ilegible`, que es la verdad.
            logger.info(
                "El PDF de %s no tiene capa de texto: sería el caso de un OCR.",
                norma.identificador_oficial,
            )
            sin_texto += 1
            continue
        except PdfSafeError as exc:
            logger.warning(
                "El PDF de %s no se puede leer: %s: %s",
                norma.identificador_oficial,
                type(exc).__name__,
                exc,
            )
            fallidas += 1
            continue

        digest = hashing.sha256_hex(contenido)
        ruta = archivar(contenido, digest, almacen_root=almacen_root)
        sumario = norma.documento

        documento = Documento(
            fuente_id=sumario.fuente_id,
            # Sufijo en el identificador para no chocar con el documento anterior, que **sigue
            # existiendo**: son dos descargas distintas de la misma norma en formatos distintos, y
            # el archivo conserva las dos (6.5).
            identificador_oficial=f"{norma.identificador_oficial}#pdf",
            fecha_publicacion=sumario.fecha_publicacion,
            url_original=url,
            sha256=digest,
            sello_tiempo=datetime.datetime.now(datetime.UTC),
            ruta_almacen=ruta,
            estado_pipeline=EstadoPipeline.INGERIDO,
            tipo=TipoDocumento.TEXTO_NORMA,
        )
        session.add(documento)
        try:
            session.flush()
        except IntegrityError:
            session.rollback()
            logger.warning(
                "Ya existía el cuerpo en PDF de %s; se deja el que hay.",
                norma.identificador_oficial,
            )
            fallidas += 1
            continue

        norma.documento_texto_id = documento.id
        # Vuelve a la cola del prefiltro. `None` en la versión del texto es lo que hace que la
        # próxima pasada la reevalúe — el mismo mecanismo que el ADR 0020 usa para que una norma
        # ilegible se recupere sola en cuanto su cuerpo pase a ser legible.
        norma.prefiltro_estado = EstadoPrefiltro.PENDIENTE
        norma.prefiltro_version_texto = None
        session.commit()
        recuperadas += 1

    return ResumenRecuperacion(
        intentadas=intentadas, recuperadas=recuperadas, sin_texto=sin_texto, fallidas=fallidas
    )
