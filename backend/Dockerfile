# Dos etapas y contexto en la RAIZ del repositorio. ADR 0033.
#
# ## Por que el contexto es la raiz y no `backend/`
#
# Porque `config/watchlist.json` vive en la raiz (seccion 4) y **tiene que entrar en la imagen**.
# En local no hacia falta: el compose monta `./config` en `/config`. En Render no hay volumen, y
# el primer despliegue murio con
#
#     WatchlistNoDisponible: no se encuentra watchlist.json en: ['/config/watchlist.json', ...]
#
# en cada endpoint que la usa. Y no es un fichero opcional: `watchlist.py` levanta en vez de
# devolver una lista vacia justamente para que esto se vea, porque una watchlist vacia no falla
# -- deja de disparar el eje referencial y el sistema parece funcionar habiendo perdido la unica
# defensa contra la instruccion que modifica un derecho sin nombrarlo.
#
# Mover el contexto a la raiz obliga a tener un `.dockerignore`, y ahi salio que `backend/data/`
# -1,6 GB del archivo- viajaba al demonio de Docker en cada build.

FROM python:3.12-slim AS base

WORKDIR /app

# Solo el manifiesto primero para aprovechar la cache de capas de Docker: si el codigo
# cambia pero las dependencias no, no se reinstalan.
COPY backend/pyproject.toml ./
RUN pip install --no-cache-dir -e "."

COPY backend/ ./

# La watchlist, donde `pipeline/watchlist.py` la busca. Es la MISMA ruta que monta el compose,
# asi que en local el volumen la tapa -y se puede editar sin reconstruir- y en produccion queda
# la copia de la imagen. No se copia a `/app/config` a proposito: seria una tercera ruta que
# mantener sincronizada con las dos que ya busca el codigo.
COPY config/ /config/

EXPOSE 8000

# `--no-access-log` por el mismo motivo que en docker-compose.yml: el log de acceso de uvicorn
# escribe la IP del cliente en cada peticion y la 6.4 lo prohibe. Un solo proceso a proposito
# (ver `api/revision.py`): con varios workers, la cadencia del panel falla abierto.
#
# `${PORT:-8000}` y forma shell en vez de la de lista: Render inyecta el puerto por entorno y
# no se puede elegir, asi que un 8000 fijo haria que el servicio arrancara y su comprobacion de
# salud fallara sin que el log dijera nada util. En local no hay PORT y se queda en 8000, que es
# lo que espera el compose.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-access-log

# --- Etapa de desarrollo: la que usa docker-compose ---------------------------------------
#
# `ruff`, `mypy` y `pytest` son lo que corre el CI, y sin ellas dentro la unica forma de ejecutar
# las comprobaciones era instalarlas a mano en el contenedor, donde **se perdian al recrearlo**
# (paso el 2026-08-14 y dejo la suite inejecutable sin ningun aviso). Por eso siguen estando; lo
# que cambia es que ahora **no viajan a la imagen que se publica en internet**.
FROM base AS dev

RUN pip install --no-cache-dir -e ".[dev]"

# --- Y la produccion va LA ULTIMA, que es lo que hace que esto funcione -------------------
#
# Docker construye la ultima etapa cuando nadie pide otra, y **Render no sabe pedir otra**:
# `dockerTarget` no existe en su especificacion de `render.yaml` (comprobado el 2026-09-05
# contra render.com/docs/blueprint-spec, despues de que rechazara el fichero por ese campo).
#
# O sea que el orden de estas tres etapas NO es cosmetico: con `dev` al final, Render habria
# publicado en internet una imagen con ruff, mypy y pytest dentro, y sin que nada lo dijera. La
# unica forma de elegir etapa por defecto es ponerla la ultima.
#
# La etapa no anade nada a `base` a proposito: es `base`, con un nombre que dice para que es.
FROM base AS produccion
