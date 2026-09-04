"""El archivo de la 6.5, sobre un almacén de objetos compatible con S3. ADR 0032.

**Esto no es una caché ni un respaldo: es el archivo.** Cuando está configurado, el almacén
remoto *sustituye* al disco local, y la garantía de la sección 6.5 —«el día X esto decía
exactamente esto», demostrable por el sha256— pasa a depender de él. Por eso este módulo repite
los tres controles que hacían falta en disco en vez de darlos por heredados:

1. **La clave del objeto se deriva del hash, nunca de un dato de la fuente** (6.3). Es la misma
   ruta relativa que `hashing.relative_storage_path` calcula para el disco, así que
   `documento.ruta_almacen` vale igual leída desde local o desde remoto y **migrar no reescribe
   ni una fila**. Se vuelve a validar aquí antes de tocar la red: un control que da por buena la
   salida de otro control deja de ser un control.
2. **El endpoint es configuración fija y se valida al arrancar**, con el mismo criterio que la
   URL de Ollama en 6.9.2: HTTPS, sin credenciales en la URL y sin ruta. Nunca se compone con
   nada dinámico.
3. **Se distingue «no está» de «no se puede llegar»** (ver `leer`). Confundirlos convertiría una
   caída de red en cientos de normas marcadas `ilegible`, que es exactamente el fallo mudo que
   prohíbe 6.9.6.

## Es la segunda excepción declarada a la allowlist de `url_guard` (6.2)

La primera es Ollama (ADR 0006). El criterio que las hace legítimas es el mismo y no se relaja:
**el destino sale de la configuración del despliegue, no de un documento**. `url_guard` existe
para las URLs que vienen de un sumario, que son las que un tercero controla. Aquí no hay ninguna
URL de fuente: la clave del objeto es un sha256 nuestro y el host es un literal de entorno
validado al arrancar.

Que hable `boto3` y no `httpx` es deliberado: firmar SigV4 a mano son sesenta líneas de HMAC
propias en el camino de escritura del archivo que sostiene el proyecto entero, y una biblioteca
de firma escrita para la ocasión es peor idea que una dependencia más.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from app.config import Settings, get_settings
from app.security import hashing

if TYPE_CHECKING:  # pragma: no cover - solo para el comprobador de tipos
    from mypy_boto3_s3.client import S3Client


class AlmacenRemotoNoConfigurado(RuntimeError):
    """Falta alguna variable del almacén remoto. Se falla cerrado, nunca se cae al disco.

    Degradar a local sería lo peor de los dos mundos: el worker parecería funcionar mientras
    escribe el archivo en el disco efímero de un runner que se destruye al terminar el job.
    """


class AlmacenRemotoCaido(RuntimeError):
    """No se pudo hablar con el almacén. **No** hereda de `OSError`, y eso es la decisión.

    `services/cuerpo.py` captura `OSError` y marca la norma como `ilegible` (7.2). Eso es lo
    correcto cuando el objeto no está —es un hecho sobre ese documento—, pero convertir una
    caída de red o una credencial caducada en «esta norma no se puede leer» marcaría cientos de
    normas por un problema que no es de ninguna de ellas, y el embudo lo contaría como
    cobertura perdida en vez de como avería. Al no ser `OSError`, esto sube y para la pasada.
    """


_cliente: S3Client | None = None
_cerrojo = threading.Lock()


def configurado(settings: Settings | None = None) -> bool:
    """¿Hay almacén remoto? Es lo que decide `services/archivo.py` entre disco y objetos."""
    ajustes = settings or get_settings()
    return bool(ajustes.almacen_s3_bucket)


def _exigir(valor: str | None, nombre: str) -> str:
    if not valor:
        raise AlmacenRemotoNoConfigurado(
            f"{nombre} no está configurado y ALMACEN_S3_BUCKET sí. El almacén remoto se "
            "configura entero o no se configura: no hay caída silenciosa al disco local."
        )
    return valor


def cliente(settings: Settings | None = None) -> S3Client:
    """El cliente S3, uno por proceso.

    Se cachea porque `boto3.client` abre un pool de conexiones y crear uno por documento
    convertiría una ingesta de 250 normas en 250 handshakes TLS. El cerrojo es por si algún día
    esto se llama desde dos hilos: `boto3` documenta que un cliente ya creado es seguro de
    compartir, pero crearlo no lo es.
    """
    global _cliente
    if _cliente is not None:
        return _cliente
    with _cerrojo:
        if _cliente is None:
            import boto3
            from botocore.config import Config

            ajustes = settings or get_settings()
            _cliente = boto3.client(
                "s3",
                endpoint_url=_exigir(ajustes.almacen_s3_endpoint, "ALMACEN_S3_ENDPOINT"),
                aws_access_key_id=_exigir(ajustes.almacen_s3_access_key, "ALMACEN_S3_ACCESS_KEY"),
                aws_secret_access_key=_exigir(
                    ajustes.almacen_s3_secret_key, "ALMACEN_S3_SECRET_KEY"
                ),
                region_name=ajustes.almacen_s3_region,
                config=Config(
                    # Tres reintentos con espera creciente. Un 503 puntual de un almacén de
                    # objetos es normal y no debería tirar una ingesta de media hora; lo que no
                    # se reintenta en bucle es un 403, que `standard` tampoco reintenta.
                    retries={"max_attempts": 3, "mode": "standard"},
                    connect_timeout=10,
                    read_timeout=60,
                    # Por encima de los hilos que usa la subida inicial (16 por defecto en
                    # `scripts/migrar_almacen.py`). El valor de fábrica de botocore es 10, y con
                    # más hilos que conexiones urllib3 empieza a descartar y rehacer conexiones
                    # avisando por un warning que es fácil no ver.
                    max_pool_connections=32,
                    # Las claves llevan `/` y son nuestras: no hace falta el modo virtual-host,
                    # que además obliga a que el bucket sea un subdominio válido.
                    s3={"addressing_style": "path"},
                ),
            )
    return _cliente


def reiniciar_cliente() -> None:
    """Tira el cliente cacheado. Solo para los tests: nada de producción cambia de credenciales."""
    global _cliente
    with _cerrojo:
        _cliente = None


def _bucket(settings: Settings | None = None) -> str:
    ajustes = settings or get_settings()
    return _exigir(ajustes.almacen_s3_bucket, "ALMACEN_S3_BUCKET")


def _clave(ruta_relativa: str) -> str:
    """Valida la ruta antes de convertirla en clave de objeto.

    Un almacén de objetos no tiene directorios, así que `..` no escapa de ningún sitio: aquí no
    hay path traversal que prevenir. Lo que se comprueba es lo otro, que sí importa —que la
    clave sea la que deriva del sha256 y no un valor que haya llegado de una fuente—, porque de
    eso depende que el objeto siga siendo localizable por su huella (6.3 y 6.5).
    """
    partes = ruta_relativa.split("/")
    esperada = None
    if len(partes) == 3:
        nombre = partes[2]
        digest, _, extension = nombre.rpartition(".")
        if digest and extension:
            try:
                esperada = hashing.relative_storage_path(digest, f".{extension}")
            except hashing.UnsafeStoragePath:
                esperada = None
    if esperada != ruta_relativa:
        raise hashing.UnsafeStoragePath(
            f"La ruta almacenada no se deriva de un sha256: {ruta_relativa!r}"
        )
    return ruta_relativa


def escribir(ruta_relativa: str, contenido: bytes) -> None:
    """Sube el contenido con la clave derivada del hash.

    **Se sube sin comprobar antes si existe**, al revés que en disco. No es un descuido: la
    clave *es* el sha256 del contenido, así que un objeto con esa clave solo puede tener esos
    bytes y sobrescribirlo es idempotente por construcción. Un `PUT` de S3 es atómico, así que
    tampoco hace falta el temporal + `os.replace` que necesita un sistema de ficheros. Y de
    paso ahorra una transacción de clase B por documento, que en el plan gratuito de B2 son
    2.500 al día y las gasta antes la lectura que la escritura.
    """
    try:
        cliente().put_object(Bucket=_bucket(), Key=_clave(ruta_relativa), Body=contenido)
    except Exception as exc:  # noqa: BLE001 - se reetiqueta y se relanza, no se traga
        raise AlmacenRemotoCaido(f"No se pudo escribir {ruta_relativa!r}: {exc}") from exc


def listar_claves() -> set[str]:
    """Todas las claves que ya hay en el bucket.

    Solo la usa `scripts/migrar_almacen.py`, para poder reanudar una subida de 84.000 ficheros
    sin volver a subirlos. **El pipeline nunca enumera el almacén**: llega a un documento por su
    `ruta_almacen`, que deriva del hash, y un almacén que hay que recorrer para encontrar algo
    es un almacén cuyo índice se ha perdido.
    """
    claves: set[str] = set()
    try:
        paginador = cliente().get_paginator("list_objects_v2")
        for pagina in paginador.paginate(Bucket=_bucket()):
            claves.update(objeto["Key"] for objeto in pagina.get("Contents", []) if "Key" in objeto)
    except Exception as exc:  # noqa: BLE001 - se reetiqueta y se relanza, no se traga
        raise AlmacenRemotoCaido(f"No se pudo listar el almacén: {exc}") from exc
    return claves


def leer(ruta_relativa: str) -> bytes:
    """Devuelve el contenido archivado, o distingue por qué no puede.

    - **No está** → `FileNotFoundError`, que es `OSError`: `cuerpo.py` lo trata igual que un
      fichero que falta en disco y la norma cae a `ilegible`, reintentable en cada pasada (7.2).
    - **Cualquier otra cosa** → `AlmacenRemotoCaido`, que no es `OSError` y para la pasada.
    """
    from botocore.exceptions import ClientError

    clave = _clave(ruta_relativa)
    try:
        respuesta = cliente().get_object(Bucket=_bucket(), Key=clave)
        return respuesta["Body"].read()
    except ClientError as exc:
        codigo = str(exc.response.get("Error", {}).get("Code", ""))
        if codigo in ("NoSuchKey", "404", "NotFound"):
            raise FileNotFoundError(f"No está en el almacén remoto: {ruta_relativa!r}") from exc
        raise AlmacenRemotoCaido(f"No se pudo leer {ruta_relativa!r}: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 - se reetiqueta y se relanza, no se traga
        raise AlmacenRemotoCaido(f"No se pudo leer {ruta_relativa!r}: {exc}") from exc
