"""Etapa 2 del pipeline: descarga el texto de las normas relevantes y extrae hechos (CLAUDE.md
sección 7 y ADR 0009).

Separado de `llm/provider.py` con el mismo criterio que `services/prefiltro.py` frente a
`pipeline/prefiltro.py`: allí vive el contrato (cómo se valida una extracción), aquí vive lo
que hace falta para llegar a poder llamarlo — descargar el texto de la norma y persistir el
resultado — y que por eso sí necesita sesión de base de datos y red.

El texto de cada norma es dato no confiable de una fuente externa (regla de oro 1), igual que
el sumario: la descarga pasa por `security/url_guard` y el parseo por `security/xml_safe`, sin
excepción. A diferencia de `llm/ollama.py`, aquí sí aplica `url_guard` entero — la URL no la
escribimos nosotros, la propone el sumario (ADR 0006).

Sobre qué se persiste y qué no: ver ADR 0009. En corto, `deteccion.clasificacion` no puede
quedar NULL (restricción de la base de datos) y el clasificador por reglas (etapa 3) todavía no
existe, así que esta etapa inserta con `INDETERMINADO`/`HEURISTICA`/`regla_aplicada=None` — un
valor centinela que no sale de nada que haya dicho el LLM, para no romper el ADR 0004.
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from xml.etree.ElementTree import Element

import httpx
from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.llm.provider import LLMError, ProveedorLLM, extraer
from app.models.deteccion import Clasificacion, Deteccion, OrigenClasificacion
from app.models.norma import EstadoPrefiltro, Norma
from app.security import url_guard, xml_safe
from app.security.url_guard import UrlGuardError
from app.security.xml_safe import XmlSafeError

logger = logging.getLogger(__name__)

# Tope de caracteres del documento que se envían al LLM. No es un control de seguridad —
# `url_guard` y `xml_safe` ya acotan lo que se descarga y se parsea (20 MB cada uno)— es
# pragmatismo de modelo, y el número sale de haberlo probado de verdad contra la Ley 4/2023
# real (`BOE-A-2023-5366`) en la máquina del proyecto (CPU, sin GPU dedicada, ADR 0008):
# 40.000 caracteres devolvía un JSON con un campo `error` en vez del esquema esperado (el
# modelo se pierde con tanto contexto), y 8.000 agotaba el timeout de 180 s de puro lento.
# 3.000 sí funcionó de punta a punta. Se deja un margen sobre esa cifra verificada, no una
# suposición redonda. **Esto es un parámetro de rendimiento, no de calidad**: seguirá sin
# saber si el modelo entiende bien un artículo largo cortado a la mitad hasta que el gold set
# lo mida (CLAUDE.md sección 11); subir esta cifra requiere o un modelo más grande o más
# tiempo de timeout, ambos fuera del alcance de esta tarea.
MAX_CARACTERES_DOCUMENTO = 4_000

# Cabecera que exige la API del BOE también para el texto íntegro de cada disposición, igual
# que para el sumario (`ingest/boe.py`). No verificado contra este endpoint en concreto, pero
# es la misma familia de API y no tiene coste enviarla de más.
_CABECERAS = {"Accept": "application/xml"}


@dataclass(frozen=True)
class ResumenExtraccion:
    """El embudo de esta etapa, con el mismo espíritu que `ResumenPrefiltro`."""

    evaluadas: int
    extraidas: int
    fallidas: int


def _texto_plano(raiz: Element) -> str:
    """Extrae el cuerpo real de la norma, sin el ruido de sus metadatos.

    Verificado contra un documento real de texto íntegro del BOE (`BOE-A-2023-5366`, no
    deducido de documentación): la estructura es `documento > metadatos, metadata-eli,
    analisis, texto`. `analisis` trae referencias a normas relacionadas (a qué modifica, quién
    la modificó después) en decenas de etiquetas `<texto>` cortas propias; concatenar el árbol
    entero sin distinguirlas agota el presupuesto de caracteres en ese ruido antes de llegar
    al articulado real, que vive entero en el único `<texto>` de primer nivel.

    Si ese elemento no existe —una fuente distinta del BOE, o un tipo de documento con otra
    forma que todavía no se ha comprobado— se cae al árbol completo: no es ideal, pero es
    mejor que no enviar nada, y no inventa una estructura que no se ha verificado para ese
    caso (regla de oro 8).
    """
    cuerpo = raiz.find("./texto")
    objetivo = cuerpo if cuerpo is not None else raiz
    fragmentos = (fragmento.strip() for fragmento in objetivo.itertext())
    return " ".join(f for f in fragmentos if f)


def _recortar(texto: str, *, identificador: str) -> str:
    """Aplica el tope de caracteres, dejando constancia si se ha cortado algo.

    Un recorte silencioso es peor que uno registrado: si el extractor empieza a fallar en
    normas largas, esto es lo primero que hay que poder mirar.
    """
    if len(texto) <= MAX_CARACTERES_DOCUMENTO:
        return texto
    logger.warning(
        "Documento de %s recortado de %s a %s caracteres antes de enviarlo al LLM.",
        identificador,
        len(texto),
        MAX_CARACTERES_DOCUMENTO,
    )
    return texto[:MAX_CARACTERES_DOCUMENTO]


# Estados que entran en la cola del LLM, **y el orden en que entran** (CLAUDE.md 7.2).
# `RELEVANTE` primero, `SOSPECHA` después: las dos se extraen, pero una extracción cuesta
# 133,9 s y si la pasada se corta a medias hay que haber gastado ese tiempo en lo más probable.
_COLA = (EstadoPrefiltro.RELEVANTE, EstadoPrefiltro.SOSPECHA)


def _pendientes(documento_id: int | None):  # type: ignore[no-untyped-def]
    """Normas en cola de extracción que aún no tienen ninguna `deteccion`.

    **Antes esto era `== RELEVANTE`, y con el estado `sospecha` (7.2) eso pasó a ser un
    filtro que pierde datos en silencio.** Una norma marcada como sospecha es una que el
    prefiltro no ha sabido descartar; dejarla fuera de la cola equivale a descartarla, solo
    que sin decirlo y sin que aparezca en ningún recuento. Es exactamente el falso negativo
    que el proyecto no se puede permitir.

    El orden no es cosmético: `RELEVANTE` antes que `SOSPECHA`. La extracción cuesta 133,9 s
    por norma (ADR 0011), así que una pasada interrumpida tiene que haber gastado el tiempo en
    lo más probable primero.

    No distingue "nunca se intentó" de "se intentó y falló": una extracción fallida (LLMError,
    fallo de red, control de seguridad) no deja fila, así que la norma vuelve a aparecer aquí
    en la siguiente pasada. Mismo criterio de idempotencia que el resto del pipeline.
    """
    consulta = (
        select(Norma)
        .outerjoin(Deteccion, Deteccion.norma_id == Norma.id)
        .where(Norma.prefiltro_estado.in_(_COLA), Deteccion.id.is_(None))
    )
    if documento_id is not None:
        consulta = consulta.where(Norma.documento_id == documento_id)
    # `case` y no un ORDER BY sobre el texto del estado: alfabéticamente "sospecha" va antes
    # que "relevante", que es justo al revés de lo que hace falta.
    return consulta.order_by(
        case({estado: indice for indice, estado in enumerate(_COLA)}, value=Norma.prefiltro_estado),
        Norma.id,
    )


def aplicar(
    session: Session,
    proveedor: ProveedorLLM,
    *,
    documento_id: int | None = None,
    client: httpx.Client | None = None,
) -> ResumenExtraccion:
    """Extrae y persiste. Idempotente: una norma con `deteccion` no se vuelve a tocar.

    `documento_id=None` barre toda la tabla; el worker normal lo llama acotado al documento
    que acaba de ingerir, igual que hace con el prefiltro.
    """
    normas = list(session.scalars(_pendientes(documento_id)))
    extraidas = fallidas = 0

    for norma in normas:
        if not norma.url_texto:
            logger.warning(
                "Norma %s sin url_texto en el sumario; no se puede extraer.",
                norma.identificador_oficial,
            )
            fallidas += 1
            continue

        try:
            contenido = url_guard.fetch(norma.url_texto, headers=_CABECERAS, client=client)
            raiz = xml_safe.parse(contenido)
            texto = _recortar(_texto_plano(raiz), identificador=norma.identificador_oficial)
            resultado = extraer(proveedor, texto)
        except (UrlGuardError, XmlSafeError) as exc:
            # Mismo criterio que `worker/run.py` con la ingesta: un control de seguridad que
            # salta no es un fallo de red cualquiera, y no debe perderse entre ellos.
            logger.error(
                "CONTROL DE SEGURIDAD al extraer %s: %s: %s",
                norma.identificador_oficial,
                type(exc).__name__,
                exc,
            )
            fallidas += 1
            continue
        except LLMError as exc:
            logger.warning("Extracción descartada para %s: %s", norma.identificador_oficial, exc)
            fallidas += 1
            continue

        # Ver ADR 0009: valor centinela, no un veredicto. `version_prompt` y `modelo` viajan
        # dentro del propio JSON porque `deteccion` no tiene columnas dedicadas para ellos —
        # mismo motivo que el prefiltro guarda su versión junto al resultado.
        deteccion = Deteccion(
            norma_id=norma.id,
            extraccion_json={
                "extraccion": resultado.extraccion.model_dump(mode="json"),
                "version_prompt": resultado.version_prompt,
                "modelo": resultado.modelo,
                "extraido_en": datetime.datetime.now(datetime.UTC).isoformat(),
            },
            clasificacion=Clasificacion.INDETERMINADO,
            origen=OrigenClasificacion.HEURISTICA,
            regla_aplicada=None,
        )
        session.add(deteccion)
        extraidas += 1

    session.commit()

    return ResumenExtraccion(evaluadas=len(normas), extraidas=extraidas, fallidas=fallidas)
