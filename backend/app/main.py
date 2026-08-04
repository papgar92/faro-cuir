"""Punto de entrada de la app FastAPI.

Bootstrap minimo para que el contenedor arranque con docker-compose. El endpoint /health,
la config vía pydantic-settings y el resto llegan en el commit "feat: backend minimo".
"""

from fastapi import FastAPI

app = FastAPI(title="Centinela")
