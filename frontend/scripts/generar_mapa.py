#!/usr/bin/env python3
"""Genera `src/components/MapaCCAA/ccaa-paths.ts` desde el TopoJSON oficial.

Se ejecuta a mano, no en el build:

    python frontend/scripts/generar_mapa.py

Por qué existe
--------------
La geometría anterior venía del handoff de diseño ya proyectada a SVG
(`_design-export/data/ccaa-paths.json`) y traía tres defectos que el humano
reportó en el backlog (CLAUDE.md sección 12): Canarias mal colocada y a una
escala que no era la del resto, y **sin Ceuta ni Melilla**. Los tres son
defectos de proyección, y una proyección no se arregla moviendo números a mano
en un fichero de 58 KB: se rehace desde el origen. El TopoJSON fuente ya estaba
en el repo, conservado justamente "como referencia de procedencia".

Decisiones de cartografía, y por qué (regla de oro 8: no inventar geometría)
---------------------------------------------------------------------------
1. **Proyección cónica equivalente de Albers** (paralelos estándar 37°N y 43°N,
   meridiano central 3°O). Equivalente = conserva la superficie. En un mapa
   donde el color de cada comunidad es el dato, una proyección que agrande unas
   comunidades respecto de otras sesga la lectura antes de que nadie mire la
   leyenda. Es la misma decisión que toma el IGN para sus mapas temáticos.

2. **Canarias en recuadro, a la MISMA escala que la península.** Las islas están
   a 1.800 km y no caben en el encuadre peninsular sin dejar dos tercios del
   lienzo vacíos. Se proyectan con su propio meridiano central —si no, la
   distorsión cónica a 15° del centro las deforma— pero con **el mismo factor de
   escala**, y el recuadro lo dice. Un inset a escala distinta miente sobre el
   tamaño de la comunidad, y aquí Canarias tiene el mismo peso que cualquier otra.

3. **Ceuta y Melilla en su posición real, con marcador ampliado.** Son 19 y 12
   km²: a la escala de este mapa miden menos de un píxel. Se dibuja su geometría
   real *y* un círculo de radio fijo alrededor, que es lo que se puede señalar
   con el ratón o con el tabulador. La posición no se falsea; lo que se amplía
   es el objetivo de interacción, y la leyenda lo declara.

4. **Gibraltar se excluye.** El TopoJSON trae un objeto 20 rotulado "Gibraltar.
   Territorio no asociado a ninguna autonomía". Faro Cuir vigila boletines
   oficiales de 17 CCAA + 2 ciudades autónomas + BOE (CLAUDE.md sección 1); un
   territorio sin boletín que vigilar no es una entidad de este mapa. Se
   documenta la exclusión en vez de dejarla implícita.

5. **Simplificación Douglas-Peucker** con tolerancia en píxeles de salida. La
   geometría de origen tiene detalle para un mapa mucho mayor que este: sin
   simplificar, el fichero generado ocupa más que todo el resto del frontend
   junto y el navegador rasteriza vértices que caen en el mismo píxel.

Procedencia: `_design-export/data/es-autonomous-regions.topo.json`, geometría
del IGN (CC BY 4.0). No se descarga nada: el fichero ya está versionado.
"""

from __future__ import annotations

import json
import math
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ORIGEN = RAIZ / "_design-export" / "data" / "es-autonomous-regions.topo.json"
DESTINO = RAIZ / "src" / "components" / "MapaCCAA" / "ccaa-paths.ts"

# --- Lienzo -----------------------------------------------------------------
# Solo se fija el alto. El ancho sale de la geometría ya escalada, para que el
# viewBox no arrastre franjas vacías: con el zoom, un viewBox con aire a los
# lados hace que el primer nivel de ampliación no amplíe nada.
ALTO = 700.0
MARGEN = 14.0
# El recuadro de Canarias NO se dimensiona a ojo: la escala del inset es la de la
# península (decisión 2 del encabezado), así que el que cede es el recuadro. Se
# reserva una banda inferior calculada a partir de la proporción real entre la
# altura de las islas y la de la península, y la península se ajusta a lo que
# queda. Al revés —fijar el recuadro y encoger las islas para que quepan— es
# exactamente el defecto que se está arreglando.
INSET_PADDING = 11.0
INSET_SEPARACION = 12.0

# --- Proyección -------------------------------------------------------------
PAR_1 = 37.0
PAR_2 = 43.0
LAT_ORIGEN = 40.0
MERIDIANO_PENINSULA = -3.0
MERIDIANO_CANARIAS = -15.6

TOLERANCIA_PX = 0.18  # por debajo no se gana detalle: manda la cuantizacion del TopoJSON (~200 m)
AREA_MINIMA_PX2 = 0.6

