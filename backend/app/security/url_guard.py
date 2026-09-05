"""Guardia de URLs salientes: la defensa contra SSRF de CLAUDE.md 6.2.

El worker de ingesta sigue enlaces que vienen dentro de los sumarios de los boletines. Eso
es dato no confiable (regla de oro 1). Sin validación, el worker se convierte en un proxy
hacia la red interna: quien controle o comprometa una fuente solo tiene que colar un
`<url>http://169.254.169.254/latest/meta-data/</url>` en su sumario para que se lo
descarguemos.

**Este módulo es la única puerta de salida HTTP del proyecto.** Nada en `ingest/` debe
importar `httpx` directamente; si lo hace, se ha saltado todos los controles de aquí.

Controles implementados:

1. Solo `https`. Sin `http`, `file`, `gopher`, `data`, ni nada más.
2. Solo puerto 443.
3. Host en allowlist (coincidencia exacta o subdominio real, no "empieza por").
4. Sin credenciales embebidas en la URL.
5. Toda IP resuelta debe ser global: nada de loopback, privadas, link-local (metadatos de
   cloud), CGNAT ni reservadas.
6. Redirecciones seguidas a mano, revalidando cada salto. Máximo 3.
7. Tope de bytes aplicado mientras se lee el cuerpo, no confiando en `Content-Length`.
8. Timeouts de conexión y de lectura.
9. Conexión clavada a la IP ya validada (ver `fetch`, sobre DNS rebinding).
"""

from __future__ import annotations

import ipaddress
import socket
import ssl
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

# Allowlist por defecto. Hoy solo el BOE, que es la única fuente verificada en
# docs/fuentes.md. Cuando exista ingesta real de varias fuentes, esto debería derivarse de
# `fuente.url_base` en la base de datos en vez de vivir en el código; se deja como constante
# mientras solo hay una fuente para no montar la maquinaria antes de necesitarla.
# Hosts que **solo** negocian un perfil TLS heredado, con lo que se ha medido de cada uno. Es
# una lista por host y no un ajuste global: relajar el perfil para todo el mundo debilitaría
# también la descarga del BOE, que negocia TLS 1.3 sin problema.
#
# `portaldogc.gencat.cat` (texto íntegro del DOGC, ADR 0019) solo acepta **TLS 1.2 con
# `AES256-SHA`**, verificado el 2026-08-16 probando handshakes uno a uno. OpenSSL 3 lo rechaza
# por su nivel de seguridad por defecto; `curl` funciona porque en Windows usa el TLS del
# sistema, y esa discrepancia es justo lo que hacía parecer el fallo cosa nuestra.
#
# **Qué se relaja y qué no**, porque la diferencia es lo que hace aceptable esto: se acepta un
# cifrado sin secreto hacia adelante y con MAC antiguo; **NO se relaja la verificación del
# certificado**, así que sigue haciendo falta un certificado válido para el nombre. Y el archivo
# no depende solo del canal: lo que se descarga se sella con su `sha256` (6.5), así que una
# alteración posterior es detectable aunque el transporte sea más débil de lo que nos gustaría.
# El contenido, además, es normativa pública: no hay confidencialidad que proteger, sí
# integridad, y esa se sostiene con certificado + huella.
HOSTS_TLS_HEREDADO: frozenset[str] = frozenset({"portaldogc.gencat.cat"})

DEFAULT_ALLOWLIST: frozenset[str] = frozenset(
    {
        "boe.es",
        # --- DOGC, segunda fuente y primera autonómica (ADR 0019) ---------------------------
        # Portal Jurídic (sumario y texto íntegro). Entran **los dos** subdominios vía el
        # dominio raíz porque el texto íntegro llega por redirección entre hosts
        # (`portaljuridic` → `portaldogc`) y `fetch` revalida cada salto: con uno solo, la
        # descarga fallaría como control de seguridad y parecería un problema de la fuente.
        "gencat.cat",
        # El sumario del DOGC **no vive en un dominio del diario**: vive en el portal de datos
        # abiertos de la Generalitat, que corre sobre un proveedor externo. Es la fuente oficial
        # de datos abiertos del gobierno catalán, y por eso entra; pero entra como decisión
        # escrita y no de tapadillo, porque "dominios oficiales" deja de ser autodescriptivo en
        # cuanto uno de ellos no lo parece.
        "transparenciacatalunya.cat",
        # --- BOA, tercera fuente y segunda autonómica (ADR 0028) ----------------------------
        # El sumario y el texto íntegro salen del mismo host, así que aquí no hace falta la
        # gimnasia de dos dominios del DOGC: una sola entrada cubre las dos fases.
        "boa.aragon.es",
        # --- BOCYL, cuarta fuente y tercera autonómica (ADR 0029) ---------------------------
        # Sumario (HTML) y cuerpo (XML) salen del mismo host, como en el BOA.
        "bocyl.jcyl.es",
    }
)

