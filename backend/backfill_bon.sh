#!/bin/sh
# Ingesta de fondo del BON (Navarra, ADR 0036), hacia atras por meses. Mismo diseno que
# `backfill.sh` y por los mismos dos motivos, que conviene no volver a aprender:
#
#   * IDEMPOTENTE por el sha256: reejecutar un dia no duplica documentos.
#   * REANUDABLE por un fichero de marcas, una por bloque terminado. Sin eso, al morir el
#     proceso el bucle vuelve a empezar por el principio y repite meses ya hechos.
#
# La marca solo se escribe si el worker salio con 0: un bloque interrumpido se repite entero,
# que es barato y es lo unico que garantiza que no queden huecos silenciosos en el archivo.
#
# CUIDADO, ESTA ES LA CARA DE LAS SIETE (ADR 0036). El BON no tiene calendario y su busqueda
# por fecha MIENTE -devuelve siempre el ultimo boletin-, asi que cada dia se resuelve por
# biseccion sobre el numero de boletin, leyendo la cabecera que declara cada candidato: hasta
# 16 peticiones de ~100 KB SOLO para averiguar que boletin toca, antes de descargar nada.
#
# Por eso arranca con TRES meses y no con seis como las otras dos. Se amplia cuando se vea el
# ritmo real, no antes: anadir bloques a esta lista es una linea, y lanzarlos a ciegas contra un
# portal ajeno no es aceptable (6.2).
#
# Y su articulado es HTML, o sea nivel C: si el portal cambia de maqueta, sus normas caeran a
# `ilegible` -que se reintenta y se cuenta aparte- en vez de archivarse vacias en silencio.
#
# OJO: lanzarlo con el `.env` tal cual escribiria en el bucket de produccion. Se lanza SIEMPRE
# con el compose local:
#
#   docker compose -f docker-compose.yml -f docker-compose.local.yml exec -d worker \
#       sh /app/backfill_bon.sh
#
# `--sin-extraccion` a proposito: una extraccion cuesta ~318 s y NO alimenta el gate humano,
# que se surte del catalogo de reglas leyendo el texto archivado (ADR 0016).

set -u

DATOS=/app/data
LOG="$DATOS/backfill-bon.log"
HECHOS="$DATOS/backfill-bon.hechos"

mkdir -p "$DATOS"
touch "$HECHOS"

echo "=== arranque $(date -u) ===" >> "$LOG"

for RANGO in \
  "2026-08-01 2026-08-31" \
  "2026-07-01 2026-07-31" \
  "2026-06-01 2026-06-30"
do
  DESDE=$(echo "$RANGO" | cut -d' ' -f1)
  HASTA=$(echo "$RANGO" | cut -d' ' -f2)

  MARCA="$DESDE..$HASTA"
  if grep -qxF "$MARCA" "$HECHOS" 2>/dev/null; then
    echo "--- saltado (ya hecho) $MARCA ---" >> "$LOG"
    continue
  fi

  echo "--- bloque $DESDE .. $HASTA  ($(date -u)) ---" >> "$LOG"
  if python -m worker.run --fuente bon --fecha "$DESDE" --hasta "$HASTA" --sin-extraccion \
      >> "$LOG" 2>&1
  then
    echo "$MARCA" >> "$HECHOS"
    echo "--- fin bloque $DESDE ($(date -u)) ---" >> "$LOG"
  else
    echo "--- BLOQUE $DESDE FALLIDO, no se marca; se reintenta al relanzar ($(date -u)) ---" >> "$LOG"
  fi
done

echo "=== TERMINADO $(date -u) ===" >> "$LOG"
