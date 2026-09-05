"""Con qué comunidad conviene seguir, medido en vez de elegido a ojo.

**No es código de producción.** Está en el repo por lo mismo que `medir_ventana_verbo.py`: una
decisión de alcance sostenida por números que nadie puede reproducir es una opinión con
decimales. Se ejecuta a mano y no toca la red:

    docker compose exec -T backend python -m scripts.medir_fuentes_pendientes

## Qué contesta

El humano pidió el 2026-09-05 «que el resto de comunidades cojan datos». Son **13 boletines
autonómicos + 43 provinciales**, y la sección 8 pone el techo de la primera iteración en cinco
fuentes; vamos por cuatro. O sea que la pregunta real no es «¿todas?» sino **«¿cuál es la
quinta?»**, y esa sí se puede medir.

Tres cosas, y la tercera es la que manda:

1. **Qué ha rendido cada fuente ya integrada.** Normas ingeridas, cuántas entraron en la cola
   del gate humano y cuántas acabaron en alerta. Es el único dato empírico que tenemos sobre
   cuánto aporta añadir un boletín.
2. **Qué comunidades tienen norma vigilada.** El eje referencial (7.3) **solo puede disparar
   sobre una norma de la watchlist**: en una comunidad sin ley propia queda el eje léxico y
   nada más. No es un detalle — es la mitad del sistema apagada.
3. **El cruce**: comunidades con norma vigilada y sin boletín integrado. Ahí es donde un
   boletín nuevo puede rendir; en las demás se añade superficie sin añadir vigilancia.

## El límite que hay que tener delante al leer esto (ADR 0027)

Solo el **7 %** de las disposiciones modifican algo, y ampliar la watchlist rindió **~5 casos al
año**. Este script no va a encontrar una comunidad que multiplique la cobertura, porque no
existe. Sirve para ordenar, no para prometer.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy import text

from app.database import SessionLocal

# Nombres para el informe. El código ISO no dice nada en una tabla que va a leer una persona.
CCAA = {
    "AN": "Andalucía",
    "AR": "Aragón",
    "AS": "Asturias",
    "CB": "Cantabria",
    "CE": "Ceuta",
    "CL": "Castilla y León",
    "CM": "Castilla-La Mancha",
    "CN": "Canarias",
    "CT": "Cataluña",
    "EX": "Extremadura",
    "GA": "Galicia",
    "IB": "Baleares",
    "MC": "Murcia",
    "MD": "Madrid",
    "ML": "Melilla",
    "NC": "Navarra",
    "PV": "País Vasco",
    "RI": "La Rioja",
    "VC": "C. Valenciana",
}


def _watchlist() -> tuple[Counter[str], dict[str, str]]:
    """Cuántas normas vigiladas tiene cada comunidad, y cuáles constan sin ley propia."""
    raiz = Path(__file__).resolve().parents[2] / "config" / "watchlist.json"
    datos = json.loads(raiz.read_text(encoding="utf-8"))
    por_ccaa: Counter[str] = Counter()
    for norma in datos["normas"]:
        if norma["ambito"] != "estatal":
            por_ccaa[norma["ambito"]] += 1
    return por_ccaa, datos.get("_sin_ley_autonomica", {})


def main() -> int:
    vigiladas, sin_ley = _watchlist()

    with SessionLocal() as session:
        # Lo que ha rendido cada fuente ya integrada. `entra_en_la_cola` se replica aquí en SQL
        # a propósito de forma explícita (relevante + sospecha) para que el recuento no dependa
        # de importar el pipeline: este script tiene que poder leerse solo.
        filas = session.execute(
            text("""
                SELECT f.nombre,
                       f.ccaa_codigo,
                       count(DISTINCT n.id) AS normas,
                       count(DISTINCT n.id) FILTER (
                           WHERE n.prefiltro_estado IN ('relevante', 'sospecha')) AS en_cola,
                       count(DISTINCT d2.id) AS detecciones,
                       min(doc.fecha_publicacion) AS desde,
                       max(doc.fecha_publicacion) AS hasta
                FROM fuente f
                JOIN documento doc ON doc.fuente_id = f.id
                JOIN norma n ON n.documento_id = doc.id
                LEFT JOIN deteccion d2 ON d2.norma_id = n.id AND d2.regla_aplicada IS NOT NULL
                GROUP BY f.nombre, f.ccaa_codigo
                ORDER BY 3 DESC
            """)
        ).all()

        integradas = {fila.ccaa_codigo for fila in filas if fila.ccaa_codigo}

        print("=" * 78)
        print("1. QUE HA RENDIDO CADA FUENTE YA INTEGRADA")
        print("=" * 78)
        print(f"{'fuente':<38} {'normas':>8} {'en cola':>8} {'detecc.':>8}  periodo")
        for fila in filas:
            periodo = f"{fila.desde} a {fila.hasta}"
            print(
                f"{fila.nombre[:38]:<38} {fila.normas:>8} {fila.en_cola:>8} "
                f"{fila.detecciones:>8}  {periodo}"
            )
            # El dato que de verdad importa de una fuente: de cada mil normas ingeridas,
            # cuantas llegan a la cola donde una persona las mira.
            if fila.normas:
                por_mil = fila.en_cola * 1000 / fila.normas
                print(f"{'':<38} {'':>8} {por_mil:>7.1f}‰ de lo ingerido entra en la cola")

    print()
    print("=" * 78)
    print("2. QUE COMUNIDADES PUEDEN DISPARAR EL EJE REFERENCIAL")
    print("=" * 78)
    print("Una comunidad sin norma vigilada solo tiene el eje lexico: media vigilancia (7.3).")
    print()
    print(f"{'comunidad':<18} {'vigiladas':>10}  {'boletin':<14} {'nota'}")
    for codigo, nombre in sorted(CCAA.items(), key=lambda par: -vigiladas[par[0]]):
        n = vigiladas[codigo]
        boletin = "INTEGRADO" if codigo in integradas else "—"
        if codigo in sin_ley:
            nota = "sin ley autonomica propia"
        elif n == 0:
            nota = "no consta en la watchlist"
        else:
            nota = ""
        print(f"{nombre:<18} {n:>10}  {boletin:<14} {nota}")

    print()
    print("=" * 78)
    print("3. EL CRUCE: DONDE UN BOLETIN NUEVO PUEDE RENDIR")
    print("=" * 78)
    candidatas = [(CCAA[c], n) for c, n in vigiladas.items() if c not in integradas and c in CCAA]
    candidatas.sort(key=lambda par: -par[1])
    print("Con norma vigilada y SIN boletin integrado (por orden de normas vigiladas):")
    for nombre, n in candidatas:
        print(f"  {nombre:<18} {n} norma(s) vigilada(s)")
    print()
    inutiles = [CCAA[c] for c in CCAA if c not in integradas and vigiladas[c] == 0]
    if inutiles:
        print("Sin norma vigilada: anadir su boletin suma superficie, no vigilancia referencial:")
        print("  " + ", ".join(inutiles))

    print()
    print("Recordatorio del ADR 0027 antes de sacar conclusiones: solo el 7 % de las")
    print("disposiciones modifican algo, y ampliar la watchlist rindio ~5 casos al ano.")
    print("Esto ordena candidatas; no promete cobertura.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