# Solo https: aparte de la confidencialidad, es lo que hace que el pinning por IP de `fetch`
# siga siendo seguro. Sobre http no habría certificado que verificar y clavarnos a una IP
# sería clavarnos a lo que dijera el DNS, sin nada que lo desmienta.
ALLOWED_SCHEMES: frozenset[str] = frozenset({"https"})
ALLOWED_PORTS: frozenset[int] = frozenset({443})

MAX_RESPONSE_BYTES: int = 20 * 1024 * 1024
MAX_REDIRECTS: int = 3
# **`connect` subió de 5 s a 20 s el 2026-09-05, con la ingesta ya en GitHub Actions (ADR
# 0032).** Los 5 s se eligieron con el proyecto corriendo en el portátil del humano, o sea una
# conexión española hablando con servidores españoles. Desde un runner en un centro de datos la
# ruta es mucho más larga, y el primer estreno del workflow lo enseñó: BOE y BOA cayeron los dos
# con `httpx.ConnectTimeout` mientras DOGC y BOCYL pasaban, y en el segundo intento pasaron las
# cuatro y falló el versionado, que sale a la misma red. Fallos distintos en cada pasada es la
# firma de un margen corto, no la de un bloqueo por rango de IP — que era la otra hipótesis y
# habría exigido su propio ADR.
#
# **No relaja ningún control.** Los que protegen son el timeout de LECTURA —que sigue en 15 s y
# es el que impide que una fuente lenta retenga el worker— y `MAX_RESPONSE_BYTES`. El de
# conexión solo dice cuánto se espera a que el otro extremo conteste, no qué se acepta cuando
# contesta. Y esperar de más ante una fuente pública es preferible a declararla caída: una
# ingesta que se salta un día deja un hueco de vigilancia, que es el fallo que importa aquí.
DEFAULT_TIMEOUT: httpx.Timeout = httpx.Timeout(15.0, connect=20.0)

_REDIRECT_STATUS: frozenset[int] = frozenset({301, 302, 303, 307, 308})

# Identificarse ante fuentes públicas es cortesía básica: si la ingesta molestara a alguien,
# quien administre el servidor puede saber qué es esto y a quién escribir, en vez de ver
# tráfico anónimo y bloquearlo sin más.
USER_AGENT: str = "FaroCuir/0.1 (vigilancia normativa de derechos LGTBI+; proyecto academico)"

# Resolver inyectable: (hostname, puerto) -> lista de IPs en texto. Existe para poder probar
# el guardia sin depender del DNS real.
Resolver = Callable[[str, int], list[str]]


class UrlGuardError(Exception):
    """Una URL o una respuesta se rechaza.

    Todas las subclases son de rechazo, nunca de aviso: si algo llega aquí, la ingesta de
    ese documento falla. Un guardia SSRF que degrada a warning no es un guardia.
    """


class SchemeNotAllowed(UrlGuardError):
    pass


class PortNotAllowed(UrlGuardError):
    pass


class HostNotAllowed(UrlGuardError):
    pass


class CredentialsInUrl(UrlGuardError):
    pass


class PrivateAddressBlocked(UrlGuardError):
    pass


class UnresolvableHost(UrlGuardError):
    pass


class TooManyRedirects(UrlGuardError):
    pass


class ResponseTooLarge(UrlGuardError):
    pass


@dataclass(frozen=True)
class ValidatedTarget:
    """Una URL que ha pasado todos los controles, junto con la IP a la que se resolvió."""

    url: str
    hostname: str
    port: int
    ip: str


def _default_resolver(hostname: str, port: int) -> list[str]:
    try:
        infos = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnresolvableHost(f"No se pudo resolver el host: {hostname!r}") from exc
    # sockaddr[0] es la IP tanto en IPv4 como en IPv6.
    return [str(info[4][0]) for info in infos]


def _host_allowed(hostname: str, allowlist: frozenset[str]) -> bool:
    """Coincidencia exacta o subdominio auténtico.

    Comparar con `startswith`/`in` es el fallo clásico: `boe.es.evil.com` contiene "boe.es",
    y `notboe.es` termina en "boe.es". Exigir el punto separador descarta ambos.
    """
    host = hostname.lower().rstrip(".")
    return any(host == domain or host.endswith(f".{domain}") for domain in allowlist)