# Códigos ISO 3166-2:ES, que son los que ya usa el frontend (REGIONS en
# api/mocks.ts) y los que usará la API cuando el mapa deje de ser una maqueta.
# El id del TopoJSON es el código INE de comunidad, que no coincide.
CODIGOS = {
    "01": ("AN", "Andalucía"),
    "02": ("AR", "Aragón"),
    "03": ("AS", "Asturias"),
    "04": ("IB", "Illes Balears"),
    "05": ("CN", "Canarias"),
    "06": ("CB", "Cantabria"),
    "07": ("CL", "Castilla y León"),
    "08": ("CM", "Castilla-La Mancha"),
    "09": ("CT", "Catalunya"),
    "10": ("VC", "C. Valenciana"),
    "11": ("EX", "Extremadura"),
    "12": ("GA", "Galicia"),
    "13": ("MD", "Madrid"),
    "14": ("MC", "Murcia"),
    "15": ("NC", "Navarra"),
    "16": ("PV", "Euskadi"),
    "17": ("RI", "La Rioja"),
    "18": ("CE", "Ceuta"),
    "19": ("ML", "Melilla"),
    # 20 = Gibraltar: excluido a propósito, ver el encabezado.
}

CIUDADES_AUTONOMAS = {"CE", "ML"}
INSET = {"CN"}


# --- TopoJSON ---------------------------------------------------------------


def decodificar_arcos(topo: dict) -> list[list[tuple[float, float]]]:
    """Deshace la cuantización y la codificación por deltas del TopoJSON."""
    escala = topo["transform"]["scale"]
    traslado = topo["transform"]["translate"]
    arcos = []
    for arco in topo["arcs"]:
        x = y = 0
        puntos = []
        for dx, dy in arco:
            x += dx
            y += dy
            puntos.append((x * escala[0] + traslado[0], y * escala[1] + traslado[1]))
        arcos.append(puntos)
    return arcos


def anillo(indices: list[int], arcos: list[list[tuple[float, float]]]) -> list[tuple[float, float]]:
    """Une los arcos de un anillo. Un índice negativo ~i significa el arco i al revés."""
    puntos: list[tuple[float, float]] = []
    for indice in indices:
        tramo = arcos[~indice][::-1] if indice < 0 else arcos[indice]
        # El último punto de un arco es el primero del siguiente: se evita duplicarlo.
        puntos.extend(tramo[1:] if puntos else tramo)
    return puntos


def poligonos(geometria: dict, arcos: list) -> list[list[list[tuple[float, float]]]]:
    if geometria["type"] == "Polygon":
        return [[anillo(r, arcos) for r in geometria["arcs"]]]
    if geometria["type"] == "MultiPolygon":
        return [[anillo(r, arcos) for r in poly] for poly in geometria["arcs"]]
    raise ValueError(f"tipo de geometría no esperado: {geometria['type']}")


# --- Albers cónica equivalente ---------------------------------------------


class Albers:
    def __init__(self, meridiano: float) -> None:
        f1, f2 = math.radians(PAR_1), math.radians(PAR_2)
        self.n = (math.sin(f1) + math.sin(f2)) / 2
        self.c = math.cos(f1) ** 2 + 2 * self.n * math.sin(f1)
        self.rho0 = math.sqrt(self.c - 2 * self.n * math.sin(math.radians(LAT_ORIGEN))) / self.n
        self.meridiano = math.radians(meridiano)

    def __call__(self, lon: float, lat: float) -> tuple[float, float]:
        rho = math.sqrt(self.c - 2 * self.n * math.sin(math.radians(lat))) / self.n
        theta = self.n * (math.radians(lon) - self.meridiano)
        # y crece hacia el norte; el volteo a coordenadas de pantalla se hace al encajar.
        return rho * math.sin(theta), self.rho0 - rho * math.cos(theta)


# --- Simplificación ---------------------------------------------------------


def douglas_peucker(puntos: list[tuple[float, float]], tol: float) -> list[tuple[float, float]]:
    if len(puntos) < 3:
        return puntos
    inicio, fin = puntos[0], puntos[-1]
    dx, dy = fin[0] - inicio[0], fin[1] - inicio[1]
    longitud = math.hypot(dx, dy)

    peor, indice = 0.0, 0
    for i in range(1, len(puntos) - 1):
        px, py = puntos[i]
        if longitud == 0:
            d = math.hypot(px - inicio[0], py - inicio[1])
        else:
            d = abs(dy * px - dx * py + fin[0] * inicio[1] - fin[1] * inicio[0]) / longitud
        if d > peor:
            peor, indice = d, i

    if peor <= tol:
        return [inicio, fin]
    izq = douglas_peucker(puntos[: indice + 1], tol)
    der = douglas_peucker(puntos[indice:], tol)
    return izq[:-1] + der


