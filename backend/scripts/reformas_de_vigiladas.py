"""Quién ha reformado a cada norma de la watchlist, preguntándoselo al BOE consolidado.

Ejecutar: `docker compose exec -T backend python -m scripts.reformas_de_vigiladas`

## El problema que resuelve

Hasta el 2026-08-30 la única forma de encontrar una reforma de una ley vigilada era **tropezarse
con ella**: ingerir el día en que se publicó y esperar a que el eje referencial la cruzara. Con el
archivo cubriendo ~un año de BOE, y con el ADR 0027 midiendo que el eje referencial rinde unos 5
casos al año, eso dejaba el mapa con dos comunidades y quince en silencio.

El silencio no era falso —el sistema no puede afirmar lo que no ha visto— pero **sí era evitable**,
porque el dato existía y no se le estaba preguntando a nadie.

## El método, y por qué funciona

El texto consolidado que publica el BOE trae, **por cada bloque y por cada una de sus redacciones
sucesivas, el identificador de la norma que la introdujo** (`id_norma`, ver `extraer_bloques` en
`ingest/boe_consolidado.py`, ADR 0018). O sea que el consolidado de una ley **es su historial de
reformas**, y basta una petición por ley vigilada para tenerlo entero, desde su publicación hasta
hoy, sin ingerir un solo día de más.

19 peticiones —las leyes autonómicas vigentes— frente a backfillear años de boletín a ~20 minutos
por día. La primera ejecución, el 2026-08-30, encontró **14 normas modificadoras en 6 comunidades**
y **7 de ellas caían en huecos del archivo**.

## Lo que este script NO hace, y es deliberado

**No ingiere nada y no clasifica nada.** Imprime qué días habría que ingerir; ingerirlos es una
decisión con coste que toma una persona, y clasificar sigue siendo trabajo del catálogo de reglas
leyendo el texto archivado (ADR 0016). Un script que descubriera y publicara a la vez se saltaría
las dos puertas que este proyecto tiene puestas a propósito.

**Tampoco afirma que una reforma sea un retroceso.** Dice quién tocó qué y cuántos bloques; el
signo lo deriva el clasificador con reglas auditables (regla de oro 2). El recuento de bloques es
una medida del **tamaño** del cambio, no de su dirección: una ley que amplía derechos también toca
treinta bloques.

## El hallazgo que lo justifica

`BOE-A-2025-11959`, «Ley 5/2025, de 30 de mayo, **de medidas fiscales, de gestión administrativa y
financiera**», reescribió **31 bloques** de la ley trans valenciana (`BOE-A-2017-5118`) — el mismo
tamaño que la reforma madrileña de 2023 que el proyecto usa para explicarse.

Su título no contiene **ni una sola palabra** del vocabulario del prefiltro. El eje léxico no la
ve, y hasta que se ingirió su día el eje referencial no tenía dónde mirar. Es la definición exacta
del retroceso silencioso de la sección 1: la norma de rango bajo, publicada sin titular, que
desmonta un derecho dentro de una ley de acompañamiento presupuestario.
"""

from __future__ import annotations

import collections
import time

from app.ingest import boe_consolidado
from app.pipeline.watchlist import watchlist
from app.security import url_guard, xml_safe

# Cortesía con la fuente y freno propio (6.2), igual que la fase 2.
PAUSA_SEGUNDOS = 0.5


def main() -> int:
    lista = watchlist()
    vigiladas = [n for n in lista.normas if n.ambito not in ("", "estatal") and n.vigente]
    print(f"Consolidado de {len(vigiladas)} leyes autonómicas vigentes de la watchlist.\n")

    modificadoras: dict[str, list[tuple[str, str, int]]] = collections.defaultdict(list)
    fallos = 0

    for indice, vigilada in enumerate(sorted(vigiladas, key=lambda n: n.ambito)):
        if indice:
            time.sleep(PAUSA_SEGUNDOS)
        try:
            crudo = url_guard.fetch(
                boe_consolidado.url_consolidado(vigilada.identificador),
                headers=boe_consolidado.CABECERAS,
            )
            raiz = xml_safe.parse(crudo)
            boe_consolidado.comprobar_respuesta(raiz)
            bloques = boe_consolidado.extraer_bloques(raiz)
        except Exception as exc:  # noqa: BLE001 — es una sonda, no el pipeline
            # Se cuenta y se sigue. Un fallo aquí no invalida el resto, pero **sí se dice**: un
            # recuento de reformas con una ley que no se pudo consultar es un recuento incompleto,
            # y presentarlo como completo sería la afirmación de cobertura que 7.2 no permite.
            print(f"  {vigilada.ambito}  {vigilada.identificador}  FALLO {type(exc).__name__}")
            fallos += 1
            continue

        cuenta: collections.Counter[str] = collections.Counter()
        for bloque in bloques:
            for version in bloque.versiones:
                if version.id_norma and version.id_norma != vigilada.identificador:
                    cuenta[version.id_norma] += 1

        print(
            f"  {vigilada.ambito}  {vigilada.identificador}  "
            f"bloques={len(bloques):>4}  la han modificado: {len(cuenta)}"
        )
        for ident, bloques_tocados in cuenta.most_common():
            print(f"        {ident}  ({bloques_tocados} bloques)")
            modificadoras[ident].append((vigilada.ambito, vigilada.identificador, bloques_tocados))

    print(
        f"\n{len(modificadoras)} normas modificadoras distintas, en "
        f"{len({a for v in modificadoras.values() for a, _, _ in v})} comunidades."
    )
    if fallos:
        print(f"⚠  {fallos} leyes no se pudieron consultar: el recuento está INCOMPLETO.")
    print(
        "\nSiguiente paso, que NO hace este script: comprobar cuáles de esas normas están ya en\n"
        "`norma` e ingerir el día de las que falten. El coste de ingerir lo decide una persona."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
