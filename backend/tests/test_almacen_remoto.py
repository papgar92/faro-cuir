"""El archivo de la 6.5 cuando vive en un bucket. ADR 0032.

Lo que se prueba aquí no es «boto3 sube ficheros» —eso lo prueba boto3— sino las cuatro cosas
que el proyecto no se puede permitir que cambien al mover el archivo de sitio:

1. Que **por defecto no cambia nada**: sin bucket configurado, el archivo sigue en disco.
2. Que la ruta que se guarda en `documento.ruta_almacen` es **la misma cadena** en los dos
   destinos. Si no lo fuera, migrar exigiría reescribir 84.000 filas.
3. Que la clave del objeto se deriva del sha256 y **lo que no derive no llega a la red** (6.3).
4. Que «no está» y «no se puede llegar» siguen siendo hechos distintos (7.2 y 6.9.6).
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import Any

import pytest
from botocore.exceptions import ClientError
from pydantic import ValidationError

from app.config import Settings
from app.security.hashing import UnsafeStoragePath
from app.services import almacen_remoto, archivo

_BASE = {"database_url": "postgresql+psycopg://x@localhost/x"}
_CONTENIDO = b"<xml>lo que publico el boletin aquel dia</xml>"
_DIGEST = hashlib.sha256(_CONTENIDO).hexdigest()
_RUTA = f"{_DIGEST[:2]}/{_DIGEST[2:4]}/{_DIGEST}.xml"


class _FakeS3:
    """El almacén de objetos, con la superficie exacta que usa `almacen_remoto` y ni una más."""

    def __init__(self) -> None:
        self.objetos: dict[tuple[str, str], bytes] = {}
        self.caido = False

    def put_object(self, *, Bucket: str, Key: str, Body: bytes) -> dict[str, Any]:  # noqa: N803
        if self.caido:
            raise ClientError({"Error": {"Code": "InternalError"}}, "PutObject")
        self.objetos[(Bucket, Key)] = Body
        return {}

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:  # noqa: N803
        if self.caido:
            raise ClientError({"Error": {"Code": "InternalError"}}, "GetObject")
        try:
            cuerpo = self.objetos[(Bucket, Key)]
        except KeyError:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject") from None
        return {"Body": io.BytesIO(cuerpo)}


def _ajustes(**extra: Any) -> Settings:
    # `_env_file=None` por lo mismo que en `test_config_llm_url.py`: lo que se prueba es el
    # código, no el `.env` de la máquina de quien lance la suite.
    return Settings(**_BASE, **extra, _env_file=None)  # type: ignore[call-arg]


@pytest.fixture
def bucket(monkeypatch: pytest.MonkeyPatch) -> _FakeS3:
    """Deja el almacén remoto configurado y devuelve el bucket falso que hay detrás."""
    falso = _FakeS3()
    ajustes = _ajustes(
        almacen_s3_bucket="archivo-farocuir",
        almacen_s3_endpoint="https://s3.eu-central-003.backblazeb2.com",
        almacen_s3_access_key="clave",
        almacen_s3_secret_key="secreto",
    )
    monkeypatch.setattr(almacen_remoto, "get_settings", lambda: ajustes)
    monkeypatch.setattr(almacen_remoto, "cliente", lambda *_, **__: falso)
    return falso


def test_por_defecto_el_archivo_sigue_en_disco(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sin bucket no hay cambio de comportamiento: es lo que corre en local y en los tests."""
    monkeypatch.setattr(almacen_remoto, "get_settings", lambda: _ajustes())

    ruta = archivo.archivar(_CONTENIDO, _DIGEST, almacen_root=tmp_path)

    assert not almacen_remoto.configurado()
    assert (tmp_path / ruta).read_bytes() == _CONTENIDO


def test_con_bucket_el_archivo_va_al_bucket_y_no_al_disco(tmp_path: Path, bucket: _FakeS3) -> None:
    """No es una réplica ni una caché: es el archivo, y solo está en un sitio.

    Escribir también en disco sería peor que no escribir: en un runner de Actions ese disco se
    destruye al acabar el job, así que quedaría una copia que parece un respaldo y no lo es.
    """
    ruta = archivo.archivar(_CONTENIDO, _DIGEST, almacen_root=tmp_path)

    assert bucket.objetos == {("archivo-farocuir", ruta): _CONTENIDO}
    assert list(tmp_path.iterdir()) == []
    assert archivo.leer(ruta, almacen_root=tmp_path) == _CONTENIDO


