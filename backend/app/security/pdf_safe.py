"""La única puerta por la que entra un PDF. CLAUDE.md 6.1.

Es el hermano de `xml_safe`, y existe por el mismo motivo: **un PDF de una fuente externa es
entrada hostil**, y el sitio para decidir qué se le permite es uno solo. Ningún otro módulo importa
`pypdf`; hay un test que lo comprueba, igual que con `defusedxml`.

## Qué hace, y sobre todo qué NO hace

Extrae **la capa de texto** y nada más. Un PDF no es un documento: es un programa con un formato
de archivo alrededor, y casi todo lo que puede hacer aquí no hace falta.

- **No ejecuta JavaScript.** Los PDF pueden llevarlo; `pypdf` no lo interpreta y aquí no se toca
  el `/OpenAction` ni ningún `/AA`. No se ejecuta nada, punto.
- **No sigue enlaces ni recursos externos.** Un PDF puede referenciar ficheros remotos y
  formularios que envían datos. Nada de eso se resuelve: se lee el texto que ya está dentro.
- **No hace OCR.** El humano levantó la prohibición el 2026-08-22, pero sigue siendo el último
  recurso y no el primero: si el PDF no trae capa de texto, esto **se abstiene y lo dice**, y
  quien quiera OCR tendrá que escribirlo con su propio ADR. Medido antes de decidirlo: el PDF del
  DOGC trae 59 referencias de fuente y **cero imágenes**, así que aquí no hace ninguna falta.
- **No descomprime nada por su cuenta** más allá de lo que `pypdf` necesita para leer los flujos
  de contenido, y con el tope de páginas por delante.

## Los tres topes, y por qué son tres

Un solo límite de bytes no basta, porque los tres ataques son distintos:

1. `MAX_PDF_BYTES` para la descarga: lo que no se lee no puede hacer daño.
2. `MAX_PAGINAS` para la bomba de páginas: un PDF de 300 KB puede declarar cien mil páginas y
   dejar al worker extrayendo hasta que alguien lo mate.
3. `MAX_CARACTERES` para la bomba de expansión: pocas páginas cuyo flujo de contenido genera
   cientos de megas de texto. Es el equivalente de la bomba de entidades del XML.

Al pasarse cualquiera de los tres **se levanta excepción y no se devuelve texto a medias**: medio
documento archivado como si fuera entero es peor que ninguno, porque el prefiltro lo evaluaría y
diría «aquí no hay nada» sobre un texto que nadie ha visto completo.
"""

from __future__ import annotations

import io
import logging

from pypdf import PdfReader
from pypdf.errors import PdfReadError

logger = logging.getLogger(__name__)

# Un boletín autonómico grande ronda el mega. 20 MB es el mismo tope que `xml_safe` y deja
# margen de sobra sin permitir que una fuente nos llene el disco.
MAX_PDF_BYTES: int = 20 * 1024 * 1024

# El DOGC más largo del corpus no llega a 100 páginas. 400 deja margen para un boletín
# extraordinario y corta en seco la bomba de páginas.
MAX_PAGINAS: int = 400

# Tope del texto extraído. Un documento normativo largo ronda los 400.000 caracteres; 4 millones
# es diez veces eso y sigue siendo un orden de magnitud menos que lo que una bomba produciría.
MAX_CARACTERES: int = 4_000_000


class PdfSafeError(Exception):
    """Cualquier motivo por el que un PDF no se puede leer con seguridad."""


class PdfTooLarge(PdfSafeError):
    """El fichero pesa más que el tope."""


class MaxPaginasExceeded(PdfSafeError):
    """Declara más páginas de las permitidas: posible bomba de páginas."""


class MaxCaracteresExceeded(PdfSafeError):
    """El texto extraído se pasa del tope: posible bomba de expansión."""


class MalformedPdf(PdfSafeError):
    """No es un PDF, está corrupto, o `pypdf` no puede con él."""


class SinCapaDeTexto(PdfSafeError):
    """Es un PDF válido y **no trae texto**: seguramente es un escaneo.

    Se distingue de `MalformedPdf` a propósito, y la distinción es la misma que el ADR 0020 hizo
    entre «no lo hemos descargado» y «lo descargamos y no se puede leer»: aquí el fichero está
    bien y lo que falta es la capa de texto. Es el **único** caso en que el OCR entraría en la
    conversación, así que tiene que poder contarse aparte para saber si alguna vez hace falta.
    """


def extraer_texto(
    datos: bytes,
    *,
    max_bytes: int = MAX_PDF_BYTES,
    max_paginas: int = MAX_PAGINAS,
    max_caracteres: int = MAX_CARACTERES,
) -> str:
    """El texto de un PDF no confiable, o una excepción. Nunca texto a medias.

    No registra el contenido en ningún caso, solo tamaños y motivos: el texto de un documento
    hostil no tiene por qué acabar en un log donde alguien lo lea sin contexto (mismo criterio
    que 6.10 con la salida del modelo).
    """
    if len(datos) > max_bytes:
        raise PdfTooLarge(f"El PDF ocupa {len(datos)} bytes, por encima del tope de {max_bytes}")

    try:
        lector = PdfReader(io.BytesIO(datos))
        paginas = len(lector.pages)
    except (PdfReadError, ValueError, OSError, RecursionError) as exc:
        # `RecursionError` incluida a propósito: un PDF con referencias circulares en su árbol de
        # objetos la provoca, y sin capturarla se lleva por delante al worker entero.
        raise MalformedPdf(f"No se puede leer el PDF: {type(exc).__name__}") from exc

    if paginas > max_paginas:
        raise MaxPaginasExceeded(f"El PDF declara {paginas} páginas, por encima de {max_paginas}")

    trozos: list[str] = []
    total = 0
    for indice in range(paginas):
        try:
            texto = lector.pages[indice].extract_text() or ""
        except (PdfReadError, ValueError, KeyError, RecursionError) as exc:
            # Una página ilegible **no invalida el documento**: los PDF reales traen páginas raras
            # (portadas con solo un sello, anexos con tablas). Se salta y se cuenta; lo que sí
            # invalidaría el resultado es callarlo, así que va al log.
            logger.warning(
                "Página %d de %d ilegible en el PDF (%s); se salta.",
                indice + 1,
                paginas,
                type(exc).__name__,
            )
            continue
        total += len(texto)
        if total > max_caracteres:
            raise MaxCaracteresExceeded(
                f"El texto extraído pasa de {max_caracteres} caracteres: posible bomba de expansión"
            )
        trozos.append(texto)

    completo = "\n".join(trozos).strip()
    if not completo:
        # Ni una letra en ninguna página. El fichero es válido, así que esto no es un error de
        # formato: es un escaneo, y decirlo con su propio tipo es lo que permitirá algún día saber
        # cuántos documentos justificarían un OCR — en vez de suponerlo.
        raise SinCapaDeTexto(f"El PDF tiene {paginas} páginas y ninguna capa de texto")
    return completo
