#!/bin/sh
# Ingesta de fondo del BOCM (Madrid, ADR 0034), hacia atras por meses. Mismo diseno que
# `backfill.sh` y por los mismos dos motivos, que conviene no volver a aprender:
#
#   * IDEMPOTENTE por el sha256: reejecutar un dia no duplica documentos.
#   * REANUDABLE por un fichero de marcas, una por bloque terminado. Sin eso, al morir el
#     proceso el bucle vuelve a empezar por el principio y se pasa horas repitiendo meses ya
#     hechos antes de llegar a terreno nuevo. Paso dos veces con el BOE.
#
# La marca solo se escribe si el worker salio con 0: un bloque interrumpido a medias se repite
# entero la proxima vez, que es barato y es lo unico que garantiza que no queden huecos
# silenciosos en el archivo.
#
# PARTICULARIDAD DE ESTA FUENTE (ADR 0034): su sumario pesa 2,9 MB porque repite la lista
# entera 37 veces -2.701 elementos <disposicion> para 73 disposiciones reales-, asi que lo caro
# aqui es la descarga del sumario y no la fase 2. Un dia sin boletin da 404 y el worker sale
# con 0, o sea que los fines de semana no matan el bloque.
#
# OJO: lanzarlo con el `.env` tal cual escribiria en el bucket de produccion. Se lanza SIEMPRE
# con el compose local:
#
#   docker compose -f docker-compose.yml -f docker-compose.local.yml exec -d worker \
#       sh /app/backfill_bocm.sh
#
# `--sin-extraccion` a proposito: una extraccion cuesta ~318 s y NO alimenta el gate humano,
# que se surte del catalogo de reglas leyendo el texto archivado (ADR 0016). Lo que se salta
# aqui no se pierde: la cola del extractor es una consulta.

set -u

DATOS=/app/data
LOG="$DATOS/backfill-bocm.log"
HECHOS="$DATOS/backfill-bocm.hechos"

mkdir -p "$DATOS"
touch "$HECHOS"

echo "=== arranque $(date -u) ===" >> "$LOG"

for RANGO in \
  "2026-08-01 2026-08-31" \
  "2026-07-01 2026-07-31" \
  "2026-06-01 2026-06-30" \
  "2026-05-01 2026-05-31" \
  "2026-04-01 2026-04-30" \
  "2026-03-01 2026-03-31"
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
  if python -m worker.run --fuente bocm --fecha "$DESDE" --hasta "$HASTA" --sin-extraccion \
      >> "$LOG" 2>&1
  then
    echo "$MARCA" >> "$HECHOS"
    echo "--- fin bloque $DESDE ($(date -u)) ---" >> "$LOG"
  else
    echo "--- BLOQUE $DESDE FALLIDO, no se marca; se reintenta al relanzar ($(date -u)) ---" >> "$LOG"
  fi
done

echo "=== TERMINADO $(date -u) ===" >> "$LOG"
