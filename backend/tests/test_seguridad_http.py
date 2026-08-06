"""Tests de los controles HTTP de la sección 6.8: cabeceras y rate limiting."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.security.headers import CSP_API, SecurityHeadersMiddleware
from app.security.rate_limit import RateLimiter, RateLimitMiddleware


@pytest.fixture
def app_minima() -> FastAPI:
    """Una app de juguete: aquí se prueban los middlewares, no las rutas reales."""
    app = FastAPI()

    @app.get("/api/prueba")
    def prueba() -> dict[str, str]:
        return {"ok": "si"}

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


class TestCabeceras:
    @pytest.fixture
    def client(self, app_minima: FastAPI) -> TestClient:
        app_minima.add_middleware(SecurityHeadersMiddleware)
        return TestClient(app_minima)

    def test_no_permite_adivinar_el_tipo_de_contenido(self, client: TestClient) -> None:
        assert client.get("/api/prueba").headers["x-content-type-options"] == "nosniff"

    def test_csp_bloquea_todo_en_las_respuestas_de_api(self, client: TestClient) -> None:
        assert client.get("/api/prueba").headers["content-security-policy"] == CSP_API

    def test_no_filtra_el_referer(self, client: TestClient) -> None:
        """En un observatorio LGTBI+ el referer revela que alguien venía de aquí."""
        assert client.get("/api/prueba").headers["referrer-policy"] == "no-referrer"

    def test_no_se_puede_enmarcar(self, client: TestClient) -> None:
        respuesta = client.get("/api/prueba")
        assert respuesta.headers["x-frame-options"] == "DENY"
        assert "frame-ancestors 'none'" in respuesta.headers["content-security-policy"]

    def test_hsts_sin_preload(self, client: TestClient) -> None:
        """`preload` es difícil de revertir; no se pide sin un dominio definitivo."""
        hsts = client.get("/api/prueba").headers["strict-transport-security"]
        assert "max-age=31536000" in hsts
        assert "preload" not in hsts

    def test_tambien_en_las_respuestas_de_error(self, client: TestClient) -> None:
        """Un 404 es tan susceptible de acabar interpretado por un navegador como un 200."""
        respuesta = client.get("/api/no-existe")
        assert respuesta.status_code == 404
        assert respuesta.headers["x-content-type-options"] == "nosniff"


class TestRateLimiter:
    """La lógica del contador, sin ASGI de por medio."""

    def test_deja_pasar_hasta_el_limite_y_luego_no(self) -> None:
        limitador = RateLimiter(peticiones=3, ventana=60)
        assert [limitador.permitir("1.2.3.4", ahora=0)[0] for _ in range(3)] == [True] * 3
        permitido, espera = limitador.permitir("1.2.3.4", ahora=0)
        assert not permitido
        assert espera > 0

    def test_la_ventana_es_deslizante(self) -> None:
        """Con ventana fija se colarían 2x el límite a caballo entre dos ventanas."""
        limitador = RateLimiter(peticiones=2, ventana=60)
        limitador.permitir("1.2.3.4", ahora=0)
        limitador.permitir("1.2.3.4", ahora=30)
        assert not limitador.permitir("1.2.3.4", ahora=59)[0]
        # A los 61s la primera ya ha salido de la ventana, pero la de t=30 sigue dentro.
        assert limitador.permitir("1.2.3.4", ahora=61)[0]
        assert not limitador.permitir("1.2.3.4", ahora=61)[0]

    def test_los_clientes_no_se_afectan_entre_si(self) -> None:
        limitador = RateLimiter(peticiones=1, ventana=60)
        assert limitador.permitir("1.1.1.1", ahora=0)[0]
        assert not limitador.permitir("1.1.1.1", ahora=0)[0]
        assert limitador.permitir("2.2.2.2", ahora=0)[0]

    def test_el_limitador_no_es_un_agotamiento_de_memoria(self) -> None:
        """Rotar la IP de origen no puede hacer crecer el diccionario sin límite.

        Es el fallo clásico de un limitador casero: el propio control se convierte en el
        vector. Al llegar al tope se falla ABIERTO a propósito — protege de un descuido, no
        guarda un secreto, y bloquear a todo el mundo sería peor que el problema.
        """
        limitador = RateLimiter(peticiones=1, ventana=60, max_clientes=5)
        for i in range(50):
            assert limitador.permitir(f"10.0.0.{i}", ahora=0)[0]
        assert len(limitador._clientes) <= 5


class TestRateLimitMiddleware:
    def test_responde_429_con_retry_after(self, app_minima: FastAPI) -> None:
        app_minima.add_middleware(RateLimitMiddleware, limiter=RateLimiter(peticiones=2))
        client = TestClient(app_minima)

        assert client.get("/api/prueba").status_code == 200
        assert client.get("/api/prueba").status_code == 200
        respuesta = client.get("/api/prueba")
        assert respuesta.status_code == 429
        assert int(respuesta.headers["retry-after"]) >= 1

    def test_health_queda_exento(self, app_minima: FastAPI) -> None:
        """Lo consulta el healthcheck del contenedor; limitarlo lo declararía caído."""
        app_minima.add_middleware(RateLimitMiddleware, limiter=RateLimiter(peticiones=1))
        client = TestClient(app_minima)

        for _ in range(10):
            assert client.get("/health").status_code == 200

    def test_el_429_tambien_lleva_cabeceras_de_seguridad(self, app_minima: FastAPI) -> None:
        """Fija el orden de los middlewares en `main.py`.

        El limitador tiene que rechazar antes de tocar la ruta, pero su respuesta debe salir
        igualmente por el middleware de cabeceras. Si alguien invierte el orden de los
        `add_middleware`, este test cae.
        """
        app_minima.add_middleware(RateLimitMiddleware, limiter=RateLimiter(peticiones=1))
        app_minima.add_middleware(SecurityHeadersMiddleware)
        client = TestClient(app_minima)

        client.get("/api/prueba")
        respuesta = client.get("/api/prueba")
        assert respuesta.status_code == 429
        assert respuesta.headers["x-content-type-options"] == "nosniff"
        assert respuesta.headers["content-security-policy"] == CSP_API


def test_la_app_real_trae_los_dos_controles() -> None:
    """Que los middlewares existan no sirve de nada si no están registrados."""
    from app.main import app

    registrados = {middleware.cls for middleware in app.user_middleware}
    assert SecurityHeadersMiddleware in registrados
    assert RateLimitMiddleware in registrados
    # El más externo es el último añadido, y debe ser el de cabeceras.
    assert app.user_middleware[0].cls is SecurityHeadersMiddleware
