"""Punto de entrada de la app FastAPI."""

from fastapi import FastAPI

from app.api.documentos import router as documentos_router
from app.api.health import router as health_router
from app.security.headers import SecurityHeadersMiddleware
from app.security.rate_limit import RateLimitMiddleware

app = FastAPI(title="Faro Cuir")

# El orden no es indiferente. En Starlette el **último** `add_middleware` queda por fuera,
# así que las cabeceras se registran las últimas para envolverlo todo: el limitador sigue
# rechazando antes de que la petición toque la ruta o la base de datos, y su respuesta 429
# sale igualmente por el middleware de cabeceras. Al revés, un 429 viajaría sin ellas — y una
# respuesta de error es tan susceptible de acabar interpretada por un navegador como las
# demás. Hay un test que fija este orden.
#
# No se activa CORS a propósito (CLAUDE.md): el proxy de Vite resuelve el desarrollo y en
# producción frontend y API van tras el mismo origen.
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

app.include_router(health_router)
app.include_router(documentos_router)