def _assert_public_ip(raw_ip: str, hostname: str) -> None:
    ip = ipaddress.ip_address(raw_ip)

    # Un IPv6 mapeado (`::ffff:127.0.0.1`) es un IPv4 disfrazado. Se desenvuelve antes de
    # juzgarlo porque, según la versión de Python, el predicado sobre el IPv6 envoltorio no
    # siempre mira la dirección de dentro — y esa discrepancia es justo un bypass.
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped

    # `is_global` en vez de una lista a mano de rangos prohibidos: la lista a mano siempre se
    # deja algo fuera (CGNAT 100.64/10, 0.0.0.0/8, benchmarking 198.18/15, unique-local IPv6).
    # Invertir la pregunta —"¿es enrutable en Internet?"— hace que lo desconocido se rechace
    # por defecto en vez de colarse.
    if not ip.is_global:
        raise PrivateAddressBlocked(
            f"{hostname!r} resuelve a {ip}, que no es una dirección pública. "
            "Posible SSRF hacia la red interna o a los metadatos del proveedor cloud."
        )


def validate(
    url: str,
    *,
    allowlist: frozenset[str] = DEFAULT_ALLOWLIST,
    resolver: Resolver = _default_resolver,
) -> ValidatedTarget:
    """Valida una URL y devuelve el destino con su IP ya resuelta.

    Lanza la subclase de `UrlGuardError` que corresponda al primer control que falle.
    """
    parts = urlsplit(url)

    if parts.scheme not in ALLOWED_SCHEMES:
        raise SchemeNotAllowed(f"Esquema no permitido: {parts.scheme!r} (solo https)")

    if parts.username is not None or parts.password is not None:
        raise CredentialsInUrl("La URL lleva credenciales embebidas")

    hostname = parts.hostname
    if not hostname:
        raise HostNotAllowed(f"URL sin host: {url!r}")

    try:
        port = parts.port or 443
    except ValueError as exc:  # puerto no numérico
        raise PortNotAllowed(f"Puerto inválido en {url!r}") from exc
    if port not in ALLOWED_PORTS:
        raise PortNotAllowed(f"Puerto no permitido: {port}")

    if not _host_allowed(hostname, allowlist):
        raise HostNotAllowed(f"Host fuera de la allowlist: {hostname!r}")

    addresses = resolver(hostname, port)
    if not addresses:
        raise UnresolvableHost(f"El host no resolvió a ninguna dirección: {hostname!r}")

    # Se comprueban TODAS las direcciones, no solo la primera: un host que resuelve a una IP
    # pública y a una privada a la vez no es un host legítimo, es un intento de que elijamos
    # la buena y usemos la mala.
    for address in addresses:
        _assert_public_ip(address, hostname)

    return ValidatedTarget(url=url, hostname=hostname, port=port, ip=addresses[0])


def _netloc_for_ip(ip: str, port: int) -> str:
    address = ipaddress.ip_address(ip)
    host = f"[{address}]" if isinstance(address, ipaddress.IPv6Address) else str(address)
    return host if port == 443 else f"{host}:{port}"


def _build_pinned_request(
    client: httpx.Client, target: ValidatedTarget, headers: Mapping[str, str] | None
) -> httpx.Request:
    """Construye la petición apuntando a la IP ya validada, no al nombre.

    Sin esto queda un TOCTOU: validamos que `boe.es` resuelve a una IP pública y acto seguido
    httpx vuelve a resolver por su cuenta. Entre las dos resoluciones, un DNS hostil puede
    responder distinto (DNS rebinding) y la petición real acaba yendo a 127.0.0.1 con la
    validación ya superada.

    Al pedir directamente `https://<ip>/...` la segunda resolución no existe. Se conserva el
    nombre en la cabecera `Host` (para que el servidor sirva el vhost correcto) y en la
    extensión `sni_hostname`, que es la que usa httpx tanto para el SNI del handshake TLS como
    para verificar el certificado. Es decir: nos conectamos a la IP validada, pero seguimos
    exigiendo un certificado válido para el nombre original.
    """
    parts = urlsplit(target.url)
    pinned_url = parts._replace(netloc=_netloc_for_ip(target.ip, target.port)).geturl()
    host_header = target.hostname if target.port == 443 else f"{target.hostname}:{target.port}"

    cabeceras = {"User-Agent": USER_AGENT, **dict(headers or {})}
    # El Host lo fija el guardia y no quien llama. Permitir sobreescribirlo dejaría a la
    # capa de ingesta desactivar el pinning sin querer (o queriendo) con un solo parámetro.
    if any(nombre.lower() == "host" for nombre in cabeceras):
        raise UrlGuardError("La cabecera Host la fija el guardia; no se puede sobreescribir")
    cabeceras["Host"] = host_header

    return client.build_request(
        "GET",
        pinned_url,
        headers=cabeceras,
        extensions={"sni_hostname": target.hostname},
    )


