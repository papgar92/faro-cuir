"""¿Qué normas han modificado a las vigiladas? Se le pregunta al BOE, no se adivina.

**No es código de producción** —nadie del pipeline lo importa— y está en el repo por lo mismo
que `medir_fase2.py` y `medir_ruido_lexico.py`: es la consulta que decide **qué días hay que
ingerir** para que el gold set tenga casos de un tipo concreto, y sin ella la alternativa es
traer meses de boletín a ciegas con la esperanza de que caiga uno.

    docker compose exec worker python -m scripts.quien_modifica

(como módulo, no como fichero suelto: ejecutarlo por ruta pone `scripts/` en `sys.path` en vez
de `/app` y el paquete `app` deja de encontrarse.)

## Cómo funciona, y el detalle que costó encontrarlo

El texto **consolidado** de cada norma vigilada trae en `<posteriores>` la lista de las normas
que la han modificado después. Ojo, porque **ese bloque no tiene la forma del `<anteriores>` del
texto de una norma**: usa `<id_norma>` y `<relacion>` («SE MODIFICA», «SE DEROGA»), no el
atributo `referencia` ni `<palabra>`. Verificado el 2026-08-19 sobre `BOE-A-2016-6728`.

## Lo que dio el 2026-08-19

29 normas modificadoras sobre las 21 vigiladas. Entre ellas, los dos casos que el gold set
llevaba desde el 2026-08-09 pidiendo y que no aparecían ingiriendo días seguidos: la **Ley Foral
de Presupuestos de Navarra 2022** (modifica la ley trans navarra) y la **ley de medidas fiscales
de la Generalitat Valenciana 2021** (modifica la ley LGTBI valenciana). Los dos están ya en
`tests/gold_set/casos/`.

Sale a la red por `url_guard`, con pausa entre peticiones (6.2), y valida el formato de cada
identificador antes de componer nada con él (6.10) — que venga de la fuente oficial no lo hace
confiable.
"""

import time

from app.ingest.boe_consolidado import url_consolidado
from app.pipeline.watchlist import watchlist
from app.security import url_guard, xml_safe

CABECERAS = {"Accept": "application/xml"}
MODIFICATIVOS = (
    "SE MODIFICA",
    "SE DEROGA",
    "SE SUPRIME",
    "SE AÑADE",
    "SE SUSTITUYE",
    "SE DEJA SIN EFECTO",
)


def main() -> int:
    lista = watchlist()
    filas = []
    for indice, vigilada in enumerate(lista.normas):
        if indice:
            time.sleep(1.0)
        try:
            crudo = url_guard.fetch(url_consolidado(vigilada.identificador), headers=CABECERAS)
            raiz = xml_safe.parse(crudo)
        except Exception as exc:  # noqa: BLE001 - es un script de consulta
            print(f"  !! {vigilada.identificador}: {type(exc).__name__}: {str(exc)[:80]}")
            continue
        # OJO: el bloque `posteriores` del CONSOLIDADO no tiene la forma del `anteriores` del
        # texto de la norma. Usa <id_norma> y <relacion>, no el atributo `referencia` ni
        # <palabra>. Verificado el 2026-08-19 sobre BOE-A-2016-6728.
        posteriores = raiz.findall(".//posteriores/posterior")
        tocan = []
        for posterior in posteriores:
            relacion = (posterior.findtext("relacion") or "").strip().upper()
            if any(relacion.startswith(v) for v in MODIFICATIVOS):
                tocan.append(
                    (
                        (posterior.findtext("id_norma") or "").strip(),
                        relacion,
                        (posterior.findtext("texto") or "").strip()[:110],
                    )
                )
        print(
            f"{vigilada.identificador} ({vigilada.ambito}): "
            f"{len(posteriores)} posteriores, {len(tocan)} modificativas"
        )
        for referencia, palabra, texto in tocan:
            print(f"    {referencia}  {palabra:10} {texto}")
            filas.append((vigilada.identificador, referencia, palabra))
    print()
    print("=== identificadores que modifican algo vigilado:")
    for vigilada, referencia, palabra in filas:
        print(f"{referencia}\t{palabra}\t-> {vigilada}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
