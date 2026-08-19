"""Mide de qué se compone la cola del extractor: señal directa o fórmula administrativa.

**No es código de producción y no lo importa nadie del pipeline.** Está en el repo por lo mismo
que `medir_fase2.py`: los números que produce sostienen el ADR 0021, y una decisión sostenida por
números que nadie puede reproducir es una opinión con decimales. Se ejecuta a mano, sobre lo ya
ingerido y archivado, sin tocar la red ni el LLM:

    docker compose exec worker python -m scripts.medir_ruido_lexico

(como módulo, no como fichero suelto: ejecutarlo por ruta pone `scripts/` en `sys.path` en vez de
`/app` y el paquete `app` deja de encontrarse.)

## Qué contesta

El eje léxico (7.3) reparte sus términos en DIRECTO y CONTEXTO, y hasta el ADR 0021 esa
distinción **no cambiaba la decisión**: bastaba con que apareciera cualquiera de los dos para
entrar en la cola del LLM. Sobre un título eso es razonable —quince palabras— pero la fase 2 pasó
a evaluar el texto íntegro, donde «plan de igualdad» o «igualdad de trato» son fórmulas que
aparecen en cualquier documento administrativo largo.

Este script cuenta cuántas normas de la cola entran **solo** por términos de contexto, sobre qué
longitud de documento, y qué términos concretos son los responsables. Sin el desglose por término
no se puede afinar el vocabulario sin tocarlo entero, que es la misma razón por la que el embudo
guarda `por_eje`.

## Lo que midió el 2026-08-19, antes del ADR 0021

    cola total: 140
    SOLO por términos de contexto: 100  (71 %)
    con al menos un término directo:  40
    longitud de las «solo contexto»: mediana 54.099 caracteres, máximo 2.035.373
    responsables: igualdad de trato (51), plan de igualdad (24), no discriminación (20),
                  registro civil (18)

Reejecutarlo después del ADR 0021 no da «0 solo-contexto» porque esas normas ya no están en la
cola: da una cola más pequeña. Para volver a ver el reparto de antes hay que mirar toda la tabla,
no solo la cola, que es lo que hace `--todas`.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from collections import Counter

from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models.norma import EstadoPrefiltro, Norma
from app.pipeline.prefiltro import (
    _VOCABULARIO_NORMALIZADO,
    Categoria,
    _normalizar,
    terminos_presentes,
)
from app.services.cuerpo import CuerpoIlegible, leer_cuerpo

EN_COLA = (EstadoPrefiltro.RELEVANTE, EstadoPrefiltro.SOSPECHA)


def _es_directo(termino: str) -> bool:
    return _VOCABULARIO_NORMALIZADO[_normalizar(termino)][1] is Categoria.DIRECTO


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scripts.medir_ruido_lexico")
    parser.add_argument(
        "--todas",
        action="store_true",
        help=(
            "Mira todas las normas con cuerpo archivado y no solo las que están en cola. Es lo "
            "que hay que usar después del ADR 0021 para ver el reparto completo, porque las "
            "'solo contexto' ya no están en la cola."
        ),
    )
    args = parser.parse_args(argv)

    raiz = get_settings().almacen_root
    consulta = select(Norma).where(Norma.documento_texto_id.is_not(None))
    if not args.todas:
        consulta = consulta.where(Norma.prefiltro_estado.in_(EN_COLA))

    reparto: Counter[str] = Counter()
    culpables: Counter[str] = Counter()
    longitudes: list[int] = []

    with SessionLocal() as session:
        normas = session.scalars(consulta).all()
        for norma in normas:
            try:
                cuerpo = leer_cuerpo(norma, almacen_root=raiz)
            except CuerpoIlegible:
                # ADR 0020: archivada y sin poder leerse. No es ni señal ni ruido, es un hueco,
                # y contarla en cualquiera de los dos lados falsearía el reparto.
                reparto["ilegible"] += 1
                continue
            if cuerpo is None:
                continue
            terminos = terminos_presentes(cuerpo.texto)
            if not terminos:
                reparto["sin ningun termino"] += 1
                continue
            if any(_es_directo(termino) for termino in terminos):
                reparto["con al menos un termino directo"] += 1
                continue
            reparto["SOLO por terminos de contexto"] += 1
            longitudes.append(len(cuerpo.texto))
            for termino in terminos:
                culpables[termino] += 1

    print(f"normas miradas: {len(normas)}")
    for clave, valor in sorted(reparto.items(), key=lambda par: -par[1]):
        print(f"  {clave}: {valor}")
    if longitudes:
        print(
            "  longitud de las 'solo contexto': mediana "
            f"{int(statistics.median(longitudes))}, min {min(longitudes)}, max {max(longitudes)}"
        )
    print(f"  terminos responsables: {culpables.most_common(12)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
