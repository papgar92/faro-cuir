"""Tests de huella de contenido y rutas de almacén (CLAUDE.md 6.3 y 6.5)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.security import hashing
from app.security.hashing import UnsafeStoragePath

DIGEST = "a" * 64


def test_sha256_coincide_con_la_referencia() -> None:
    contenido = b"<sumario>Resolucion de ejemplo</sumario>"
    assert hashing.sha256_hex(contenido) == hashlib.sha256(contenido).hexdigest()


def test_el_hash_distingue_cambios_de_un_solo_byte() -> None:
    """Es la propiedad de la que depende el archivo verificable de la seccion 6.5."""
    antes = hashing.sha256_hex(b"se reconoce el derecho")
    despues = hashing.sha256_hex(b"se reconoce el derecho.")
    assert antes != despues


def test_la_ruta_se_reparte_en_dos_niveles(tmp_path: Path) -> None:
    digest = "0123456789abcdef" * 4
    ruta = hashing.storage_path(digest, ".xml", root=tmp_path)
    assert ruta == tmp_path / "01" / "23" / f"{digest}.xml"


def test_el_mismo_contenido_da_la_misma_ruta(tmp_path: Path) -> None:
    """Deduplicacion gratis: no es un extra, es consecuencia de derivar del hash."""
    contenido = b"<sumario/>"
    primera = hashing.storage_path(hashing.sha256_hex(contenido), ".xml", root=tmp_path)
    segunda = hashing.storage_path(hashing.sha256_hex(contenido), ".xml", root=tmp_path)
    assert primera == segunda


@pytest.mark.parametrize(
    "digest",
    [
        "../../../../etc/cron.d/pwn",
        "..\\..\\windows\\system32\\drivers\\etc\\hosts",
        "/etc/passwd",
        "C:\\Windows\\System32\\config\\SAM",
        "..%2f..%2fetc%2fpasswd",
        "....//....//etc/passwd",  # sobrevive a un saneado ingenuo que borre "../"
        f"{'a' * 64}\n../../etc/passwd",  # salto de linea: por que la regex ancla con \\A\\Z
        f"../../{'a' * 58}",
        "a" * 63,  # longitud incorrecta
        "a" * 65,
        "A" * 64,  # mayusculas: hexadecimal, pero no la forma canonica que emitimos
        "g" * 64,  # no es hexadecimal
        "",
        "a" * 64 + "\x00.php",  # byte nulo para truncar la extension
    ],
)
def test_rechaza_cualquier_digest_que_no_sea_un_sha256(digest: str, tmp_path: Path) -> None:
    """El titulo de un documento es texto hostil; jamas debe acabar siendo un nombre de fichero.

    Estos payloads no llegarian aqui si el flujo es correcto, precisamente porque el nombre se
    deriva del hash. El test fija que, si alguien cambia eso algun dia, la funcion se niega en
    vez de escribir donde le digan.
    """
    with pytest.raises(UnsafeStoragePath):
        hashing.storage_path(digest, ".xml", root=tmp_path)


@pytest.mark.parametrize("extension", [".php", ".sh", ".lnk", "xml", ".XML", "", ".xml.php"])
def test_rechaza_extensiones_fuera_de_la_lista_blanca(extension: str, tmp_path: Path) -> None:
    with pytest.raises(UnsafeStoragePath):
        hashing.storage_path(DIGEST, extension, root=tmp_path)


@pytest.mark.parametrize("extension", [".xml", ".pdf", ".html", ".txt"])
def test_acepta_las_extensiones_de_la_lista_blanca(extension: str, tmp_path: Path) -> None:
    ruta = hashing.storage_path(DIGEST, extension, root=tmp_path)
    assert ruta.suffix == extension


def test_la_ruta_siempre_queda_dentro_del_almacen(tmp_path: Path) -> None:
    ruta = hashing.storage_path(DIGEST, ".xml", root=tmp_path)
    assert ruta.resolve().is_relative_to(tmp_path.resolve())


def test_la_ruta_relativa_usa_separadores_posix() -> None:
    """Lo que se guarda en documento.ruta_almacen debe leerse igual desde Windows y Linux."""
    relativa = hashing.relative_storage_path(DIGEST, ".xml")
    assert relativa == f"aa/aa/{DIGEST}.xml"
    assert "\\" not in relativa


def test_la_ruta_relativa_tambien_valida_la_entrada() -> None:
    with pytest.raises(UnsafeStoragePath):
        hashing.relative_storage_path("../../etc/passwd", ".xml")
