"""¿Qué normas modifica de verdad este corpus, y cuántas veces? Censo sobre lo ya archivado.

Se lanza **como módulo y desde `backend/`**::

    docker compose exec -T worker python -m scripts.medir_normas_mas_modificadas          # censo
    docker compose exec -T worker python -m scripts.medir_normas_mas_modificadas 5000     # muestra

Ni una petición de red.

## Para qué existe

Para decidir **qué añadir a `config/watchlist.json`** con un dato en vez de con una intuición.

Medido el 2026-08-23: la watchlist tiene 24 normas, el corpus toca 22 de ellas y 17 ya producen
veredicto. Como las cuatro reglas que llegan al gate exigen «toca una norma vigilada» (ADR 0017),
**el techo del sistema entero son esas 22 normas en 69.388**. El catálogo no está ciego: mira por
una rendija.

Y hay un criterio que decide qué candidata merece la pena, y no es la importancia jurídica:

> **Una norma en la watchlist solo aporta si algo la modifica.** El eje referencial no detecta que
> una norma sea importante, detecta que otra disposición la MODIFIQUE o DEROGUE. Una ley venerable
> que nadie toca nunca no aporta ni un caso.

Ese criterio es **puramente empírico**, así que se mide aquí en vez de estimarlo. Este script no
sabe nada de derecho antidiscriminatorio y no pretende saberlo: dice qué se modifica mucho. Cruzar
eso con qué importa es el trabajo del `jurista-lgtbi` (13.4), y las dos mitades hacen falta —
una lista ordenada por frecuencia sin criterio jurídico vigilaría la normativa tributaria, y una
lista con criterio jurídico y sin frecuencia vigilaría normas que nadie toca.

## Qué cuenta exactamente

Referencias **modificativas** (`es_modificativa`: MODIFICA, DEROGA, SUPRIME, AÑADE…), que es la
misma condición que usa `_vigiladas` en el catálogo y el eje referencial del prefiltro. Una cita
sin verbo no cuenta, por lo mismo que allí: citar la Ley 4/2023 en el temario de una oposición no
es tocarla.

Se marca con `*` lo que ya está en la watchlist. Esas filas son el **control positivo**: si la
watchlist actual no apareciera por ningún lado, el instrumento estaría roto.
"""

from __future__ import annotations

import json
import random
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models.norma import Norma
from app.pipeline.watchlist import watchlist
from app.services.cuerpo import CuerpoIlegible, leer_cuerpo

CUANTAS_ENSENAR = 60


def main(argv: list[str]) -> int:
    n_muestra = int(argv[1]) if len(argv) > 1 else 0
    ajustes = get_settings()
    root = Path(ajustes.almacen_root)
    lista = watchlist()

    with SessionLocal() as sesion:
        ids = [
            fila[0]
            for fila in sesion.execute(
                select(Norma.id).where(
                    Norma.documento_texto_id.is_not(None),
                    # Los anuncios (`BOE-B-*`) no modifican normas. Fuera, por lo mismo que en
                    # `medir_terminos_candidatos`: diluyen sin aportar.
                    ~Norma.identificador_oficial.like("BOE-B-%"),
                )
            ).all()
        ]
        if n_muestra:
            random.seed(42)
            ids = random.sample(ids, min(n_muestra, len(ids)))
            print(f"MUESTRA de {len(ids):,} disposiciones")
        else:
            print(f"CENSO de {len(ids):,} disposiciones")

        modificadas: Counter[str] = Counter()
        # Cuántas normas del corpus modifican algo: es el denominador con el que se lee todo lo
        # demás, y sin él «47 modificaciones» no se sabe si es mucho o poco.
        con_alguna = 0
        leidas = 0
        titulos: dict[str, str] = {}

        for norma_id in ids:
            norma = sesion.get(Norma, norma_id)
            if norma is None:
                continue
            try:
                cuerpo = leer_cuerpo(norma, almacen_root=root, lista=lista)
            except CuerpoIlegible:
                continue
            if cuerpo is None:
                continue
            leidas += 1
            propias = {
                referencia.identificador
                for referencia in cuerpo.referencias
                if referencia.es_modificativa
            }
            if propias:
                con_alguna += 1
            modificadas.update(propias)
            for referencia in cuerpo.referencias:
                if referencia.es_modificativa and referencia.identificador not in titulos:
                    titulos[referencia.identificador] = (referencia.texto or "")[:90]

    print(f"leídas de verdad: {leidas:,}")
    print(f"de ellas, modifican o derogan alguna norma: {con_alguna:,}")
    print(f"normas distintas tocadas: {len(modificadas):,}\n")

    vigiladas_vistas = sum(1 for ident in modificadas if lista.contiene(ident))
    print(f"{'veces':>6}  {'identificador':22} {'':2} qué dice la referencia")
    print("-" * 110)
    for ident, veces in modificadas.most_common(CUANTAS_ENSENAR):
        marca = "*" if lista.contiene(ident) else " "
        print(f"{veces:>6}  {ident:22} {marca:2} {titulos.get(ident, '')}")

    print(f"\n* = ya está en la watchlist ({vigiladas_vistas} de las {len(modificadas):,} tocadas)")

    # El recuento se vuelca a disco porque el censo es caro (27.118 cuerpos leídos de un bind
    # mount) y la pregunta «¿cuánto aportaría ESTA candidata?» se hace una vez por cada lista de
    # candidatas que alguien proponga. Con el índice, esa pregunta pasa a ser un lookup.
    destino = Path(ajustes.almacen_root) / "normas-modificadas.json"
    destino.write_text(
        json.dumps(
            {
                "leidas": leidas,
                "con_alguna_modificacion": con_alguna,
                "muestra": n_muestra or None,
                "modificadas": dict(modificadas.most_common()),
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"índice volcado en {destino}")
    if vigiladas_vistas == 0:
        print(
            "\n*** CONTROL EN CERO: ninguna norma de la watchlist aparece entre las modificadas, "
            "cuando se sabe que 22 lo están. El instrumento está roto y ninguna fila de arriba "
            "significa nada. ***"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
