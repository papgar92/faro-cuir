#!/bin/sh
# Ingesta de fondo del BOE, hacia atras por meses, desacoplada de ninguna sesion.
#
# IDEMPOTENTE Y REANUDABLE, que son dos cosas distintas y hacen falta las dos:
#
#   * Idempotente lo era ya, por el sha256: reejecutar un dia no duplica documentos. Eso protege
#     los DATOS, y los datos nunca han estado en peligro — cada documento se confirma en Postgres
#     segun se descarga, y la base vive en un volumen con nombre que sobrevive a que se paren los
#     contenedores, a que se reinicie Docker y a que se apague el ordenador.
#
#   * Reanudable NO lo era, y eso costaba TIEMPO. La lista de meses vivia en la memoria del shell,
#     asi que al morir el proceso el bucle volvia a empezar por agosto y se pasaba ~5 horas
#     repitiendo meses ya hechos antes de llegar a terreno nuevo. Paso dos veces el 2026-08-22:
#     una por suspension del portatil y otra porque el motor de Docker se colgo y hubo que
#     reiniciarlo.
#
# Como se reanuda: un fichero de marcas, una por bloque terminado, en el mismo volumen que el log.
# No se consulta la base para decidir - un bloque "hecho" es un bloque cuyo worker termino con
# exito, y eso no se puede deducir contando filas.

set -u

DATOS=/app/data
LOG="$DATOS/backfill.log"
HECHOS="$DATOS/backfill.hechos"

mkdir -p "$DATOS"
touch "$HECHOS"

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

  # La marca lleva las dos fechas: si alguien cambia el rango de un bloque, deja de estar hecho.
  MARCA="$DESDE..$HASTA"
  if grep -qxF "$MARCA" "$HECHOS" 2>/dev/null; then
    echo "--- saltado (ya hecho) $MARCA ---" >> "$LOG"
    continue
  fi

  echo "--- bloque $DESDE .. $HASTA  ($(date -u)) ---" >> "$LOG"
  if python -m worker.run --fuente boe --fecha "$DESDE" --hasta "$HASTA" --sin-extraccion >> "$LOG" 2>&1
  then
    # La marca se escribe SOLO si el worker salio con 0. Un bloque interrumpido a medias no se
    # marca y se repite entero la proxima vez: es barato (el sha256 lo hace idempotente) y es lo
    # unico que garantiza que no queden huecos silenciosos en el archivo, que es justo el fallo
    # que este proyecto existe para no cometer.
    echo "$MARCA" >> "$HECHOS"
    echo "--- fin bloque $DESDE ($(date -u)) ---" >> "$LOG"
  else
    echo "--- BLOQUE $DESDE FALLIDO, no se marca; se reintenta al relanzar ($(date -u)) ---" >> "$LOG"
  fi
done

echo "=== TERMINADO $(date -u) ===" >> "$LOG"
