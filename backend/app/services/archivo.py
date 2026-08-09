"""Escritura en el almacén de documentos crudos. CLAUDE.md 6.5 y ADR 0005.

**Una sola función escribe en el almacén, y es esta.** Vivía dentro de `ingesta.py` cuando el
único contenido archivable era el sumario del día; con el ADR 0015 también se archivan los
cuerpos de las normas, y dejarla allí habría obligado a que el servicio de la fase 2 la
importara de un módulo que no tiene nada que ver con él o —lo que siempre acaba pasando—
a que escribiera la suya.

Que sea una es lo que hace que la garantía de 6.5 sea comprobable de un vistazo: la ruta se
deriva **siempre** del hash (nunca de un dato de la fuente, 6.3) y la escritura es **siempre**
atómica. El mismo criterio que `url_guard` con el HTTP y `xml_safe` con el XML.
"""

from __future__ import annotations

import os
from pathlib import Path

from app.security import hashing


def archivar(contenido: bytes, digest: str, *, almacen_root: Path, extension: str = ".xml") -> str:
    """Escribe el contenido crudo en el almacén y devuelve su ruta relativa.

    Si el fichero ya existe no se reescribe: mismo hash es mismo contenido, así que
    reescribirlo solo añadiría el riesgo de dejarlo a medias sin ganar nada. Eso hace además
    que la deduplicación sea gratis — dos normas que republiquen el mismo texto comparten
    fichero, y cada una conserva su propia fila con su propio sello.
    """
    ruta_relativa = hashing.relative_storage_path(digest, extension)
    destino = hashing.storage_path(digest, extension, root=almacen_root)

    if destino.exists():
        return ruta_relativa

    destino.parent.mkdir(parents=True, exist_ok=True)
    # Escritura atómica: primero un temporal en el mismo directorio y luego `os.replace`, que
    # es atómico dentro del mismo sistema de ficheros. Si el proceso muere a mitad, el almacén
    # nunca queda con un fichero truncado cuyo nombre promete un sha256 que su contenido ya no
    # cumple — y eso rompería justo la propiedad que hace útil al archivo de la sección 6.5.
    temporal = destino.with_name(f"{destino.name}.{os.getpid()}.tmp")
    temporal.write_bytes(contenido)
    os.replace(temporal, destino)
    return ruta_relativa


def leer(ruta_relativa: str, *, almacen_root: Path) -> bytes:
    """Lee del almacén un contenido ya archivado.

    Existe para que la fase 2 pueda reevaluar el prefiltro **sin volver a la red** (ADR 0015):
    subir `VERSION_VOCABULARIO` reevalúa cientos de normas leyendo de disco, no pidiéndole otra
    vez el día entero al BOE.

    La ruta viene de `documento.ruta_almacen`, que la escribió `archivar` derivándola del hash;
    aun así se vuelve a validar contra la raíz antes de abrir. Un control que da por buena la
    salida de otro control deja de ser un control: si alguien llegara a escribir esa columna
    por otra vía, esto sigue impidiendo leer fuera del almacén.
    """
    root = almacen_root.resolve()
    destino = (almacen_root / ruta_relativa).resolve()
    if not destino.is_relative_to(root):
        raise hashing.UnsafeStoragePath(
            f"La ruta almacenada se sale del almacén: {ruta_relativa!r}"
        )
    return destino.read_bytes()
