#!/bin/sh
# Ingesta DIRIGIDA de los dias en que se publico una reforma de una norma vigilada.
#
# De donde salen estas fechas, porque el metodo importa mas que la lista: se le pregunta al
# TEXTO CONSOLIDADO de cada ley de la watchlist quien la ha modificado. Cada version de bloque
# que sirve el BOE lleva el `id_norma` que la introdujo (ADR 0018), asi que 19 peticiones dan el
# historial completo de reformas de las 19 leyes autonomicas vigentes -- sin backfillear anos.
# Lo hace `scripts/reformas_de_vigiladas.py`.
#
# POR QUE HACIA FALTA: el archivo del BOE cubre bien 2025-09..2026-08 y de ahi hacia atras solo
# tenia dias sueltos. Seis de las catorce normas modificadoras caian en esos huecos, y una de
# ellas es la mas grave que ha encontrado el proyecto: BOE-A-2025-11959, "Ley 5/2025 de medidas
# fiscales, de gestion administrativa y financiera", que reescribio 31 bloques de la ley trans
# valenciana. Su titulo no tiene una sola palabra del vocabulario: el eje lexico no la ve, y sin
# el dia ingerido el eje referencial tampoco tenia donde mirar.
#
# Reanudable e idempotente igual que los otros backfill.

set -u
DATOS=/app/data
LOG="$DATOS/reformas.log"
HECHOS="$DATOS/reformas.hechos"
mkdir -p "$DATOS"; touch "$HECHOS"
echo "=== arranque $(date -u) ===" >> "$LOG"

for FECHA in 2018-11-07 2019-02-27 2024-07-22 2024-12-26 2025-05-15 2025-06-14
do
  if grep -qxF "$FECHA" "$HECHOS" 2>/dev/null; then
    echo "--- saltado (ya hecho) $FECHA ---" >> "$LOG"; continue
  fi
  echo "--- dia $FECHA ($(date -u)) ---" >> "$LOG"
  if python -m worker.run --fuente boe --fecha "$FECHA" --sin-extraccion >> "$LOG" 2>&1; then
    echo "$FECHA" >> "$HECHOS"
  else
    echo "--- DIA $FECHA FALLIDO, no se marca ($(date -u)) ---" >> "$LOG"
  fi
done
echo "=== TERMINADO $(date -u) ===" >> "$LOG"
