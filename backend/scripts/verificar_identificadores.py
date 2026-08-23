"""¿Existe esta norma y se llama como dicen que se llama? Se le pregunta al BOE.

Se lanza **como módulo y desde `backend/`**::

    docker compose exec -T worker python -m scripts.verificar_identificadores \\
        BOE-A-2022-11589 BOE-A-2023-13287 BOE-A-2018-14610

Sin argumentos verifica **las que ya están en `config/watchlist.json`**, que es la comprobación
de que la lista vigente sigue siendo real.

## Por qué existe este script

`config/watchlist.json` lo dice mejor que ninguna otra parte del repositorio:

> «un identificador inventado aquí **NO falla ruidosamente**. Simplemente no cruza nunca con
> nada, y el eje referencial parece funcionar mientras deja pasar justo lo que debía detectar.
> Es el peor error posible en este fichero.»

Ese es el modo de fallo exacto que la regla de oro 8 teme y el único que no se detecta usando el
sistema: una watchlist con una entrada fantasma se comporta igual que una watchlist correcta a la
que nadie modifica esa norma. Hasta hoy la única defensa era que quien la editara mirase boe.es a
mano.

El aviso no es teórico. El informe del `jurista-lgtbi` del 2026-08-23 entregó dos identificadores
**de memoria que eran falsos** y los cazó él mismo al verificarlos: `BOE-A-2007-13022` no es la
Ley 19/2007 del deporte sino la LO 8/2007 de financiación de partidos, y `BOE-A-2022-21630` no es
la Ley 39/2022 del Deporte sino una convocatoria de la Universidad de Murcia. Los dos son
identificadores **perfectamente bien formados y existentes**, así que ninguna validación de
formato los habría parado: apuntan a otra norma, que es la forma silenciosa del error.

De ahí la única comprobación que sirve: traer el **título oficial** y ponerlo al lado del que se
afirma. Que el identificador exista no es la pregunta; la pregunta es si es el de esta norma.

## Cómo sale a la red

Por `url_guard` (allowlist, sin IP privadas, con tope de tamaño) y `xml_safe`, igual que
`quien_modifica.py`, con pausa de cortesía entre peticiones (6.2). El identificador se valida
contra `PATRON_IDENTIFICADOR` antes de componer ninguna URL (6.10).

## Cómo leer la salida

- `OK` — el BOE devuelve esa norma. El título que imprime es **el oficial**: compáralo con el que
  creías que era. Esta es la comprobación, no el `OK`.
- `NO ESTÁ EN CONSOLIDADA` — no prueba que el identificador sea falso. La base consolidada no
  contiene todo el BOE: una resolución o una instrucción pueden existir y no estar consolidadas.
  Significa «esto hay que mirarlo a mano», no «esto es mentira».
"""

from __future__ import annotations

import sys
import time

from app.ingest.boe_consolidado import url_consolidado
from app.pipeline.watchlist import watchlist
from app.security import url_guard, xml_safe

CABECERAS = {"Accept": "application/xml"}
PAUSA_SEGUNDOS = 1.0


def _titulo_oficial(identificador: str) -> tuple[str, str]:
    """Devuelve `(estado, título)` preguntándole al BOE. No lanza: es un script de consulta."""
    try:
        crudo = url_guard.fetch(url_consolidado(identificador), headers=CABECERAS)
        raiz = xml_safe.parse(crudo)
    except Exception as exc:  # noqa: BLE001 - script de consulta, el error es el resultado
        return (f"ERROR {type(exc).__name__}", str(exc)[:90])

    titulo = (raiz.findtext(".//metadatos/titulo") or "").strip()
    if not titulo:
        # Algunas fichas traen el título en otro sitio; se busca sin anclar antes de rendirse.
        titulo = (raiz.findtext(".//titulo") or "").strip()
    if not titulo:
        return ("NO ESTÁ EN CONSOLIDADA", "")
    return ("OK", titulo)


def main(argv: list[str]) -> int:
    identificadores = argv[1:]
    esperados: dict[str, str] = {}
    if not identificadores:
        lista = watchlist()
        identificadores = [n.identificador for n in lista.normas]
        esperados = {n.identificador: n.titulo for n in lista.normas}
        print(f"Verificando las {len(identificadores)} normas de config/watchlist.json\n")
    else:
        print(f"Verificando {len(identificadores)} identificadores dados a mano\n")

    problemas = 0
    for indice, identificador in enumerate(identificadores):
        if indice:
            time.sleep(PAUSA_SEGUNDOS)
        estado, titulo = _titulo_oficial(identificador)
        if estado != "OK":
            problemas += 1
        print(f"{identificador:22} {estado}")
        if titulo:
            print(f"{'':22} título oficial: {titulo[:150]}")
        if identificador in esperados:
            print(f"{'':22} en la watchlist: {esperados[identificador][:150]}")
        print()

    print(f"{len(identificadores) - problemas} de {len(identificadores)} respondieron con título.")
    print(
        "RECUERDA: el `OK` solo dice que la norma existe. Lo que hay que comparar es el TÍTULO "
        "OFICIAL con el que se creía que era — un identificador bien formado que apunta a otra "
        "norma es el error que este script existe para cazar."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
