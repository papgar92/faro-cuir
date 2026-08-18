"""Etapa 3 del pipeline: extrae hechos del texto ya archivado (CLAUDE.md sección 7, ADR 0009).

Separado de `llm/provider.py` con el mismo criterio que `services/prefiltro.py` frente a
`pipeline/prefiltro.py`: allí vive el contrato (cómo se valida una extracción), aquí vive lo
que hace falta para llegar a poder llamarlo — leer el texto de la norma y persistir el
resultado — y que por eso sí necesita sesión de base de datos.

**Este módulo ya no toca la red, y es un cambio del ADR 0015.** Antes descargaba el cuerpo de
cada norma él mismo; ahora lo lee del almacén, donde lo dejó la fase 2 (`services/texto_integro`).
Tres consecuencias, y las tres son mejoras:

- El mismo byte no se descarga dos veces. Antes la fase 2 y el extractor pedían al BOE lo
  mismo, con dos sellos de tiempo distintos para un solo hecho.
- El LLM ve **exactamente el texto archivado**, no una segunda descarga que podría diferir. Es
  la precondición de 7.5: si la evidencia se cita contra el archivado, hay que haber extraído
  del archivado.
- Desaparece una salida HTTP del proyecto. Quedan dos: `ingest/boe.py` y la fase 2, las dos por
  `url_guard`.

El texto sigue siendo dato no confiable de una fuente externa (regla de oro 1): el parseo pasa
por `security/xml_safe` sin excepción, aunque venga de nuestro propio disco — archivarlo no lo
convierte en confiable, solo lo hace reproducible.

Sobre qué se persiste y qué no: ver ADR 0009. En corto, `deteccion.clasificacion` no puede
quedar NULL (restricción de la base de datos), así que esta etapa inserta con
`INDETERMINADO`/`HEURISTICA`/`regla_aplicada=None` — un valor centinela que no sale de nada que
haya dicho el LLM, para no romper el ADR 0004.

El centinela **sigue siendo lo correcto aunque el catálogo de reglas ya exista**
(`services/clasificacion.py`, ADR 0016): esta etapa no clasifica y no debe. Quien pisa esas
tres columnas es el catálogo, leyendo el texto archivado, y por eso las detecciones que ha
tocado se distinguen de las que no por `origen='derivado_diff'` y `regla_aplicada IS NOT NULL`.
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.llm.provider import LLMError, ProveedorLLM, extraer
from app.models.deteccion import Clasificacion, Deteccion, OrigenClasificacion
from app.models.norma import EstadoPrefiltro, Norma
from app.pipeline.anclaje import VERSION_ANCLAJE, anclar
from app.pipeline.texto import VERSION_TEXTO_PLANO
from app.services.cuerpo import leer_cuerpo

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


@dataclass(frozen=True)
class ResumenExtraccion:
    """El embudo de esta etapa, con el mismo espíritu que `ResumenPrefiltro`."""

    evaluadas: int
    extraidas: int
    fallidas: int
    # Artículos que el modelo citó **sin texto por ninguno de los dos lados** (ADR 0016). Antes
    # de ese ADR, uno solo de estos tumbaba la extracción entera; ahora se conservan como
    # punteros inertes y se cuentan, porque lo que no se cuenta no se afina. Un documento con
    # muchos punteros es la señal barata de que ahí hay supresiones que el catálogo de reglas
    # tiene que ir a corroborar contra el texto archivado.
    punteros: int = 0


def _anclar_extraccion(
    extraccion: object, texto: str, *, identificador: str, desplazamiento: int = 0
) -> list[dict[str, object]] | None:
    """Ancla al archivo cada texto que la extracción afirma haber leído. Regla de oro 9.

    Devuelve una lista de anclas —una por texto citado, en el orden en que aparecen los
    artículos— o `None` si **alguna** cita no está en el documento. `None` significa descartar la
    extracción entera, y esa severidad es deliberada: si el modelo se ha inventado una redacción,
    lo que ha escrito en los demás campos tampoco merece crédito. Sigue la misma vía que un fallo
    de esquema (6.9.3): no se crea fila, así que la norma vuelve sola a la cola.

    Un **puntero** (artículo citado sin texto por ninguno de los dos lados, ADR 0016) no ancla
    nada y no invalida nada: no hay cita que verificar, y por eso mismo no acciona nada por sí
    solo (regla de oro 10).

    Se registra **qué campo** falla, nunca lo que dijo el modelo: si el documento fue manipulado
    para que emitiera un veredicto, ese texto no puede acabar en un log donde alguien lo lea como
    conclusión del sistema (6.10).
    """
    anclas: list[dict[str, object]] = []
    for indice, articulo in enumerate(extraccion.articulos):  # type: ignore[attr-defined]
        for campo in ("texto_anterior", "texto_nuevo"):
            afirmado = getattr(articulo, campo)
            if afirmado is None:
                continue
            ancla = anclar(texto, afirmado, desplazamiento=desplazamiento)
            if ancla is None:
                logger.warning(
                    "Extracción de %s descartada: el campo %s del artículo %s afirma un texto "
                    "que no está en el documento archivado (regla de oro 9).",
                    identificador,
                    campo,
                    indice,
                )
                return None
            anclas.append(
                {
                    "articulo": indice,
                    "campo": campo,
                    "inicio": ancla.inicio,
                    "fin": ancla.fin,
                    # El recorte del ARCHIVO, no lo que devolvió el modelo. Es lo que se enseña.
                    "fragmento": ancla.fragmento,
                }
            )
    return anclas


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
        .where(
            Norma.prefiltro_estado.in_(_COLA),
            Deteccion.id.is_(None),
            # Sin cuerpo archivado no hay nada que extraer (ADR 0015). Se filtra aquí y no con
            # un `continue` dentro del bucle para que el recuento de `evaluadas` signifique
            # "normas que se podían extraer" y no "normas que se miraron y se descartaron":
            # un embudo cuyo primer escalón cuenta trabajo imposible no dice nada.
            Norma.documento_texto_id.is_not(None),
        )
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
    almacen_root: Path,
    documento_id: int | None = None,
) -> ResumenExtraccion:
    """Extrae y persiste. Idempotente: una norma con `deteccion` no se vuelve a tocar.

    `documento_id=None` barre toda la tabla; el worker normal lo llama acotado al documento
    que acaba de ingerir, igual que hace con el prefiltro.

    Ya no acepta un `httpx.Client`: este servicio no hace peticiones desde el ADR 0015. Ese
    parámetro solo lo usaban los tests, y era además un agujero en la puerta única —
    `url_guard.fetch` devuelve el cliente que le pasen tal cual, así que un llamante podía
    colar un cliente sin timeout o sin verificación de TLS a través del control.
    """
    normas = list(session.scalars(_pendientes(documento_id)))
    extraidas = fallidas = punteros = 0

    for norma in normas:
        # `leer_cuerpo` ya registra el motivo, y distingue el control de seguridad que salta
        # (mismo criterio que `worker/run.py` con la ingesta) del fichero que falta en el
        # almacén. Aquí las dos cosas cuentan igual: no hay extracción.
        cuerpo = leer_cuerpo(norma, almacen_root=almacen_root)
        if cuerpo is None:
            fallidas += 1
            continue
        texto = _recortar(cuerpo.texto, identificador=norma.identificador_oficial)
        try:
            resultado = extraer(proveedor, texto)
        except LLMError as exc:
            logger.warning("Extracción descartada para %s: %s", norma.identificador_oficial, exc)
            fallidas += 1
            continue

        # Ver ADR 0009: valor centinela, no un veredicto. `version_prompt` y `modelo` viajan
        # dentro del propio JSON porque `deteccion` no tiene columnas dedicadas para ellos —
        # mismo motivo que el prefiltro guarda su versión junto al resultado.
        del_documento = len(resultado.extraccion.punteros)
        if del_documento:
            # Se registran **cuántos** y no cuáles: el identificador lo escribe el modelo sobre
            # un texto que no controlamos, y un log es justo donde alguien lo leería como
            # conclusión del sistema (6.10). Cuáles son se guarda en la fila, que es donde se
            # puede contrastar contra el archivo.
            logger.info(
                "%s cita %s precepto(s) sin reproducir su texto: punteros a corroborar contra "
                "el archivo (ADR 0016).",
                norma.identificador_oficial,
                del_documento,
            )
        punteros += del_documento

        # Regla de oro 9: lo que no se puede señalar en el archivo no se guarda. Va **antes** de
        # crear la fila, no después: una detección que existe y luego se corrige es una que
        # alguien pudo leer mientras tanto.
        anclas = _anclar_extraccion(
            resultado.extraccion, texto, identificador=norma.identificador_oficial
        )
        if anclas is None:
            fallidas += 1
            continue

        deteccion = Deteccion(
            norma_id=norma.id,
            extraccion_json={
                "extraccion": resultado.extraccion.model_dump(mode="json"),
                "version_prompt": resultado.version_prompt,
                "modelo": resultado.modelo,
                # Cuántos artículos llegan sin texto por ninguno de los dos lados. Va dentro
                # del JSON y no en una columna por lo mismo que `version_prompt`: es un dato
                # de esta extracción concreta, no un eje por el que se vaya a consultar.
                "punteros": del_documento,
                # Regla de oro 9 y 7.5: cada texto citado, con su rango sobre el texto derivado
                # del documento archivado. Las dos versiones viajan al lado porque un offset sin
                # saber sobre qué derivación y con qué criterio se midió no es reproducible.
                "anclas": anclas,
                "version_texto_plano": VERSION_TEXTO_PLANO,
                "version_anclaje": VERSION_ANCLAJE,
                "extraido_en": datetime.datetime.now(datetime.UTC).isoformat(),
            },
            clasificacion=Clasificacion.INDETERMINADO,
            origen=OrigenClasificacion.HEURISTICA,
            regla_aplicada=None,
        )
        session.add(deteccion)
        # **Un commit por norma, no uno al final.** Medido el 2026-08-18: una pasada de 19 horas
        # sobre 11 normas no dejó ni una fila porque el commit estaba fuera del bucle, así que
        # cualquier interrupción tiraba todo el trabajo del modelo. Es el mismo criterio que ya
        # seguían la fase 2 y el versionado, y por el mismo motivo: aquí cada iteración cuesta
        # 133,9 s (ADR 0011) y perder una hora de CPU por cerrar una terminal es inaceptable.
        session.commit()
        extraidas += 1


    return ResumenExtraccion(
        evaluadas=len(normas), extraidas=extraidas, fallidas=fallidas, punteros=punteros
    )
