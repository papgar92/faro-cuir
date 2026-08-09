"""La URL de Ollama se valida al arrancar (CLAUDE.md 6.9.2).

Es el control que convierte la excepción del ADR 0006 en una excepción **acotada**. Sin él,
`LLM_BASE_URL` es una variable de entorno sin comprobar y la única salida HTTP del proyecto sin
allowlist apunta a donde diga el entorno.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings

_BASE = {"database_url": "postgresql+psycopg://x@localhost/x"}


def _settings(url: str) -> Settings:
    # `_env_file=None` para que un `.env` presente en la máquina no decida el resultado del
    # test: lo que se prueba es el validador, no el entorno de quien lo ejecuta.
    return Settings(**_BASE, llm_base_url=url, _env_file=None)  # type: ignore[call-arg]


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:11434",
        "http://localhost:11434",
        "http://host.docker.internal:11434",
        "https://127.0.0.1:11434",
        "http://127.0.0.1:11434/",
    ],
)
def test_acepta_los_destinos_locales(url: str) -> None:
    assert _settings(url).llm_base_url == url


@pytest.mark.parametrize(
    ("url", "motivo"),
    [
        ("http://ollama.example.com:11434", "host remoto: exfiltra el prompt y el boletín"),
        ("http://10.0.0.5:11434", "IP interna que no es la nuestra: SSRF a la red del host"),
        ("http://169.254.169.254", "metadatos de nube, el destino clásico de un SSRF"),
        ("file:///etc/passwd", "esquema no HTTP"),
        ("ftp://127.0.0.1", "esquema no HTTP"),
        # El que se cuela si se compara `netloc` en vez de `hostname`: la cadena contiene
        # "127.0.0.1" pero el host real es evil.com.
        ("http://127.0.0.1@evil.com:11434", "credenciales que disfrazan el host real"),
        ("http://127.0.0.1:11434/api/generate", "ruta: la compone `ollama.py`, no el entorno"),
    ],
)
def test_rechaza_lo_que_no_es_un_ollama_local(url: str, motivo: str) -> None:
    with pytest.raises(ValidationError):
        _settings(url), motivo


def test_falla_al_construir_y_no_en_la_primera_llamada() -> None:
    """Un fallo de configuración que solo aparece a media ingesta se descubre en producción."""
    with pytest.raises(ValidationError):
        _settings("http://evil.example.com:11434")
