"""Tests del guardia SSRF (CLAUDE.md 6.2).

Cada test es un intento de ataque concreto. No se toca la red real: el resolver DNS se
inyecta y el transporte HTTP es un `MockTransport`, así que la suite es determinista y corre
igual en CI sin salida a Internet.
"""

from __future__ import annotations

import httpx
import pytest

from app.security import url_guard
from app.security.url_guard import (
    CredentialsInUrl,
    HostNotAllowed,
    PortNotAllowed,
    PrivateAddressBlocked,
    ResponseTooLarge,
    SchemeNotAllowed,
    TooManyRedirects,
    UnresolvableHost,
)

ALLOWLIST = frozenset({"boe.es"})
IP_PUBLICA = "93.184.216.34"


def resolver_fijo(*ips: str) -> url_guard.Resolver:
    def _resolver(hostname: str, port: int) -> list[str]:
        return list(ips)

    return _resolver


def resolver_por_llamada(*respuestas: list[str]) -> url_guard.Resolver:
    """Devuelve una respuesta distinta en cada llamada: simula DNS rebinding."""
    pendientes = list(respuestas)

    def _resolver(hostname: str, port: int) -> list[str]:
        return pendientes.pop(0) if pendientes else []

    return _resolver


def cliente_mock(handler: object) -> httpx.Client:
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    return httpx.Client(transport=transport)


# --- Esquema, puerto, host -------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://boe.es/sumario",  # sin TLS
        "file:///etc/passwd",  # lectura de fichero local
        "gopher://boe.es:70/_secret",  # clásico para hablar con Redis/SMTP
        "data:text/plain;base64,aGVsbG8=",
        "ftp://boe.es/pub",
    ],
)
def test_rechaza_esquemas_distintos_de_https(url: str) -> None:
    with pytest.raises(SchemeNotAllowed):
        url_guard.validate(url, allowlist=ALLOWLIST, resolver=resolver_fijo(IP_PUBLICA))


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.com/x",
        "https://notboe.es/x",  # termina en "boe.es" como cadena, pero no es subdominio
        "https://boe.es.evil.com/x",  # contiene "boe.es", cuelga de otro dominio
        "https://xboe.es/x",
    ],
)
def test_rechaza_hosts_fuera_de_la_allowlist(url: str) -> None:
    with pytest.raises(HostNotAllowed):
        url_guard.validate(url, allowlist=ALLOWLIST, resolver=resolver_fijo(IP_PUBLICA))


@pytest.mark.parametrize("url", ["https://boe.es/x", "https://www.boe.es/x", "https://BOE.ES/x"])
def test_acepta_el_dominio_y_sus_subdominios_reales(url: str) -> None:
    objetivo = url_guard.validate(url, allowlist=ALLOWLIST, resolver=resolver_fijo(IP_PUBLICA))
    assert objetivo.ip == IP_PUBLICA


def test_rechaza_credenciales_embebidas_en_la_url() -> None:
    # Truco de suplantación visual: parece que va a boe.es, el host real es evil.com.
    with pytest.raises(CredentialsInUrl):
        url_guard.validate(
            "https://boe.es@evil.com/x", allowlist=ALLOWLIST, resolver=resolver_fijo(IP_PUBLICA)
        )


@pytest.mark.parametrize("url", ["https://boe.es:8443/x", "https://boe.es:22/x"])
def test_rechaza_puertos_no_permitidos(url: str) -> None:
    with pytest.raises(PortNotAllowed):
        url_guard.validate(url, allowlist=ALLOWLIST, resolver=resolver_fijo(IP_PUBLICA))


# --- Direcciones internas --------------------------------------------------------------


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",  # loopback
        "10.0.0.5",  # privada
        "192.168.1.1",  # privada
        "172.16.0.9",  # privada
        "169.254.169.254",  # metadatos de cloud: el objetivo estrella del SSRF
        "0.0.0.0",  # unspecified
        "100.64.0.1",  # CGNAT, se olvida en casi toda lista hecha a mano
        "::1",  # loopback IPv6
        "fd00::1",  # unique-local IPv6
        "::ffff:127.0.0.1",  # loopback IPv4 disfrazado de IPv6
    ],
)
def test_bloquea_hosts_que_resuelven_a_direcciones_internas(ip: str) -> None:
    with pytest.raises(PrivateAddressBlocked):
        url_guard.validate("https://boe.es/x", allowlist=ALLOWLIST, resolver=resolver_fijo(ip))


def test_bloquea_si_alguna_de_las_ips_resueltas_es_interna() -> None:
    # Devolver una IP buena y una mala busca que validemos la primera y usemos la segunda.
    with pytest.raises(PrivateAddressBlocked):
        url_guard.validate(
            "https://boe.es/x",
            allowlist=ALLOWLIST,
            resolver=resolver_fijo(IP_PUBLICA, "127.0.0.1"),
        )


def test_rechaza_host_que_no_resuelve() -> None:
    with pytest.raises(UnresolvableHost):
        url_guard.validate("https://boe.es/x", allowlist=ALLOWLIST, resolver=resolver_fijo())


