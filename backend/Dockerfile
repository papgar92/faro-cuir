FROM python:3.12-slim

WORKDIR /app

# Solo el manifiesto primero para aprovechar la cache de capas de Docker: si el codigo
# cambia pero las dependencias no, no se reinstalan.
COPY pyproject.toml ./
# Con las dependencias de desarrollo dentro. La imagen es la de este proyecto de un solo
# entorno, y `ruff`, `mypy` y `pytest` son lo que corre el CI: sin ellas, la única forma de
# ejecutar las comprobaciones era instalarlas a mano dentro del contenedor, y **se perdían al
# recrearlo** (pasó el 2026-08-14 y dejó la suite inejecutable sin ningún aviso). Una imagen de
# despliegue real las quitaría con una etapa aparte; ese día se añade, hoy sería complejidad
# para un despliegue que no existe.
RUN pip install --no-cache-dir -e ".[dev]"

COPY . .

EXPOSE 8000

# `--no-access-log` por el mismo motivo que en docker-compose.yml: el log de acceso de uvicorn
# escribe la IP del cliente en cada peticion y la 6.4 lo prohibe. Un solo proceso a proposito
# (ver `api/revision.py`): con varios workers, la cadencia del panel falla abierto.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
