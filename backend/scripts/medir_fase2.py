"""Mide el coste real de la fase 2 de ingesta (CLAUDE.md 7.1, tarea 0.a del bloque
"EMPIEZA AQUÍ").

**No es código de producción y no lo importa nadie del pipeline.** Está en el repo y no en un
scratchpad por una razón concreta: los números que produce fijan una decisión de diseño en el
ADR 0011, y una decisión sostenida por números que nadie puede reproducir es una opinión con
decimales. Se ejecuta a mano, sobre los sumarios ya ingeridos:

    docker compose exec worker python -m scripts.medir_fase2 --salida /tmp/fase2.json

(como módulo, no como fichero suelto: ejecutarlo por ruta pone `scripts/` en `sys.path` en vez
de `/app` y el paquete `app` deja de encontrarse.)

Qué mide, y por qué cada cosa:

1. **Coste de descargar el día entero.** Bytes y tiempo de bajar el texto íntegro de *todas*
   las normas del sumario, no solo de las que pasarían un umbral. Es el número que decide si
   la fase 2 puede prescindir de filtro previo (7.1): si el día entero es asumible, el
   prefiltro pasa de descartar a priorizar, y el falso negativo por título deja de existir.
2. **Cuántas dispararía un umbral bajo.** Con una definición *candidata* del umbral (léxico
   actual sobre el título + patrones estructurales), para poder comparar con el punto 1. La
   definición definitiva del estado `sospecha` es trabajo de la tarea 0.b; aquí solo se
   cuenta, no se implementa nada que el pipeline vaya a usar.
3. **Cuánto se pierde decidiendo sobre el título.** Se reevalúa el vocabulario léxico sobre el
   texto íntegro descargado y se cuentan las normas que el título descartaba y el cuerpo
   dispara. Es la medición directa de la afirmación de 7.1 —"el título es lo que el redactor
   controla"— y el único de estos números que puede refutar la sección.
4. **Cobertura del bloque `<analisis>`**, que es la fuente de datos del eje referencial (7.3):
   qué porcentaje de documentos lo trae y cuántas referencias por documento.

Las descargas pasan por `security/url_guard` como cualquier otra salida HTTP del proyecto
(ADR 0006): esto se ejecuta contra el BOE real y no hay motivo para que un script de medición
tenga un camino de red propio. Con pausa entre peticiones y tope por ejecución, que es además
lo que la 6.2 exige a la fase 2 de verdad.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from xml.etree.ElementTree import Element

import httpx
from sqlalchemy import select

from app.database import SessionLocal
from app.models.documento import Documento
from app.models.norma import Norma
from app.pipeline.prefiltro import VERSION_VOCABULARIO, ResultadoPrefiltro, evaluar
from app.pipeline.prefiltro import _normalizar as normalizar
from app.security import url_guard, xml_safe
from app.security.url_guard import UrlGuardError
from app.security.xml_safe import XmlSafeError

_CABECERAS = {"Accept": "application/xml"}

# Patrones estructurales candidatos del umbral bajo (7.1). Son fórmulas de encabezamiento del
# BOE, no vocabulario del dominio: describen que la disposición *toca* algo previo, que es
# justo la forma de un retroceso que no se nombra a sí mismo. Se escriben normalizados (sin
# tildes, minúsculas) porque se comparan contra `normalizar`.
#
# Están aquí y no en `pipeline/prefiltro.py` a propósito: esto mide un candidato para poder
# decidir el umbral con números. Implementarlo en el pipeline es la tarea 0.b, y hacerlo antes
# de tener la medición sería fijar el umbral por intuición, que es lo que 7.1 prohíbe.
PATRONES_ESTRUCTURALES: tuple[str, ...] = (
    "se modifica",
    "se modifican",
    "por la que se modifica",
    "queda sin efecto",
    "quedan sin efecto",
    "se deroga",
    "se derogan",
    "se suprime",
    "se suprimen",
    "se deja sin efecto",
    "cartera de servicios",
    "anexo",
    "instruccion",
)


@dataclass
class Medida:
    """Lo medido para una norma. Un registro por fila, para poder rehacer cualquier agregado."""

    identificador: str
    documento: str
    titulo: str
    # --- Señales sobre el título (lo único que trae el sumario, fase 1) ------------------
    titulo_lexico_relevante: bool
    titulo_lexico_solo_contexto: bool
    titulo_lexico_terminos: list[str]
    titulo_patrones: list[str]
    # --- Coste real de bajar el texto íntegro (fase 2) -----------------------------------
    ok: bool = False
    error: str | None = None
    bytes_descargados: int = 0
    ms_peticion: float = 0.0
    # --- Señales sobre el texto íntegro (lo que decide de verdad, 7.1) -------------------
    caracteres_texto: int = 0
    texto_lexico_relevante: bool = False
    texto_lexico_solo_contexto: bool = False
    texto_lexico_terminos: list[str] = field(default_factory=list)
    # --- Materia prima del eje referencial (7.3) ----------------------------------------
    tiene_analisis: bool = False
    # `anteriores` son las normas a las que ESTA disposición afecta (deroga, modifica): es
    # exactamente lo que el eje referencial tiene que cruzar con la watchlist. `posteriores`
    # son las que la afectaron a ella después, y no sirven para decidir en el día.
    referencias_anteriores: int = 0
    referencias_posteriores: int = 0
    # Verbos del BOE sobre cada referencia anterior (DEROGA, MODIFICA, ...). Son los que
    # convierten "menciona una norma" en "toca una norma".
    verbos_anteriores: list[str] = field(default_factory=list)
    ids_anteriores: list[str] = field(default_factory=list)


def _dispara_umbral_bajo(medida: Medida) -> bool:
    """Umbral bajo candidato: cualquier señal del título, en OR (7.3: nunca en AND)."""
    return medida.titulo_lexico_relevante or bool(medida.titulo_patrones)


def _patrones_en(titulo: str) -> list[str]:
    normalizado = normalizar(titulo)
    return [patron for patron in PATRONES_ESTRUCTURALES if normalizar(patron) in normalizado]


def _texto_plano(raiz: Element) -> str:
    """Mismo criterio que `services/extraccion._texto_plano`: el articulado vive en `<texto>`.

    Se duplica en vez de importarse porque aquí se mide el documento entero tal cual llega,
    sin el recorte a `MAX_CARACTERES_DOCUMENTO` que aplica el extractor: lo que interesa es el
    tamaño real, no el que cabe en el modelo.
    """
    cuerpo = raiz.find("./texto")
    objetivo = cuerpo if cuerpo is not None else raiz
    return " ".join(f.strip() for f in objetivo.itertext() if f.strip())


def _analisis(raiz: Element, medida: Medida) -> None:
    """Vacía el bloque `<analisis>` en la medida — ruido para el extractor, señal para el eje
    referencial (CLAUDE.md 7.3 y sección 11).

    Estructura verificada contra `BOE-A-2023-5366` real, no deducida de documentación:
    `analisis > referencias > anteriores > anterior[@referencia]`, con un `<palabra>` que dice
    qué le hace (DEROGA, MODIFICA) y un `<texto>` que dice a qué artículos. Es materia prima
    mucho mejor de lo que se suponía en 7.3: no es solo "menciona esta norma", viene el verbo.
    """
    bloque = raiz.find("./analisis")
    if bloque is None:
        return
    medida.tiene_analisis = True
    anteriores = bloque.findall("./referencias/anteriores/anterior")
    medida.referencias_anteriores = len(anteriores)
    medida.referencias_posteriores = len(bloque.findall("./referencias/posteriores/posterior"))
    for nodo in anteriores:
        # Dato de fuente externa: se recoge tal cual para medir, y **no se usa para construir
        # ninguna petición** (6.10). La validación de formato antes de cruzarlo con la
        # watchlist es trabajo de la tarea 0.b.
        identificador = nodo.get("referencia")
        if identificador:
            medida.ids_anteriores.append(identificador)
        palabra = nodo.findtext("./palabra")
        if palabra:
            medida.verbos_anteriores.append(palabra.strip())


def _resultado(res: ResultadoPrefiltro) -> tuple[bool, bool, list[str]]:
    return res.relevante, res.solo_por_contexto, list(res.terminos)


def medir(*, limite: int | None, pausa: float, client: httpx.Client | None = None) -> list[Medida]:
    with SessionLocal() as session:
        filas = list(
            session.execute(
                select(Norma, Documento.identificador_oficial)
                .join(Documento, Documento.id == Norma.documento_id)
                .order_by(Norma.id)
            )
        )

    medidas: list[Medida] = []
    for indice, (norma, sumario) in enumerate(filas):
        if limite is not None and indice >= limite:
            break

        relevante, solo_contexto, terminos = _resultado(
            evaluar(norma.titulo, organo_emisor=norma.organo_emisor)
        )
        medida = Medida(
            identificador=norma.identificador_oficial,
            documento=sumario,
            titulo=norma.titulo[:160],
            titulo_lexico_relevante=relevante,
            titulo_lexico_solo_contexto=solo_contexto,
            titulo_lexico_terminos=terminos,
            titulo_patrones=_patrones_en(norma.titulo),
        )

        if not norma.url_texto:
            medida.error = "sin url_texto"
            medidas.append(medida)
            continue

        # Cortesía con la fuente y freno propio (6.2): la pausa va antes de cada petición y
        # queda fuera del tiempo medido, que es el de la petición en sí.
        if indice and pausa:
            time.sleep(pausa)

        inicio = time.perf_counter()
        try:
            contenido = url_guard.fetch(norma.url_texto, headers=_CABECERAS, client=client)
            medida.ms_peticion = (time.perf_counter() - inicio) * 1000
            medida.bytes_descargados = len(contenido)
            raiz = xml_safe.parse(contenido)
        except (UrlGuardError, XmlSafeError) as exc:
            medida.error = f"{type(exc).__name__}: {exc}"
            medidas.append(medida)
            continue
        except httpx.HTTPError as exc:
            medida.error = f"{type(exc).__name__}: {exc}"
            medidas.append(medida)
            continue

        texto = _texto_plano(raiz)
        medida.ok = True
        medida.caracteres_texto = len(texto)
        (
            medida.texto_lexico_relevante,
            medida.texto_lexico_solo_contexto,
            medida.texto_lexico_terminos,
        ) = _resultado(evaluar(texto, organo_emisor=norma.organo_emisor))
        _analisis(raiz, medida)
        medidas.append(medida)

        if (indice + 1) % 25 == 0:
            print(f"  … {indice + 1}/{len(filas)}", file=sys.stderr, flush=True)

    return medidas


def _percentil(valores: list[float], q: float) -> float:
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    posicion = min(int(q * len(ordenados)), len(ordenados) - 1)
    return ordenados[posicion]


def resumir(medidas: list[Medida]) -> dict[str, object]:
    ok = [m for m in medidas if m.ok]
    tiempos = [m.ms_peticion for m in ok]
    total_bytes = sum(m.bytes_descargados for m in ok)

    umbral_bajo = [m for m in medidas if _dispara_umbral_bajo(m)]
    # El número que puede refutar 7.1: el título no dio ninguna señal léxica y el cuerpo sí,
    # y además con un término que no es de contexto genérico.
    perdidas_por_titulo = [
        m for m in ok if not m.titulo_lexico_relevante and m.texto_lexico_relevante
    ]
    perdidas_directas = [m for m in perdidas_por_titulo if not m.texto_lexico_solo_contexto]

    con_analisis = [m for m in ok if m.tiene_analisis]

    return {
        "version_vocabulario": VERSION_VOCABULARIO,
        "normas": len(medidas),
        "descargadas_ok": len(ok),
        "errores": Counter(m.error.split(":")[0] for m in medidas if m.error is not None),
        "coste_dia_entero": {
            "bytes": total_bytes,
            "mb": round(total_bytes / 1024 / 1024, 2),
            "kb_media_por_norma": round(total_bytes / len(ok) / 1024, 1) if ok else 0,
            "segundos_peticiones": round(sum(tiempos) / 1000, 1),
            "ms_media": round(statistics.mean(tiempos), 1) if tiempos else 0,
            "ms_mediana": round(statistics.median(tiempos), 1) if tiempos else 0,
            "ms_p95": round(_percentil(tiempos, 0.95), 1),
            "ms_max": round(max(tiempos), 1) if tiempos else 0,
        },
        "umbral_bajo_candidato": {
            "disparan": len(umbral_bajo),
            "porcentaje": round(100 * len(umbral_bajo) / len(medidas), 1) if medidas else 0,
            "solo_por_lexico": sum(
                1 for m in umbral_bajo if m.titulo_lexico_relevante and not m.titulo_patrones
            ),
            "solo_por_estructura": sum(
                1 for m in umbral_bajo if m.titulo_patrones and not m.titulo_lexico_relevante
            ),
            "por_patron": Counter(p for m in medidas for p in m.titulo_patrones),
            "bytes_ahorrados_mb": round(
                sum(m.bytes_descargados for m in ok if not _dispara_umbral_bajo(m)) / 1024 / 1024,
                2,
            ),
        },
        "coste_de_decidir_sobre_el_titulo": {
            "titulo_relevante": sum(1 for m in medidas if m.titulo_lexico_relevante),
            "texto_relevante": sum(1 for m in ok if m.texto_lexico_relevante),
            "descartadas_por_titulo_que_el_texto_dispara": len(perdidas_por_titulo),
            "de_ellas_con_termino_directo": len(perdidas_directas),
            "ejemplos_directos": [
                {
                    "id": m.identificador,
                    "titulo": m.titulo,
                    "terminos_en_texto": m.texto_lexico_terminos,
                }
                for m in perdidas_directas[:15]
            ],
        },
        "eje_referencial": {
            "documentos_con_analisis": len(con_analisis),
            "porcentaje_con_analisis": round(100 * len(con_analisis) / len(ok), 1) if ok else 0,
            "documentos_con_referencias_anteriores": sum(1 for m in ok if m.referencias_anteriores),
            "referencias_anteriores_total": sum(m.referencias_anteriores for m in ok),
            "referencias_anteriores_media": round(
                statistics.mean([m.referencias_anteriores for m in con_analisis]), 1
            )
            if con_analisis
            else 0,
            "referencias_anteriores_max": max((m.referencias_anteriores for m in ok), default=0),
            # El reparto de verbos dice si el eje referencial tendrá que mirarlos todos o solo
            # los que tocan el contenido de otra norma.
            "verbos": Counter(v for m in ok for v in m.verbos_anteriores).most_common(15),
            "normas_mas_referenciadas": Counter(
                i for m in ok for i in m.ids_anteriores
            ).most_common(10),
        },
        "tamano_documento": {
            "caracteres_media": round(statistics.mean([m.caracteres_texto for m in ok]))
            if ok
            else 0,
            "caracteres_mediana": round(statistics.median([m.caracteres_texto for m in ok]))
            if ok
            else 0,
            "caracteres_max": max((m.caracteres_texto for m in ok), default=0),
            # Cuántos superan el tope que hoy se manda al LLM (6.9.7): dice si el truncado es
            # un caso raro o la norma.
            "superan_4000_caracteres": sum(1 for m in ok if m.caracteres_texto > 4_000),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limite", type=int, default=None, help="tope de normas a descargar")
    parser.add_argument("--pausa", type=float, default=0.3, help="segundos entre peticiones")
    parser.add_argument("--salida", default="/tmp/fase2.json", help="fichero JSON de resultados")
    args = parser.parse_args()

    arranque = time.perf_counter()
    with httpx.Client(follow_redirects=False, timeout=url_guard.DEFAULT_TIMEOUT) as client:
        medidas = medir(limite=args.limite, pausa=args.pausa, client=client)
    reloj = time.perf_counter() - arranque

    resumen = resumir(medidas)
    resumen["segundos_reloj_con_pausas"] = round(reloj, 1)
    resumen["pausa_entre_peticiones_s"] = args.pausa

    with open(args.salida, "w", encoding="utf-8") as fichero:
        json.dump(
            {"resumen": resumen, "medidas": [asdict(m) for m in medidas]},
            fichero,
            ensure_ascii=False,
            indent=2,
            default=dict,
        )

    print(json.dumps(resumen, ensure_ascii=False, indent=2, default=dict))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