def _read_capped(response: httpx.Response, max_bytes: int) -> bytes:
    """Lee el cuerpo abortando en cuanto supera el tope.

    El tope se aplica sobre los bytes que van llegando, no sobre `Content-Length`: esa
    cabecera la escribe el servidor, o sea el atacante, y puede mentir. Comprobarla sería un
    atajo cómodo y exactamente igual de inútil.
    """
    total = 0
    chunks: list[bytes] = []
    for chunk in response.iter_bytes():
        total += len(chunk)
        if total > max_bytes:
            raise ResponseTooLarge(f"La respuesta supera el tope de {max_bytes} bytes")
        chunks.append(chunk)
    return b"".join(chunks)


def _contexto_tls(hostname: str) -> ssl.SSLContext | bool:
    """El contexto TLS para este host: estricto por defecto, heredado solo si está declarado."""
    if hostname not in HOSTS_TLS_HEREDADO:
        return True  # el contexto por defecto de httpx, estricto
    contexto = ssl.create_default_context()
    # Nivel 1: admite los cifrados que este servidor ofrece. `check_hostname` y la validación de
    # la cadena siguen activados —no se tocan— y por eso esto no es "verify=False" con otro
    # nombre.
    contexto.set_ciphers("DEFAULT@SECLEVEL=1")
    return contexto


@contextmanager
def _ensure_client(client: httpx.Client | None, hostname: str = "") -> Iterator[httpx.Client]:
    if client is not None:
        yield client
        return
    # follow_redirects=False a propósito: las redirecciones se siguen a mano en `fetch` para
    # poder revalidar cada salto. Si httpx las siguiera solo, el primer 302 hacia
    # http://127.0.0.1 anularía todo lo anterior.
    with httpx.Client(
        timeout=DEFAULT_TIMEOUT, follow_redirects=False, verify=_contexto_tls(hostname)
    ) as owned:
        yield owned


def fetch(
    url: str,
    *,
    allowlist: frozenset[str] = DEFAULT_ALLOWLIST,
    headers: Mapping[str, str] | None = None,
    max_bytes: int = MAX_RESPONSE_BYTES,
    max_redirects: int = MAX_REDIRECTS,
    resolver: Resolver = _default_resolver,
    client: httpx.Client | None = None,
) -> bytes:
    """Descarga `url` aplicando todos los controles del módulo. Devuelve el cuerpo en bytes.

    `headers` permite a cada fuente añadir lo que necesite (la API del BOE, por ejemplo,
    responde 400 si no se le manda un `Accept` explícito). El `Host` no es negociable: lo
    pone el guardia, porque es la mitad del mecanismo de pinning.

    Lanza `UrlGuardError` si cualquier control falla, en la URL inicial o en una redirección.
    """
    # El contexto TLS se elige por el host de la URL **inicial**; si una redirección lleva a un
    # host con perfil distinto, se abre un cliente nuevo para ese salto (ver el bucle). Elegirlo
    # una sola vez haría que una redirección a un host heredado fallara sin explicación, que es
    # exactamente el fallo que costó una hora de depuración con el DOGC.
    with _ensure_client(client, urlsplit(url).hostname or "") as active_client:
        current_url = url
        for _ in range(max_redirects + 1):
            target = validate(current_url, allowlist=allowlist, resolver=resolver)
            request = _build_pinned_request(active_client, target, headers)
            response = active_client.send(request, stream=True, follow_redirects=False)
            try:
                if response.status_code in _REDIRECT_STATUS:
                    location = response.headers.get("location")
                    if not location:
                        raise UrlGuardError(
                            f"Redirección {response.status_code} sin cabecera Location"
                        )
                    # La Location se resuelve contra la URL con nombre, no contra la URL
                    # clavada a la IP: una Location relativa debe seguir colgando del host
                    # original, no de su dirección.
                    current_url = urljoin(target.url, location)
                    destino = urlsplit(current_url).hostname or ""
                    if client is None and destino in HOSTS_TLS_HEREDADO:
                        # Salto a un host que exige perfil heredado: se sigue a mano con un
                        # cliente propio para ese host, sin tocar el perfil de los demás.
                        return _seguir_con_perfil_propio(
                            current_url,
                            allowlist=allowlist,
                            headers=headers,
                            max_bytes=max_bytes,
                            max_redirects=max_redirects - 1,
                            resolver=resolver,
                        )
                    continue

                response.raise_for_status()
                return _read_capped(response, max_bytes)
            finally:
                response.close()

        raise TooManyRedirects(f"Más de {max_redirects} redirecciones desde {url!r}")


def _seguir_con_perfil_propio(
    url: str,
    *,
    allowlist: frozenset[str],
    headers: Mapping[str, str] | None,
    max_bytes: int,
    max_redirects: int,
    resolver: Resolver,
) -> bytes:
    """Reanuda `fetch` para un host con perfil TLS heredado, sin relajar nada de los demás."""
    return fetch(
        url,
        allowlist=allowlist,
        headers=headers,
        max_bytes=max_bytes,
        max_redirects=max_redirects,
        resolver=resolver,
    )
