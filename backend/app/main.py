"""Punto de entrada de la app FastAPI."""

from fastapi import FastAPI

from app.api.health import router as health_router

app = FastAPI(title="Centinela")
app.include_router(health_router)
