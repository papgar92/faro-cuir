"""Autenticación del panel de revisión: el gate humano (regla de oro 4, ADR 0003 y 0017).

Este módulo es la **puerta única** de autenticación del proyecto, con el mismo criterio que
`url_guard` con el HTTP saliente y `xml_safe` con el XML: ningún router compara contraseñas ni
inventa su propia noción de sesión.

Cinco decisiones, todas razonadas en el ADR 0017 y resumidas aquí porque es donde se leen:

1. **No hay tabla de usuarios y no la va a haber.** Hay una credencial de revisión que vive en
   el entorno (`PANEL_PASSWORD_HASH`). Un proyecto sobre derechos LGTBI+ que guarda una tabla
   con las personas que revisan alertas trans crea justo el dato sensible que la 6.4 se dedica a
   no crear, y `cola_revision` ya decidió no registrar **quién** resuelve cada ítem. Cuando haya
   más de una persona revisando habrá que rehacer esto, y entonces será una decisión consciente
   con su ADR, no un efecto colateral de un `CREATE TABLE`.

2. **scrypt de la biblioteca estándar.** Sin dependencia nueva (coste 0 € y una cosa menos que
   auditar, sección 0 bis), con función de derivación lenta y con sal por credencial. La
   contraseña en claro **nunca** se guarda ni se registra, ni siquiera al fallar.

3. **Token de sesión opaco en cookie `HttpOnly`, no JWT ni `localStorage`.** Un JWT sin estado
   no se puede revocar, que es justo lo que hace falta cuando alguien cierra sesión o cuando se
   sospecha de un token; y `localStorage` es legible por cualquier script, así que un XSS en el
   panel se llevaría la sesión del gate humano. Es el mismo criterio que el `token_baja_opaco`
   de los suscriptores: aleatorio del generador criptográfico, sin nada derivable dentro.

4. **Las sesiones viven en memoria y solo se guarda su huella.** Reiniciar el backend obliga a
   entrar otra vez, y es un precio aceptable a cambio de no tener una segunda tabla con
   artefactos de autenticación. Se indexan por `sha256` del token: un volcado de memoria o un
   log accidental de la estructura no entrega una sesión usable, y la búsqueda no compara la
   cadena secreta.

5. **La cadencia de intentos no mira la IP, y no puede dejar fuera a quien sabe la contraseña.**
   La 6.4 prohíbe registrar IPs de quien consulta, y el limitador general (`rate_limit.py`) ya
   funciona sin persistirlas. Aquí el freno de fuerza bruta es un **cubo global**, sin clave por
   cliente — y solo lo gastan los intentos **fallidos**, comprobados después de verificar la
   contraseña. Un cubo global que se gastara antes de comprobar sería la forma de cerrarle el
   panel al revisor desde fuera, o sea de anular el gate; ver `CadenciaIntentos`, que lleva
   escrito por qué el orden importa.
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import logging
import secrets
import time

logger = logging.getLogger(__name__)


class PanelNoConfigurado(RuntimeError):
    """Falta `PANEL_PASSWORD_HASH`. Se falla cerrado: sin credencial no hay panel.

    Nunca se degrada a "pues que entre cualquiera": el panel es el único camino por el que una
    detección se convierte en alerta publicable (regla de oro 4), así que un panel sin
    autenticación es peor que un panel caído.
    """


class HashPanelInvalido(ValueError):
    """El hash configurado no tiene el formato esperado. También falla cerrado y ruidoso."""


# Parámetros de scrypt. `n=2**14` con `r=8` pide ~16 MB por derivación y tarda del orden de
# decenas de milisegundos en una máquina normal: suficiente para que probar contraseñas a
# ciegas sea caro y poco para que el revisor note el login. Van dentro del hash almacenado
# (no aquí como constantes de verificación) para poder subirlos mañana sin invalidar lo que ya
# hay generado — el hash lleva sus propios parámetros, como cualquier formato serio.
_ETIQUETA = "scrypt"
# **El separador es `:` y no `$`, y esto costó una tarde de depuración (2026-08-16).**
# El formato clásico de estos hashes usa `$`, pero este valor viaja en un `.env` que Docker
# Compose lee con **interpolación de variables**: `scrypt$16384$8$1$d923ee...$5fcc...` llega al
# contenedor convertido en `scrypt$16384$8$1$5fcc...`, porque compose sustituye `$d923ee...` por
# la cadena vacía al no existir esa variable. O sea que **la sal desaparece por el camino**, sin
# que nada avise, y el panel se queda entre un 401 imposible de explicar y un 500 al verificar.
# Se arregla en el formato y no en el `.env` (donde habría que escribir `$$`) porque el mismo
# fichero lo leen pydantic-settings, compose y una persona: el valor tiene que significar lo
# mismo para los tres. Ni la etiqueta, ni los parámetros, ni el hexadecimal contienen `:`.
_SEPARADOR = ":"
_N = 2**14
_R = 8
_P = 1
_LONGITUD_CLAVE = 32
_BYTES_SAL = 16

# Tope de sesiones vivas a la vez. Igual que el limitador de peticiones tiene tope de clientes
# en memoria: sin él, el propio control de acceso sería el vector de agotamiento de memoria.
# Con una credencial compartida, veinte sesiones son ya muchas más de las que este panel
# necesita.
_MAXIMO_SESIONES = 20


def generar_hash(password: str, *, sal: bytes | None = None) -> str:
    """Deriva el hash que va en `PANEL_PASSWORD_HASH`.

    Formato: `scrypt:n:r:p:<sal hex>:<clave hex>`. Los parámetros viajan dentro para que
    verificar no dependa de que las constantes de este módulo no hayan cambiado nunca. El
    separador **no es `$`** por lo que explica el comentario de `_SEPARADOR`: lo interpolaba
    Docker Compose y se comía la sal.

    `sal` solo se pasa en los tests, para poder comprobar la derivación contra un valor fijo.
    En uso real sale de `secrets`.
    """
    if not password:
        raise ValueError("La contraseña del panel no puede estar vacía.")
    sal = secrets.token_bytes(_BYTES_SAL) if sal is None else sal
    clave = hashlib.scrypt(
        password.encode("utf-8"), salt=sal, n=_N, r=_R, p=_P, dklen=_LONGITUD_CLAVE
    )
    return _SEPARADOR.join([_ETIQUETA, str(_N), str(_R), str(_P), sal.hex(), clave.hex()])


def verificar_password(password: str, *, hash_almacenado: str | None) -> bool:
    """¿Es esta la contraseña del panel? Comparación en tiempo constante.

    Lanza si no hay hash configurado o si el que hay no se puede interpretar. Deliberadamente
    **no** devuelve `False` en esos casos: un fallo de configuración que se presenta como
    "contraseña incorrecta" se depura durante horas, y peor aún, un hash corrupto dejaría el
    panel indistinguible de uno con la contraseña mal escrita.
    """
    if not hash_almacenado:
        raise PanelNoConfigurado(
            "PANEL_PASSWORD_HASH no está configurado; el panel de revisión no se abre sin él. "
            "Genera uno con: python -m scripts.generar_hash_panel"
        )
    try:
        if "$" in hash_almacenado:
            # Mensaje propio para el hash del formato viejo: sin esto, un `.env` traído de otra
            # máquina falla con un «expected 6, got 5» que no dice absolutamente nada.
            raise ValueError(
                "el hash usa el separador '$', que Docker Compose interpola y corrompe. "
                "Regenéralo con: python -m scripts.generar_hash_panel"
            )
        etiqueta, n, r, p, sal_hex, clave_hex = hash_almacenado.split(_SEPARADOR)
        if etiqueta != _ETIQUETA:
            raise ValueError(f"algoritmo no soportado: {etiqueta!r}")
        candidata = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(sal_hex),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(bytes.fromhex(clave_hex)),
        )
    except (ValueError, TypeError) as exc:
        # El mensaje no incluye el hash: aunque no sea la contraseña, es material de
        # autenticación y no tiene por qué acabar en un log.
        raise HashPanelInvalido(f"PANEL_PASSWORD_HASH no tiene un formato válido: {exc}") from exc
    return hmac.compare_digest(candidata, bytes.fromhex(clave_hex))


def _huella(token: str) -> str:
    """Cómo se indexa una sesión: por el sha256 del token, nunca por el token.

    El servidor no necesita poder leer los tokens vivos, solo reconocer uno cuando lo ve. Y
    guardar lo que no hace falta es cómo un volcado de memoria, una traza o un `repr` acaban
    entregando una sesión del gate humano.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class Sesiones:
    """Almacén de sesiones en memoria, con expiración y tope.

    Sin persistencia a propósito (ver la cabecera del módulo). Un reinicio del backend cierra
    todas las sesiones, que es el modo de fallo correcto para un panel de administración.
    """

    def __init__(self, *, ttl_segundos: int, maximo: int = _MAXIMO_SESIONES) -> None:
        self._ttl = ttl_segundos
        self._maximo = maximo
        self._vivas: dict[str, float] = {}

    def _purgar(self, ahora: float) -> None:
        for huella, expira in list(self._vivas.items()):
            if expira <= ahora:
                del self._vivas[huella]

    def crear(self) -> tuple[str, datetime.datetime]:
        """Devuelve el token en claro (única vez que existe) y cuándo caduca."""
        ahora = time.monotonic()
        self._purgar(ahora)
        if len(self._vivas) >= self._maximo:
            # Se cierra la más antigua en vez de rechazar el login. Rechazarlo dejaría al
            # revisor fuera por culpa de sesiones que quizá ya nadie usa, y este panel es el
            # único camino para aprobar una alerta.
            mas_antigua = min(self._vivas, key=lambda huella: self._vivas[huella])
            del self._vivas[mas_antigua]
            logger.warning("Tope de sesiones del panel alcanzado; se cierra la más antigua.")
        token = secrets.token_urlsafe(32)
        self._vivas[_huella(token)] = ahora + self._ttl
        caduca = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=self._ttl)
        return token, caduca

    def es_valida(self, token: str | None) -> bool:
        if not token:
            return False
        ahora = time.monotonic()
        self._purgar(ahora)
        return _huella(token) in self._vivas

    def cerrar(self, token: str | None) -> None:
        """Cierre de sesión real: el token deja de valer en el servidor.

        Borrar solo la cookie del navegador sería teatro — quien tuviera el token seguiría
        entrando. Esto es la mitad de la razón por la que no se usa un JWT sin estado.
        """
        if token:
            self._vivas.pop(_huella(token), None)

    def cerrar_todas(self) -> None:
        self._vivas.clear()

    def __len__(self) -> int:
        self._purgar(time.monotonic())
        return len(self._vivas)


