"""Mide el ruido que queda en el eje de citas: el verbo que cae en la ventana pero es de otra frase.

**No es código de producción y no lo importa nadie del pipeline.** Está en el repo por lo mismo
que `medir_ruido_lexico.py`: sostiene una decisión, y una decisión sostenida por números que nadie
puede reproducir es una opinión con decimales. Se ejecuta a mano, sobre lo ya archivado, sin tocar
la red ni el LLM:

    docker compose exec -T worker python -m scripts.medir_ventana_verbo --detalle

(como módulo, no por ruta: ejecutarlo por ruta pone `scripts/` en `sys.path` en vez de `/app`.)

## Qué contesta

`pipeline/citas.py` da por modificativa una referencia cuando encuentra un verbo (`se modifica`,
`se suprime`…) en los **200 caracteres anteriores** a la cita (`VENTANA_VERBO`). El 2026-08-30 se
arregló el caso en que el verbo pertenece al **nombre** de otra norma («…por la que se modifica la
Ley Orgánica 2/2006»), y quedó anotado que sobra un ruido distinto: el verbo está suelto en el
documento, dentro de la ventana, pero **pertenece a otra frase**.

    «... modificación de la Orden EDU/1234/2010. La Ley Orgánica 2/2006, de 3 de mayo, ...»

ESTADO.md lo dejó escrito así: *«no hay una construcción que lo delate, solo distancia»*, y
*«no se toca a ojo — estrechar la ventana sin medir perdería modificaciones reales»*. Esto es esa
medición.

## Qué mide

Para cada referencia **modificativa** que el eje encontraría con la selección anterior al
2026-09-03, el **desglose** de por qué `citas._gobierna` la descarta o la conserva: cuál de los
cinco criterios del ADR 0031 dispara (`F`, `N`, `C`, `R`, `P`), la distancia verbo→cita —que es lo
que decidiría un recorte de `VENTANA_VERBO`, la solución que primero se le ocurre a cualquiera— y
con `--detalle` el hueco entero, para poder leerlos uno a uno en vez de fiarse del recuento.

Y lo comprueba sobre los **casos de control**, que son las modificaciones reales que ninguna regla
nueva puede perder (`CONTROL`). Un filtro que mejora el ruido y se lleva uno de esos está mal, y
sin esta comprobación no se vería hasta que alguien mirase la cola.

## Lo que midió el 2026-09-03, sobre 925 normas de la cola (ADR 0031)

    referencias modificativas (antes): 89
    SOBREVIVEN:                        67
      descarta R (referencia, no objeto):     15
      descarta N (otra norma reclama el verbo): 9
      descarta C (empieza texto citado):        8
      descarta F (cierra una frase):            5
      descarta P («se modificaron»):            1
    (comparacion) ventana de 60:       67  <- MISMO numero, y pierde 2 modificaciones REALES
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
from app.pipeline import citas
from app.pipeline.referencias import VERBOS_MODIFICATIVOS
from app.pipeline.watchlist import watchlist
from app.services.cuerpo import CuerpoIlegible, leer_cuerpo

EN_COLA = (EstadoPrefiltro.RELEVANTE, EstadoPrefiltro.SOSPECHA)

# Modificaciones reales verificadas a mano, con la norma vigilada que tocan. Son las que el
# 2026-08-30 se usaron para comprobar el arreglo de «por la que se modifica» y **ninguna regla
# nueva puede perderlas**. Si una de estas desaparece, la regla candidata está mal, por muy bien
# que baje el ruido.
CONTROL: dict[str, str] = {
    "BOE-A-2024-10767": "las dos reformas madrileñas",
    "BOE-A-2024-10768": "las dos reformas madrileñas",
    "BOE-A-2025-11959": "la valenciana de 31 preceptos",
    "BOE-A-2022-2066": "la foral navarra",
    "BOE-A-2026-8073": "la catalana",
}

# **Los cinco criterios se importan de producción, no se copian.** Un script de medición con su
# propia copia de la regla mide su copia: la primera versión de este fichero los tenía duplicados
# y ya divergió una vez —contaba «se modifican» como flexión ajena— antes de que la regla
# existiera siquiera. Lo único que añade el script es el **desglose**: cuál de los cinco descarta
# cada referencia, que es lo que `citas._gobierna` no puede devolver porque devuelve un booleano.
_CRITERIOS: dict[str, object] = {
    "F": lambda forma, entre: citas._cierra_frase(entre),
    "N": lambda forma, entre: citas._OTRA_NORMA.search(entre) is not None,
    "C": lambda forma, entre: citas._ABRE_CITA.search(entre) is not None,
    "R": lambda forma, entre: citas._CONECTOR_REFERENCIAL.search(entre) is not None,
    "P": lambda forma, entre: citas._flexion_ajena(forma, entre),
}
_QUE_ES = {
    "F": "se cierra una frase en medio",
    "N": "otra norma reclama el verbo antes que la nuestra",
    "C": "empieza un texto citado (la redaccion nueva)",
    "R": "la cita es el termino de una referencia, no el objeto",
    "P": "el verbo casa dentro de otra palabra («se modificaron»)",
}


def _referencias_modificativas(texto: str, lista, titulo: str) -> list[tuple[str, str, str, str]]:
    """Las referencias **como se elegían antes del 2026-09-03**, con el hueco verbo→cita.

    Deliberadamente **sin** `citas._gobierna`: esa es la regla que se está midiendo, así que
    aplicarla aquí daría el «después» en las dos columnas y el script dejaría de poder decir qué
    quita. Todo lo demás sale de `citas` para que la selección no se desvíe del código real.

    Tampoco se reutiliza `extraer_referencias_citadas`: devuelve una referencia por norma y tira
    la posición del verbo, que es justo lo que hay que medir.
    """
    patron, por_cita = citas._indice(lista)
    if patron is None:
        return []
    normalizado = citas._normalizar(texto)
    salida: list[tuple[str, str, str, str]] = []
    for coincidencia in patron.finditer(normalizado):
        identificador = por_cita.get(citas._clave(coincidencia.group(0)))
        if identificador is None:
            continue
        inicio = coincidencia.start()
        ventana = normalizado[max(0, inicio - citas.VENTANA_VERBO) : inicio]
        ultimo = None
        for verbo in citas._VERBOS.finditer(ventana):
            anterior = ventana[: verbo.start()]
            if citas._TITULO_AJENO.search(anterior) and not citas._es_titulo_propio(
                titulo, coincidencia.group(0)
            ):
                continue
            ultimo = verbo
        if ultimo is None:
            continue
        forma = ultimo.group(0).lower()
        canonico = citas._CANONICO[forma]
        if canonico not in VERBOS_MODIFICATIVOS:
            continue
        entre = ventana[ultimo.end() :]
        salida.append((identificador, canonico, forma, entre))
    return salida


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scripts.medir_ventana_verbo")
    parser.add_argument(
        "--detalle",
        action="store_true",
        help="Imprime el hueco entre el verbo y la cita de cada referencia, para poder leerlos.",
    )
    parser.add_argument(
        "--todas",
        action="store_true",
        help="Mira todas las normas con cuerpo archivado y no solo las de la cola.",
    )
    args = parser.parse_args(argv)

    raiz = get_settings().almacen_root
    lista = watchlist()
    consulta = select(Norma).where(Norma.documento_texto_id.is_not(None))
    if not args.todas:
        consulta = consulta.where(Norma.prefiltro_estado.in_(EN_COLA))

    distancias: list[int] = []
    reparto: Counter[str] = Counter()
    # Dos conjuntos y no uno: «no sobrevive» y «el eje de citas nunca la vio» son resultados
    # distintos y confundirlos haría creer que una regla candidata pierde un caso que en realidad
    # entra por el `<analisis>` del BOE (ADR 0022, las dos fuentes del eje).
    vistas_hoy: set[str] = set()
    supervivientes: set[str] = set()
    detalle: list[str] = []

    with SessionLocal() as session:
        normas = session.scalars(consulta).all()
        for norma in normas:
            try:
                cuerpo = leer_cuerpo(norma, almacen_root=raiz)
            except CuerpoIlegible:
                continue
            if cuerpo is None:
                continue
            for identificador, verbo, forma, entre in _referencias_modificativas(
                cuerpo.texto, lista, norma.titulo or ""
            ):
                distancia = len(entre)
                reparto["referencias modificativas (hoy)"] += 1
                distancias.append(distancia)
                marcas = {letra: bool(prueba(forma, entre)) for letra, prueba in _CRITERIOS.items()}
                for letra, activa in marcas.items():
                    if activa:
                        reparto[f"descarta {letra} ({_QUE_ES[letra]})"] += 1
                gobierna = not any(marcas.values())
                # La comprobación que de verdad importa: el desglose de arriba tiene que dar lo
                # mismo que la regla de producción. Si divergen, el script está midiendo otra cosa.
                assert gobierna == citas._gobierna(forma, entre), (forma, entre)
                if gobierna:
                    reparto["SOBREVIVEN (lo que hace hoy citas._gobierna)"] += 1
                if distancia <= 60:
                    reparto["(comparacion) sobreviven a ventana de 60"] += 1
                clave = norma.identificador_oficial or ""
                vistas_hoy.add(clave)
                if gobierna:
                    supervivientes.add(clave)
                if args.detalle:
                    dibujo = "".join(letra if activa else "." for letra, activa in marcas.items())
                    detalle.append(
                        f"{dibujo} {clave} -> {identificador} [{verbo}] ({distancia}) "
                        f"«{entre.strip()[-160:]}»"
                    )

    print(f"normas miradas: {len(normas)}")
    for clave, valor in sorted(reparto.items(), key=lambda par: -par[1]):
        print(f"  {clave}: {valor}")
    if distancias:
        print(
            f"  distancia verbo->cita: mediana {int(statistics.median(distancias))}, "
            f"min {min(distancias)}, max {max(distancias)}"
        )

    print("\ncasos de control (ninguno puede perderse):")
    for identificador, que_es in CONTROL.items():
        if identificador not in vistas_hoy:
            estado = "el eje de citas no la ve HOY (entra por el <analisis>, o no esta en la cola)"
        elif identificador in supervivientes:
            estado = "OK"
        else:
            estado = "LA PIERDE la regla candidata"
        print(f"  {identificador} ({que_es}): {estado}")

    if detalle:
        print("\ndetalle  [F=frontera de frase en medio, N=otra norma en medio]")
        for linea in sorted(detalle):
            print("  " + linea)
    return 0


if __name__ == "__main__":
    sys.exit(main())
