"""Punto de entrada de la app FastAPI."""

from fastapi import FastAPI

from app.api.documentos import router as documentos_router
from app.api.health import router as health_router

app = FastAPI(title="Faro Cuir")
app.include_router(health_router)
app.include_router(documentos_router)
