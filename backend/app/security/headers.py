"""Cabeceras de seguridad en todas las respuestas (CLAUDE.md 6.8).

La API devuelve JSON, no HTML, así que la mayoría de estas cabeceras no protegen a la API en
sí: protegen a un navegador que reciba una respuesta nuestra y se la trate como si fuera un
documento. Ese es justo el escenario de un XSS por *content sniffing* o de una respuesta
JSON embebida en un iframe ajeno. Cuestan una línea cada una y cierran la clase entera.
"""

from __future__ import annotations

from starlette.types import ASGIApp

# Política para las respuestas de la API. `default-src 'none'` es lo más restrictivo que
# existe y es exactamente lo correcto aquí: una respuesta JSON no debe cargar absolutamente
# nada. `frame-ancestors 'none'` impide que nadie la meta en un iframe, y `base-uri`/
# `form-action` cierran dos vectores que sobreviven a muchas CSP mal escritas.
CSP_API = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"

# La documentación interactiva de FastAPI es una página HTML que carga Swagger UI de un CDN,
# así que la política de arriba la rompería. Se le da una propia, acotada a ese CDN, en vez
# de relajar la de la API entera. Es una desviación consciente y acotada: si el despliegue
# público no necesita /docs, lo correcto es desactivarlo, no ampliar la CSP.
_CDN_DOCS = "https://cdn.jsdelivr.net"
CSP_DOCS = (
    f"default-src 'none'; script-src {_CDN_DOCS}; style-src {_CDN_DOCS} 'unsafe-inline'; "
    f"img-src {_CDN_DOCS} data:; font-src {_CDN_DOCS}; connect-src 'self'; "
    "frame-ancestors 'none'; base-uri 'none'"
)

RUTAS_DOCS = ("/docs", "/redoc", "/openapi.json")

CABECERAS_COMUNES = {
    # Sin esto, un navegador puede decidir por su cuenta que un JSON es HTML y ejecutarlo.
    "X-Content-Type-Options": "nosniff",
    # No filtrar a dónde va el usuario. En un observatorio de derechos LGTBI+ el referer es
    # dato sensible por sí mismo: revela que alguien venía de aquí.
    "Referrer-Policy": "no-referrer",
    # Redundante con frame-ancestors para navegadores modernos; se mantiene por los que no.
    "X-Frame-Options": "DENY",
    # No necesitamos ninguna API del navegador. Se apagan todas explícitamente.
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), interest-cohort=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}

# Un año, con subdominios. Solo tiene efecto sobre HTTPS —un navegador ignora HSTS recibido
# por HTTP—, así que enviarla en desarrollo no rompe nada. No se incluye `preload`: pedir la
# inclusión en la lista precargada de los navegadores es difícil de revertir y no se hace sin
# un dominio definitivo.
HSTS = "max-age=31536000; includeSubDomains"


class SecurityHeadersMiddleware:
    """Middleware ASGI puro, sin depender de `BaseHTTPMiddleware`.

    `BaseHTTPMiddleware` envuelve la respuesta en una tarea y complica el manejo de errores y
    del *streaming*. Para añadir cabeceras no hace falta nada de eso.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:  # type: ignore[no-untyped-def]
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        es_docs = scope.get("path", "").rstrip("/") in RUTAS_DOCS

        async def send_con_cabeceras(mensaje):  # type: ignore[no-untyped-def]
            if mensaje["type"] == "http.response.start":
                cabeceras = mensaje.setdefault("headers", [])
                for nombre, valor in CABECERAS_COMUNES.items():
                    cabeceras.append((nombre.lower().encode(), valor.encode()))
                csp = CSP_DOCS if es_docs else CSP_API
                cabeceras.append((b"content-security-policy", csp.encode()))
                cabeceras.append((b"strict-transport-security", HSTS.encode()))
            await send(mensaje)

        await self.app(scope, receive, send_con_cabeceras)


def aplicar(app) -> None:  # type: ignore[no-untyped-def]
    """Registra el middleware en la aplicación."""
    app.add_middleware(SecurityHeadersMiddleware)


__all__ = [
    "CABECERAS_COMUNES",
    "CSP_API",
    "CSP_DOCS",
    "HSTS",
    "SecurityHeadersMiddleware",
    "aplicar",
]
