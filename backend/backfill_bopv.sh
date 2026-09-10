#!/bin/sh
# Ingesta de fondo del BOPV (Pais Vasco, ADR 0035), hacia atras por meses. Mismo diseno que
# `backfill.sh` y por los mismos dos motivos, que conviene no volver a aprender:
#
#   * IDEMPOTENTE por el sha256: reejecutar un dia no duplica documentos.
#   * REANUDABLE por un fichero de marcas, una por bloque terminado. Sin eso, al morir el
#     proceso el bucle vuelve a empezar por el principio y repite meses ya hechos.
#
# La marca solo se escribe si el worker salio con 0: un bloque interrumpido se repite entero,
# que es barato y es lo unico que garantiza que no queden huecos silenciosos en el archivo.
#
# DOS PARTICULARIDADES DE ESTA FUENTE (ADR 0035):
#
#   * cada dia cuesta UNA peticion mas -el calendario del mes, 1,5 KB- porque es lo que resuelve
#     la fecha a su numero de edicion. El BOPV no se puede pedir por fecha directamente.
#   * UN DIA PUEDE TRAER DOS BOLETINES, unas cinco veces cada 33 meses, y el segundo suele ser
#     un extraordinario con una sola norma del maximo rango. El worker recorre las dos
#     ediciones; si algun dia alguien "simplifica" eso, este backfill dejaria de traerlas.
#
# OJO: lanzarlo con el `.env` tal cual escribiria en el bucket de produccion. Se lanza SIEMPRE
# con el compose local:
#
#   docker compose -f docker-compose.yml -f docker-compose.local.yml exec -d worker \
#       sh /app/backfill_bopv.sh
#
# `--sin-extraccion` a proposito: una extraccion cuesta ~318 s y NO alimenta el gate humano,
# que se surte del catalogo de reglas leyendo el texto archivado (ADR 0016).

set -u

DATOS=/app/data
LOG="$DATOS/backfill-bopv.log"
HECHOS="$DATOS/backfill-bopv.hechos"

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

  MARCA="$DESDE..$HASTA"
  if grep -qxF "$MARCA" "$HECHOS" 2>/dev/null; then
    echo "--- saltado (ya hecho) $MARCA ---" >> "$LOG"
    continue
  fi

  echo "--- bloque $DESDE .. $HASTA  ($(date -u)) ---" >> "$LOG"
  if python -m worker.run --fuente bopv --fecha "$DESDE" --hasta "$HASTA" --sin-extraccion \
      >> "$LOG" 2>&1
  then
    echo "$MARCA" >> "$HECHOS"
    echo "--- fin bloque $DESDE ($(date -u)) ---" >> "$LOG"
  else
    echo "--- BLOQUE $DESDE FALLIDO, no se marca; se reintenta al relanzar ($(date -u)) ---" >> "$LOG"
  fi
done

echo "=== TERMINADO $(date -u) ===" >> "$LOG"