# --- fetch: pinning, redirecciones y tope de tamaño ------------------------------------


def test_fetch_devuelve_el_cuerpo() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<sumario/>")

    with cliente_mock(handler) as client:
        cuerpo = url_guard.fetch(
            "https://boe.es/sumario",
            allowlist=ALLOWLIST,
            resolver=resolver_fijo(IP_PUBLICA),
            client=client,
        )
    assert cuerpo == b"<sumario/>"


def test_fetch_se_conecta_a_la_ip_validada_conservando_el_nombre() -> None:
    """Prueba de la defensa contra DNS rebinding.

    La petición que sale de verdad apunta a la IP que ya validamos, no al nombre: no hay una
    segunda resolución que un DNS hostil pueda contestar distinto. El nombre viaja en `Host`
    (vhost correcto) y en `sni_hostname` (SNI y verificación del certificado).
    """
    vistas: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        vistas.append(request)
        return httpx.Response(200, content=b"ok")

    with cliente_mock(handler) as client:
        url_guard.fetch(
            "https://boe.es/sumario",
            allowlist=ALLOWLIST,
            resolver=resolver_fijo(IP_PUBLICA),
            client=client,
        )

    (peticion,) = vistas
    assert peticion.url.host == IP_PUBLICA
    assert peticion.url.path == "/sumario"
    assert peticion.headers["Host"] == "boe.es"
    assert peticion.extensions["sni_hostname"] == "boe.es"


def test_fetch_sigue_redirecciones_dentro_de_la_allowlist() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/viejo":
            return httpx.Response(302, headers={"location": "https://www.boe.es/nuevo"})
        return httpx.Response(200, content=b"destino")

    with cliente_mock(handler) as client:
        cuerpo = url_guard.fetch(
            "https://boe.es/viejo",
            allowlist=ALLOWLIST,
            resolver=resolver_fijo(IP_PUBLICA),
            client=client,
        )
    assert cuerpo == b"destino"


def test_fetch_resuelve_redirecciones_relativas_contra_el_host_original() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/viejo":
            return httpx.Response(302, headers={"location": "/nuevo"})
        return httpx.Response(200, content=b"destino")

    with cliente_mock(handler) as client:
        cuerpo = url_guard.fetch(
            "https://boe.es/viejo",
            allowlist=ALLOWLIST,
            resolver=resolver_fijo(IP_PUBLICA),
            client=client,
        )
    assert cuerpo == b"destino"


def test_fetch_bloquea_redireccion_fuera_de_la_allowlist() -> None:
    """El 200 es legítimo; el ataque va en la Location. Por eso se revalida cada salto."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://evil.com/robar"})

    with cliente_mock(handler) as client, pytest.raises(HostNotAllowed):
        url_guard.fetch(
            "https://boe.es/sumario",
            allowlist=ALLOWLIST,
            resolver=resolver_fijo(IP_PUBLICA),
            client=client,
        )


def test_fetch_bloquea_redireccion_a_direccion_interna() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://boe.es/interno"})

    # El host sigue en la allowlist; lo que cambia entre saltos es a qué resuelve.
    resolver = resolver_por_llamada([IP_PUBLICA], ["169.254.169.254"])

    with cliente_mock(handler) as client, pytest.raises(PrivateAddressBlocked):
        url_guard.fetch(
            "https://boe.es/sumario", allowlist=ALLOWLIST, resolver=resolver, client=client
        )


def test_fetch_corta_los_bucles_de_redireccion() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://boe.es/vueltas"})

    with cliente_mock(handler) as client, pytest.raises(TooManyRedirects):
        url_guard.fetch(
            "https://boe.es/vueltas",
            allowlist=ALLOWLIST,
            resolver=resolver_fijo(IP_PUBLICA),
            client=client,
        )


def test_fetch_rechaza_respuestas_mayores_que_el_tope() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 5000)

    with cliente_mock(handler) as client, pytest.raises(ResponseTooLarge):
        url_guard.fetch(
            "https://boe.es/gordo",
            allowlist=ALLOWLIST,
            max_bytes=1000,
            resolver=resolver_fijo(IP_PUBLICA),
            client=client,
        )


def test_fetch_aplica_el_tope_aunque_no_haya_content_length() -> None:
    """El tope va sobre los bytes leídos, no sobre una cabecera que escribe el atacante.

    Con cuerpo en streaming no hay `Content-Length` que consultar; si el control dependiera
    de esa cabecera, aquí no saltaría nada.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=iter([b"x" * 1000] * 50))

    with cliente_mock(handler) as client, pytest.raises(ResponseTooLarge):
        url_guard.fetch(
            "https://boe.es/infinito",
            allowlist=ALLOWLIST,
            max_bytes=2000,
            resolver=resolver_fijo(IP_PUBLICA),
            client=client,
        )


def test_fetch_propaga_los_errores_http_de_la_fuente() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    with cliente_mock(handler) as client, pytest.raises(httpx.HTTPStatusError):
        url_guard.fetch(
            "https://boe.es/no-existe",
            allowlist=ALLOWLIST,
            resolver=resolver_fijo(IP_PUBLICA),
            client=client,
        )
