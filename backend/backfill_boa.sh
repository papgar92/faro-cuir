#!/bin/sh
# Ingesta de fondo del BOA (ADR 0028), hacia atras por meses. Mismo diseno que `backfill.sh`
# y por los mismos dos motivos, que conviene no volver a aprender:
#
#   * IDEMPOTENTE por el sha256: reejecutar un dia no duplica documentos.
#   * REANUDABLE por un fichero de marcas, una por bloque terminado. Sin eso, al morir el
#     proceso el bucle vuelve a empezar por el principio y se pasa horas repitiendo meses ya
#     hechos antes de llegar a terreno nuevo. Paso dos veces con el BOE.
#
# La marca solo se escribe si el worker salio con 0: un bloque interrumpido a medias se repite
# entero la proxima vez, que es barato y es lo unico que garantiza que no queden huecos
# silenciosos en el archivo — justo el fallo que este proyecto existe para no cometer.
#
# `--sin-extraccion` a proposito: una extraccion cuesta ~318 s (ADR 0027 y el cierre del
# 2026-08-28) y NO alimenta el gate humano, que se surte del catalogo de reglas leyendo el
# texto archivado (ADR 0016). Lo que se salta aqui no se pierde: la cola del extractor es una
# consulta, asi que una pasada normal posterior lo recoge.

set -u

DATOS=/app/data
LOG="$DATOS/backfill-boa.log"
HECHOS="$DATOS/backfill-boa.hechos"

mkdir -p "$DATOS"
touch "$HECHOS"

echo "=== arranque $(date -u) ===" >> "$LOG"

for RANGO in \
  "2026-08-01 2026-08-28" \
  "2026-07-01 2026-07-31" \
  "2026-06-01 2026-06-30" \
  "2026-05-01 2026-05-31" \
  "2026-04-01 2026-04-30" \
  "2026-03-01 2026-03-31" \
  "2026-02-01 2026-02-28" \
  "2026-01-01 2026-01-31" \
  "2025-12-01 2025-12-31" \
  "2025-11-01 2025-11-30" \
  "2025-10-01 2025-10-31" \
  "2025-09-01 2025-09-30"
do
  DESDE=$(echo "$RANGO" | cut -d' ' -f1)
  HASTA=$(echo "$RANGO" | cut -d' ' -f2)

  # La marca lleva las dos fechas: si alguien cambia el rango de un bloque, deja de estar hecho.
  MARCA="$DESDE..$HASTA"
  if grep -qxF "$MARCA" "$HECHOS" 2>/dev/null; then
    echo "--- saltado (ya hecho) $MARCA ---" >> "$LOG"
    continue
  fi

  echo "--- bloque $DESDE .. $HASTA  ($(date -u)) ---" >> "$LOG"
  if python -m worker.run --fuente boa --fecha "$DESDE" --hasta "$HASTA" --sin-extraccion \
      >> "$LOG" 2>&1
  then
    echo "$MARCA" >> "$HECHOS"
    echo "--- fin bloque $DESDE ($(date -u)) ---" >> "$LOG"
  else
    echo "--- BLOQUE $DESDE FALLIDO, no se marca; se reintenta al relanzar ($(date -u)) ---" >> "$LOG"
  fi
done

echo "=== TERMINADO $(date -u) ===" >> "$LOG"
