#!/bin/sh
# Pone al dia el DOGC, que es la fuente que la interfaz declaraba vigilada sin estarlo.
#
# POR QUE ESTO VA ANTES QUE INTEGRAR UNA FUENTE NUEVA. El 2026-08-22, al publicar
# `ultima_publicacion` en /api/cobertura, aparecio esto: el DOGC se ingirio como una tanda
# historica de 2024 y su boletin mas reciente es del **31 de diciembre de 2024**. El mapa llevaba
# veinte meses pintando Catalunya como «vigilada», que se lee como «esto lo estamos mirando».
#
# Una fuente vigilada y desactualizada es PEOR que una no vigilada: la no vigilada se pinta con
# trama y dice la verdad, y la desactualizada promete algo que no esta pasando. Con dos fuentes en
# total, tener una asi es la mitad del sistema mintiendo por omision.
#
# Va HACIA ADELANTE, de donde se quedo hasta hoy, y no hacia atras como el del BOE: lo que falta
# aqui no es historia, es actualidad.
#
# Reanudable e idempotente por el mismo mecanismo que `backfill.sh`, y por el mismo motivo: la
# lista vive en la memoria del shell, asi que sin marcas un corte hace repetir meses enteros. La
# marca se escribe SOLO si el worker sale con 0.

set -u

DATOS=/app/data
LOG="$DATOS/backfill-dogc.log"
HECHOS="$DATOS/backfill-dogc.hechos"

mkdir -p "$DATOS"
touch "$HECHOS"

echo "=== arranque $(date -u) ===" >> "$LOG"

for RANGO in \
  "2025-01-01 2025-03-31" \
  "2025-04-01 2025-06-30" \
  "2025-07-01 2025-09-30" \
  "2025-10-01 2025-12-31" \
  "2026-01-01 2026-03-31" \
  "2026-04-01 2026-06-30" \
  "2026-07-01 2026-08-21"
do
  DESDE=$(echo "$RANGO" | cut -d' ' -f1)
  HASTA=$(echo "$RANGO" | cut -d' ' -f2)
  MARCA="$DESDE..$HASTA"

  if grep -qxF "$MARCA" "$HECHOS" 2>/dev/null; then
    echo "--- saltado (ya hecho) $MARCA ---" >> "$LOG"
    continue
  fi

  echo "--- bloque $DESDE .. $HASTA  ($(date -u)) ---" >> "$LOG"
  if python -m worker.run --fuente dogc --fecha "$DESDE" --hasta "$HASTA" --sin-extraccion >> "$LOG" 2>&1
  then
    echo "$MARCA" >> "$HECHOS"
    echo "--- fin bloque $DESDE ($(date -u)) ---" >> "$LOG"
  else
    echo "--- BLOQUE $DESDE FALLIDO, no se marca; se reintenta al relanzar ($(date -u)) ---" >> "$LOG"
  fi
done

echo "=== TERMINADO $(date -u) ===" >> "$LOG"

# AVISO PARA QUIEN LEA EL RESULTADO: se espera que una parte grande de lo que entre quede en
# `ilegible`. El DOGC publica muchas normas solo en PDF y el pipeline todavia no lo lee (ADR 0020:
# 172 de 264 normas de la tanda de 2024, el 65 %). Eso NO es un fallo de este script y no se
# arregla ingiriendo mas: se arregla con el lector de PDF, que sigue pendiente. Cualquier cifra de
# cobertura de esta fuente tiene que ir acompañada de cuantas de sus normas son ilegibles.