def area(puntos: list[tuple[float, float]]) -> float:
    """Área con signo (fórmula del cordón). En valor absoluto, para descartar migas."""
    s = 0.0
    for i in range(len(puntos)):
        x1, y1 = puntos[i]
        x2, y2 = puntos[(i + 1) % len(puntos)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


# --- Salida -----------------------------------------------------------------


def a_path(anillos: list[list[tuple[float, float]]]) -> str:
    partes = []
    for puntos in anillos:
        if len(puntos) < 3:
            continue
        d = f"M{puntos[0][0]:.1f} {puntos[0][1]:.1f}"
        d += "".join(f"L{x:.1f} {y:.1f}" for x, y in puntos[1:])
        partes.append(d + "Z")
    return "".join(partes)


def sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def main() -> None:
    topo = json.loads(ORIGEN.read_text(encoding="utf-8"))
    arcos = decodificar_arcos(topo)

    # 1. Proyectar en grados-proyectados, sin escalar todavía.
    peninsular = Albers(MERIDIANO_PENINSULA)
    canario = Albers(MERIDIANO_CANARIAS)

    crudo: dict[str, list[list[list[tuple[float, float]]]]] = {}
    for geometria in topo["objects"]["autonomous_regions"]["geometries"]:
        entrada = CODIGOS.get(geometria["id"])
        if entrada is None:
            continue
        codigo, _ = entrada
        proyecta = canario if codigo in INSET else peninsular
        crudo[codigo] = [
            [[proyecta(lon, lat) for lon, lat in anillo_] for anillo_ in poly]
            for poly in poligonos(geometria, arcos)
        ]

    faltan = set(CODIGOS.values()) - {(c, n) for c, n in CODIGOS.values() if c in crudo}
    if faltan:
        raise SystemExit(f"el TopoJSON no trae: {sorted(faltan)}")

    # 2. Escala y encaje: la manda el grupo peninsular (todo menos el inset).
    #    Ceuta y Melilla entran en el cálculo, así que el encuadre baja hasta el
    #    Estrecho en vez de cortar en Tarifa.
    puntos_peninsula = [
        p for cod, polys in crudo.items() if cod not in INSET for poly in polys for anillo_ in poly for p in anillo_
    ]
    min_x = min(p[0] for p in puntos_peninsula)
    max_x = max(p[0] for p in puntos_peninsula)
    min_y = min(p[1] for p in puntos_peninsula)
    max_y = max(p[1] for p in puntos_peninsula)

    puntos_canarias = [p for poly in crudo["CN"] for anillo_ in poly for p in anillo_]
    cn_min_x = min(p[0] for p in puntos_canarias)
    cn_max_x = max(p[0] for p in puntos_canarias)
    cn_min_y = min(p[1] for p in puntos_canarias)
    cn_max_y = max(p[1] for p in puntos_canarias)

    pen_w, pen_h = max_x - min_x, max_y - min_y
    cn_w, cn_h = cn_max_x - cn_min_x, cn_max_y - cn_min_y

    # Altura útil = península + separación + recuadro (que a su vez es
    # cn_h*escala + padding). Con escala = alto_peninsula/pen_h, se despeja:
    util = ALTO - 2 * MARGEN - INSET_SEPARACION - 2 * INSET_PADDING
    escala = (util / (1 + cn_h / pen_h)) / pen_h

    inset_ancho = cn_w * escala + 2 * INSET_PADDING
    ancho = max(pen_w * escala, inset_ancho) + 2 * MARGEN

    off_x = (ancho - pen_w * escala) / 2 - min_x * escala
    off_y = MARGEN + max_y * escala  # volteo: la y proyectada crece al norte

    def encajar(p: tuple[float, float]) -> tuple[float, float]:
        return (p[0] * escala + off_x, off_y - p[1] * escala)

    # 3. Canarias: MISMA escala, trasladada al recuadro inferior izquierdo. El
    #    recuadro se dimensiona a partir de las islas ya escaladas, no al revés.
    inset_alto = cn_h * escala + 2 * INSET_PADDING
    inset_x = MARGEN
    inset_y = ALTO - MARGEN - inset_alto
    cn_off_x = inset_x + INSET_PADDING - cn_min_x * escala
    cn_off_y = inset_y + inset_alto - INSET_PADDING + cn_min_y * escala

    def encajar_canarias(p: tuple[float, float]) -> tuple[float, float]:
        return (p[0] * escala + cn_off_x, cn_off_y - p[1] * escala)

    # El recuadro no puede solaparse con la península: si pasara, el encaje de
    # arriba está mal y hay que agrandar el lienzo, nunca encoger las islas.
    borde_sur_peninsula = off_y - min_y * escala
    if inset_y < borde_sur_peninsula + INSET_SEPARACION - 0.5:
        raise SystemExit(
            f"el recuadro de Canarias (y={inset_y:.0f}) pisa la península "
            f"(borde sur y={borde_sur_peninsula:.0f}). Sube ALTO; NO bajes la escala del inset."
        )

    # 4. Simplificar y serializar.
    salida = []
    for codigo, nombre in sorted(CODIGOS.values(), key=lambda t: sin_tildes(t[1])):
        transformar = encajar_canarias if codigo in INSET else encajar
        anillos: list[list[tuple[float, float]]] = []
        for poly in crudo[codigo]:
            for bruto in poly:
                puntos = [transformar(p) for p in bruto]
                simple = douglas_peucker(puntos, TOLERANCIA_PX)
                if simple[0] != simple[-1]:
                    simple.append(simple[0])
                if area(simple) < AREA_MINIMA_PX2:
                    continue
                anillos.append(simple)
        if not anillos:
            raise SystemExit(f"{codigo} se ha quedado sin geometría al simplificar")

        # Centroide del anillo mayor: ancla de la etiqueta y del marcador de las
        # ciudades autónomas. Del mayor y no de todos, o el de Canarias caería
        # en el Atlántico entre islas.
        mayor = max(anillos, key=area)
        cx = sum(p[0] for p in mayor) / len(mayor)
        cy = sum(p[1] for p in mayor) / len(mayor)
        salida.append(
            {
                "name": nombre,
                "code": codigo,
                "d": a_path(anillos),
                "cx": round(cx, 1),
                "cy": round(cy, 1),
                "inset": codigo in INSET,
                "micro": codigo in CIUDADES_AUTONOMAS,
            }
        )

    cabecera = f"""// GENERADO POR frontend/scripts/generar_mapa.py — NO EDITAR A MANO.
// Fuente: _design-export/data/es-autonomous-regions.topo.json (geometría IGN, CC BY 4.0).
// Proyección: Albers cónica equivalente ({PAR_1:.0f}°N / {PAR_2:.0f}°N). Canarias va en
// recuadro A LA MISMA ESCALA (ver el encabezado del script). Gibraltar excluido a
// propósito: no tiene boletín oficial que vigilar. Para cambiar algo, se cambia el
// script y se vuelve a ejecutar.

export interface CcaaPath {{
  name: string;
  code: string;
  /** Contorno SVG ya proyectado y simplificado. */
  d: string;
  /** Centroide del anillo mayor: ancla de etiqueta y de marcador. */
  cx: number;
  cy: number;
  /** Va dentro del recuadro de Canarias, no en el encuadre peninsular. */
  inset: boolean;
  /** Ciudad autónoma: su polígono real mide menos de un píxel a esta escala. */
  micro: boolean;
}}

/** Lienzo del SVG generado. El zoom trabaja sobre estas dimensiones. */
export const MAPA_VIEWBOX = {{ ancho: {ancho:.1f}, alto: {ALTO:.1f} }} as const;

/** Marco del recuadro de Canarias, en las mismas unidades. */
export const INSET_CANARIAS = {{
  x: {inset_x:.1f},
  y: {inset_y:.1f},
  ancho: {inset_ancho:.1f},
  alto: {inset_alto:.1f},
}} as const;

export const CCAA_PATHS: CcaaPath[] = [
"""
    cuerpo = "".join(
        "  {\n"
        f'    name: "{r["name"]}",\n'
        f'    code: "{r["code"]}",\n'
        f'    cx: {r["cx"]},\n'
        f'    cy: {r["cy"]},\n'
        f'    inset: {"true" if r["inset"] else "false"},\n'
        f'    micro: {"true" if r["micro"] else "false"},\n'
        f'    d: "{r["d"]}",\n'
        "  },\n"
        for r in salida
    )
    DESTINO.write_text(cabecera + cuerpo + "];\n", encoding="utf-8")

    vertices = sum(r["d"].count("L") + r["d"].count("M") for r in salida)
    print(f"{len(salida)} entidades, {vertices} vértices, {DESTINO.stat().st_size / 1024:.0f} KB")
    for r in salida:
        marca = " [inset]" if r["inset"] else (" [micro]" if r["micro"] else "")
        print(f"  {r['code']}  {r['name']:<20} centroide ({r['cx']:.0f}, {r['cy']:.0f}){marca}")


if __name__ == "__main__":
    main()
