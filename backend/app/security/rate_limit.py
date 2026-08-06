"""Rate limiting de la API pública (CLAUDE.md 6.8: "desde el principio, no al final").

La API no tiene autenticación —el contenido son boletines oficiales, que son públicos— así
que **cualquiera puede pedir lo que quiera tantas veces como quiera**. Sin un límite, la
defensa contra un cliente abusivo sería el tope de paginación y poco más.

## Por qué un limitador propio y no `slowapi`

`slowapi` haría esto mejor. Se descarta por proporción: son cuarenta líneas, el proyecto
corre en una instancia y añadir una dependencia (con su cadena transitiva) para esto va
contra "dependencias fijadas y auditadas" (6.8) sin comprar nada aquí.

## Limitaciones, que hay que decir en voz alta

- **Es por proceso.** Con varios workers de uvicorn o varias réplicas, el límite efectivo se
  multiplica por el número de procesos. Para un despliegue real con más de una instancia
  esto se sustituye por un contador en Redis, no se parchea.
- **Se reinicia con el proceso.** Un atacante que provoque un reinicio recupera su cuota.
- **No sustituye a un WAF ni a un límite de red.** Frena el abuso rutinario, no una
  denegación de servicio distribuida; para eso hace falta algo delante.

Está documentado así a propósito: un control a medias que se presenta como completo es peor
que no tenerlo, porque nadie vuelve a mirarlo.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field

from starlette.types import ASGIApp, Receive, Scope, Send

# Generoso para un humano leyendo la web, incómodo para un script que raspa. La API es de
# lectura y el contenido es público: el objetivo no es racionar el acceso sino evitar que un
# cliente descuidado tumbe la base de datos.
PETICIONES_POR_VENTANA = 60
VENTANA_SEGUNDOS = 60

# Tope de clientes distintos en memoria. Sin esto, el propio limitador es un vector de
# agotamiento de memoria: bastaría con rotar la IP de origen para hacer crecer el diccionario
# sin límite. Al llegar al tope se purga lo caducado y, si aún así no cabe, se deja pasar la
# petición en vez de bloquear a todo el mundo — fallar abierto es lo correcto aquí, porque
# este control protege de un descuido, no guarda un secreto.
MAX_CLIENTES = 10_000

# `/health` queda fuera: lo consulta el healthcheck del contenedor cada pocos segundos y
# limitarlo haría que Docker declarase el servicio caído. No expone datos.
RUTAS_EXENTAS = ("/health",)


@dataclass
class _Contador:
    """Ventana deslizante: los instantes de las peticiones recientes de un cliente.

    Deslizante y no fija porque una ventana fija permite el doble del límite a caballo entre
    dos ventanas (59 peticiones al final de una y 60 al principio de la siguiente).
    """

    marcas: deque[float] = field(default_factory=deque)

    def purgar(self, ahora: float) -> None:
        limite = ahora - VENTANA_SEGUNDOS
        while self.marcas and self.marcas[0] <= limite:
            self.marcas.popleft()


class RateLimiter:
    """Contadores en memoria. Separado del middleware para poder testearlo sin ASGI."""

    def __init__(
        self,
        peticiones: int = PETICIONES_POR_VENTANA,
        ventana: int = VENTANA_SEGUNDOS,
        max_clientes: int = MAX_CLIENTES,
    ) -> None:
        self.peticiones = peticiones
        self.ventana = ventana
        self.max_clientes = max_clientes
        self._clientes: dict[str, _Contador] = {}

    def _purgar_caducados(self, ahora: float) -> None:
        for clave in [c for c, cont in self._clientes.items() if not cont.marcas]:
            del self._clientes[clave]

    def permitir(self, cliente: str, ahora: float | None = None) -> tuple[bool, int]:
        """Devuelve (si se permite, segundos que faltan para poder reintentar)."""
        ahora = time.monotonic() if ahora is None else ahora

        contador = self._clientes.get(cliente)
        if contador is None:
            if len(self._clientes) >= self.max_clientes:
                self._purgar_caducados(ahora)
            if len(self._clientes) >= self.max_clientes:
                # Fallo abierto deliberado: ver la nota de MAX_CLIENTES.
                return True, 0
            contador = self._clientes[cliente] = _Contador()

        limite = ahora - self.ventana
        while contador.marcas and contador.marcas[0] <= limite:
            contador.marcas.popleft()

        if len(contador.marcas) >= self.peticiones:
            espera = int(contador.marcas[0] + self.ventana - ahora) + 1
            return False, max(espera, 1)

        contador.marcas.append(ahora)
        return True, 0


def _clave_de_cliente(scope: Scope) -> str:
    """IP de origen de la conexión.

    **No se lee `X-Forwarded-For`.** Es una cabecera que escribe el cliente: confiar en ella
    sin saber cuántos proxies de confianza hay delante permite que cualquiera se invente una
    IP distinta en cada petición y evite el límite por completo — y, de paso, envenene los
    logs. Cuando haya un proxy inverso real delante, la forma correcta es configurarlo con el
    número exacto de saltos de confianza (`ProxyHeadersMiddleware`), no leer la cabecera aquí.
    """
    cliente = scope.get("client")
    return cliente[0] if cliente else "desconocido"


class RateLimitMiddleware:
    def __init__(self, app: ASGIApp, limiter: RateLimiter | None = None) -> None:
        self.app = app
        self.limiter = limiter or RateLimiter()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path", "").rstrip("/") in RUTAS_EXENTAS:
            await self.app(scope, receive, send)
            return

        permitido, espera = self.limiter.permitir(_clave_de_cliente(scope))
        if permitido:
            await self.app(scope, receive, send)
            return

        cuerpo = b'{"detail":"Demasiadas peticiones. Intentalo de nuevo en un momento."}'
        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(cuerpo)).encode()),
                    # Decir cuándo se puede reintentar convierte un rechazo opaco en algo
                    # que un cliente correcto puede respetar por su cuenta.
                    (b"retry-after", str(espera).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": cuerpo})
