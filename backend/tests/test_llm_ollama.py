"""Tests del proveedor Ollama, con transporte simulado (no hace falta Ollama levantado)."""

from __future__ import annotations

import json

import httpx
import pytest

from app.llm.ollama import ProveedorOllama
from app.llm.provider import LLMError, extraer

EXTRACCION = {
    "norma_afectada": "Orden 45/2023",
    "organo_emisor": None,
    "ambito": "sanitario",
    "articulos": [{"identificador": "art. 7.2", "texto_nuevo": "nuevo texto"}],
}


def _cliente(handler) -> httpx.Client:  # type: ignore[no-untyped-def]
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_extrae_de_punta_a_punta_contra_un_ollama_simulado() -> None:
    def handler(peticion: httpx.Request) -> httpx.Response:
        assert peticion.url.path == "/api/generate"
        enviado = json.loads(peticion.content)
        assert enviado["stream"] is False
        assert enviado["format"] == "json"
        # Determinismo: una extracción de hechos no puede variar entre ejecuciones.
        assert enviado["options"]["temperature"] == 0
        return httpx.Response(200, json={"response": json.dumps(EXTRACCION)})

    proveedor = ProveedorOllama(modelo="modelo-test", client=_cliente(handler))
    resultado = extraer(proveedor, "documento del boletín")

    assert resultado.extraccion.norma_afectada == "Orden 45/2023"
    assert resultado.modelo == "modelo-test"


def test_el_prompt_y_el_documento_delimitado_llegan_separados() -> None:
    """El contenido no confiable viaja en `prompt`; las reglas, en `system`."""
    capturado: dict[str, str] = {}

    def handler(peticion: httpx.Request) -> httpx.Response:
        capturado.update(json.loads(peticion.content))
        return httpx.Response(200, json={"response": json.dumps(EXTRACCION)})

    extraer(ProveedorOllama(client=_cliente(handler)), "texto no confiable")

    assert "NO CONFIABLE" in capturado["system"]
    assert "texto no confiable" in capturado["prompt"]


def test_sin_ollama_levantado_el_error_dice_que_hacer() -> None:
    """Un fallo de arranque debe explicarse solo: es el primer tropiezo de quien retome esto."""

    def handler(peticion: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with pytest.raises(LLMError, match="ollama pull"):
        ProveedorOllama(client=_cliente(handler)).completar("sistema", "contenido")


@pytest.mark.parametrize(
    "respuesta",
    [
        httpx.Response(500, text="boom"),
        httpx.Response(200, text="no soy json"),
        httpx.Response(200, json={"otra_cosa": 1}),
    ],
)
def test_una_respuesta_rara_de_ollama_no_se_interpreta(respuesta: httpx.Response) -> None:
    with pytest.raises(LLMError):
        ProveedorOllama(client=_cliente(lambda _: respuesta)).completar("sistema", "contenido")


def test_un_veredicto_del_modelo_se_descarta_tambien_por_esta_via() -> None:
    """La defensa del ADR 0002 no depende del proveedor: vive en la validación."""

    def handler(peticion: httpx.Request) -> httpx.Response:
        manipulada = {**EXTRACCION, "clasificacion": "retroceso"}
        return httpx.Response(200, json={"response": json.dumps(manipulada)})

    with pytest.raises(LLMError):
        extraer(ProveedorOllama(client=_cliente(handler)), "documento")