class CadenciaIntentos:
    """Cubo de fichas global para los intentos **fallidos** de login. Sin IP, sin cliente.

    ## La corrección que costó la primera auditoría de este módulo

    La versión inicial gastaba una ficha **antes** de comprobar la contraseña y devolvía 429 con
    el cubo vacío. El `revisor-seguridad` lo señaló y tenía razón: eso convierte el freno de
    fuerza bruta en la forma de **anular el gate humano**. Cualquiera, sin credenciales y desde
    una sola dirección sin salirse del limitador general (60 pet./min), mantiene el cubo a cero
    indefinidamente, y entonces **la contraseña correcta tampoco entra**. El panel es el único
    camino por el que una detección llega a `alerta` (regla de oro 4), así que cerrarlo no es una
    molestia: es desactivar la única etapa que el proyecto declara obligatoria.

    Ahora el orden es el que evita ese fallo entero, no el que lo hace menos probable:

    1. **La contraseña se comprueba siempre**, haya fichas o no.
    2. **Si es correcta, se entra siempre.** No hay estado del servidor que pueda impedirlo.
    3. **Solo un intento fallido gasta ficha**, y solo un fallido con el cubo vacío da 429.

    O sea: quien tiene la contraseña no puede quedarse fuera nunca, y quien no la tiene se queda
    sin intentos. Un techo de intentos por minuto que además no es un bloqueo, porque el cubo se
    rellena solo.

    El precio: comprobar siempre significa derivar scrypt siempre, que cuesta ~50 ms y 16 MB. Por
    eso `verificar_password` se serializa con un cerrojo en `api/revision.py` — sin él, cien
    intentos a la vez son 1,6 GB de memoria y el control de acceso vuelve a ser el vector, esta
    vez de agotamiento en lugar de bloqueo.
    """

    def __init__(self, *, intentos: int, ventana_segundos: float) -> None:
        self._capacidad = float(intentos)
        self._ritmo = intentos / ventana_segundos
        self._fichas = float(intentos)
        self._ultimo = time.monotonic()

    def registrar_fallo(self) -> bool:
        """Anota un intento fallido. `False` si ya no quedaban fichas (o sea, toca 429).

        Se llama **después** de comprobar la contraseña y solo cuando ha fallado. Un login
        correcto no pasa por aquí: el uso legítimo del panel no compite con el freno pensado
        para quien adivina.
        """
        ahora = time.monotonic()
        self._fichas = min(self._capacidad, self._fichas + (ahora - self._ultimo) * self._ritmo)
        self._ultimo = ahora
        if self._fichas < 1.0:
            return False
        self._fichas -= 1.0
        return True

    def fallos_en_la_ventana(self) -> int:
        """Cuántos intentos fallidos lleva la ventana. Para el log agregado, sin identidades."""
        return round(self._capacidad - self._fichas)
