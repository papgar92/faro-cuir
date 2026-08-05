"""Huella de contenido y nombres de fichero seguros: CLAUDE.md 6.3 y 6.5.

Dos responsabilidades que van juntas a propósito:

1. **La huella del archivo íntegro (6.5).** De cada documento ingerido se guarda el sha256
   de su contenido exacto. Eso convierte el almacén en un archivo verificable de lo que
   realmente se publicó: si mañana una norma se desindexa o se reescribe sin registro
   público, el hash demuestra qué decía el día que se ingirió.

2. **El nombre del fichero (6.3).** El nombre en disco se **deriva del hash**, nunca de un
   valor que venga de la fuente. Un título como
   `../../../../etc/cron.d/pwn` o `..\\..\\windows\\system32\\x` es texto perfectamente
   válido dentro de un XML, y usarlo como nombre de archivo es escritura arbitraria en el
   sistema de ficheros. Derivar del hash elimina la clase de bug entera en vez de intentar
   sanear cadenas hostiles una por una — sanear es una lista negra, y las listas negras
   fallan.

El hash es además la razón de que la deduplicación sea gratis: el mismo contenido produce
la misma ruta.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path, PurePosixPath

# Un sha256 en hexadecimal y nada más. Anclado en ambos extremos: sin `\A`/`\Z` (o `^`/`$`
# con fullmatch) una cadena como "../../etc/passwd\n<64 hex>" podría colarse aprovechando
# que `$` en Python también casa justo antes de un salto de línea final.
_SHA256_HEX = re.compile(r"\A[0-9a-f]{64}\Z")

# Extensiones que el proyecto llega a almacenar. Lista blanca cerrada: lo que no está,
# no se guarda. Evita escribir un `.php`, `.sh` o `.lnk` en un directorio que algún día
# sirva alguien por HTTP.
ALLOWED_EXTENSIONS: frozenset[str] = frozenset({".xml", ".pdf", ".html", ".txt"})


class UnsafeStoragePath(ValueError):
    """El nombre pedido no es derivable de forma segura. Nunca se intenta 'arreglarlo'."""


def sha256_hex(content: bytes) -> str:
    """Huella del contenido tal cual se descargó, sin normalizar ni reformatear.

    Importa que sea el byte exacto recibido: si se normalizara (espacios, encoding, orden de
    atributos), el hash dejaría de probar qué se publicó y pasaría a probar qué entendimos
    nosotros, que es justo lo que no sirve como archivo verificable.
    """
    return hashlib.sha256(content).hexdigest()


def storage_path(digest: str, extension: str, *, root: Path) -> Path:
    """Devuelve la ruta de almacén de un documento a partir de su sha256.

    El resultado es `<root>/ab/cd/abcd...<ext>`. Los dos niveles de subdirectorio existen
    porque un único directorio con cientos de miles de ficheros degrada el rendimiento de
    casi cualquier sistema de ficheros; los dos primeros bytes del hash reparten uniforme.

    Lanza `UnsafeStoragePath` si el digest o la extensión no son exactamente lo esperado.
    """
    if not _SHA256_HEX.fullmatch(digest):
        # Deliberadamente no se sanea ni se recorta: si esto no es un sha256, algo ha ido mal
        # aguas arriba y seguir adelante solo serviría para esconderlo.
        raise UnsafeStoragePath(f"El digest no es un sha256 hexadecimal válido: {digest!r}")

    if extension not in ALLOWED_EXTENSIONS:
        raise UnsafeStoragePath(
            f"Extensión no permitida: {extension!r} (permitidas: {sorted(ALLOWED_EXTENSIONS)})"
        )

    candidate = root / digest[:2] / digest[2:4] / f"{digest}{extension}"

    # Cinturón y tirantes. Con un digest ya validado contra la regex esto no puede fallar,
    # pero se comprueba igual: si alguien relaja la validación de arriba en el futuro, este
    # control sigue impidiendo que se escriba fuera del almacén. Los controles de seguridad
    # no deberían depender de que otro control siga siendo correcto.
    resolved_root = root.resolve()
    if not candidate.resolve().is_relative_to(resolved_root):
        raise UnsafeStoragePath(f"La ruta calculada se sale del almacén: {candidate!r}")

    return candidate


def relative_storage_path(digest: str, extension: str) -> str:
    """La misma ruta, relativa y en formato POSIX, para guardarla en `documento.ruta_almacen`.

    En base de datos se guarda relativa a propósito: la raíz del almacén es configuración del
    despliegue (cambia entre local, Docker y CI) y meterla en la fila ataría los datos a una
    máquina concreta. Y en POSIX para que la misma fila valga leída desde Windows o Linux.
    """
    path = storage_path(digest, extension, root=Path("."))
    return str(PurePosixPath(*path.relative_to(Path(".")).parts))
