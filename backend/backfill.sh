#!/bin/sh
# Ingesta de fondo del BOE, hacia atras por meses, desacoplada de ninguna sesion.
# Idempotente: el sha256 hace que reejecutar no duplique, asi que se puede matar y relanzar.
set -u
LOG=/app/data/backfill.log
echo "=== arranque $(date -u) ===" >> "$LOG"
for RANGO in \
  "2026-08-16 2026-08-20" \
  "2026-07-01 2026-07-31" \
  "2026-06-05 2026-06-30" \
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
  echo "--- bloque $DESDE .. $HASTA  ($(date -u)) ---" >> "$LOG"
  python -m worker.run --fuente boe --fecha "$DESDE" --hasta "$HASTA" --sin-extraccion >> "$LOG" 2>&1
  echo "--- fin bloque $DESDE ($(date -u)) ---" >> "$LOG"
done
echo "=== TERMINADO $(date -u) ===" >> "$LOG"