def test_la_ruta_guardada_es_la_misma_en_disco_y_en_el_bucket(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Lo que hace que migrar el almacén no reescriba ni una fila de `documento`."""
    monkeypatch.setattr(almacen_remoto, "get_settings", lambda: _ajustes())
    en_disco = archivo.archivar(_CONTENIDO, _DIGEST, almacen_root=tmp_path)

    falso = _FakeS3()
    ajustes = _ajustes(
        almacen_s3_bucket="archivo-farocuir",
        almacen_s3_endpoint="https://s3.example.com",
        almacen_s3_access_key="clave",
        almacen_s3_secret_key="secreto",
    )
    monkeypatch.setattr(almacen_remoto, "get_settings", lambda: ajustes)
    monkeypatch.setattr(almacen_remoto, "cliente", lambda *_, **__: falso)
    en_objetos = archivo.archivar(_CONTENIDO, _DIGEST, almacen_root=tmp_path)

    assert en_disco == en_objetos == _RUTA


@pytest.mark.parametrize(
    ("ruta", "motivo"),
    [
        ("../../etc/passwd", "ni siquiera tiene forma de ruta de almacén"),
        ("aa/bb/no-es-un-hash.xml", "el nombre no es un sha256"),
        (f"zz/zz/{_DIGEST}.xml", "los directorios no son los que derivan del hash"),
        (f"{_DIGEST[:2]}/{_DIGEST[2:4]}/{_DIGEST}.sh", "extensión fuera de la lista blanca"),
        (
            f"{_DIGEST[:2]}/{_DIGEST[2:4]}/{_DIGEST.upper()}.xml",
            "un sha256 hexadecimal es en minúsculas",
        ),
    ],
)
def test_lo_que_no_deriva_de_un_sha256_no_llega_a_la_red(
    ruta: str, motivo: str, bucket: _FakeS3
) -> None:
    """En un bucket no hay `..` que escapar, pero sí una propiedad que perder.

    Si la clave dejara de ser la que deriva del hash, el objeto seguiría estando pero ya no
    sería localizable por su huella, y con eso se cae la garantía entera de la 6.5.
    """
    with pytest.raises(UnsafeStoragePath):
        almacen_remoto.leer(ruta), motivo
    assert bucket.objetos == {}


def test_un_objeto_que_no_esta_es_un_fichero_que_falta(bucket: _FakeS3) -> None:
    """`FileNotFoundError` es `OSError`, así que `cuerpo.py` la marca `ilegible` como siempre."""
    with pytest.raises(FileNotFoundError) as fallo:
        almacen_remoto.leer(_RUTA)

    assert isinstance(fallo.value, OSError)


def test_una_caida_del_almacen_no_convierte_normas_en_ilegibles(bucket: _FakeS3) -> None:
    """La distinción que evita que una avería de red se cuente como cobertura perdida (7.2).

    `cuerpo.py` captura `OSError` para marcar `ilegible`. Si esto lo fuera, un 500 del almacén
    marcaría de golpe todas las normas de la pasada por un problema que no es de ninguna.
    """
    bucket.objetos[("archivo-farocuir", _RUTA)] = _CONTENIDO
    bucket.caido = True

    with pytest.raises(almacen_remoto.AlmacenRemotoCaido) as fallo:
        almacen_remoto.leer(_RUTA)

    assert not isinstance(fallo.value, OSError)


def test_la_configuracion_a_medias_falla_cerrada(monkeypatch: pytest.MonkeyPatch) -> None:
    """Con bucket pero sin credenciales no se cae al disco: se para y se dice."""
    monkeypatch.setattr(
        almacen_remoto, "get_settings", lambda: _ajustes(almacen_s3_bucket="archivo-farocuir")
    )
    almacen_remoto.reiniciar_cliente()

    assert almacen_remoto.configurado()
    with pytest.raises(almacen_remoto.AlmacenRemotoNoConfigurado):
        almacen_remoto.cliente()


@pytest.mark.parametrize(
    ("endpoint", "motivo"),
    [
        ("http://s3.example.com", "sin TLS: por ahí van el archivo y la credencial que lo firma"),
        ("https://clave:secreta@s3.example.com", "credenciales en la URL acaban en un log"),
        ("https://s3.example.com/bucket", "con ruta el endpoint pasa a ser componible"),
        ("https://", "sin host"),
    ],
)
def test_el_endpoint_se_valida_al_arrancar(endpoint: str, motivo: str) -> None:
    """La segunda excepción declarada a `url_guard` (6.2) tiene que estar igual de acotada."""
    with pytest.raises(ValidationError):
        _ajustes(almacen_s3_endpoint=endpoint), motivo


def test_sin_endpoint_la_configuracion_es_valida() -> None:
    """El despliegue local no configura nada de esto y tiene que seguir arrancando."""
    assert _ajustes().almacen_s3_endpoint is None
