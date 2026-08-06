"""Proveedor LLM contra un Ollama local (ADR 0008).

Sin clave de API, sin coste y sin cuota. Para un proyecto que va a hacer cientos de
extracciones al construir el gold set, no tener cuota importa más que la calidad bruta del
modelo: el esquema Pydantic descarta lo que no cumpla el contrato (ADR 0002), así que un
modelo pequeño que falle a veces cuesta un reintento, no una extracción mala colada.

## Por qué esto NO pasa por `security/url_guard.py`

`url_guard` es la puerta única de salida HTTP del proyecto (ADR 0006) y rechaza a propósito
toda IP no global — loopback incluido. Este cliente iría directo contra `127.0.0.1:11434`,
así que url_guard lo bloquearía. **La excepción es correcta y hay que entender por qué:**

url_guard existe para URLs que **vienen de una fuente hostil**: los enlaces dentro de un
sumario, escritos por alguien que no somos nosotros. Su trabajo es impedir que un tercero
elija a dónde se conecta el worker. La URL de Ollama no cumple esa condición: la escribimos
nosotros en la configuración, no la propone nadie de fuera. Aplicarle url_guard no añadiría
seguridad, solo impediría el único destino que queremos.

Que la excepción quede acotada es lo que la hace aceptable: este módulo **solo** habla con
`settings.llm_base_url`, nunca con una URL derivada de un documento. Si algún día el destino
del LLM pudiera venir de contenido ingerido, esta nota deja de valer y hay que rehacerlo.
"""

from __future__ import annotations

import httpx

from app.config import get_settings
from app.llm.provider import LLMError, ProveedorLLM


class ProveedorOllama(ProveedorLLM):
    """Habla con la API de Ollama. Una instancia por proceso; el cliente se reutiliza."""

    def __init__(
        self,
        base_url: str | None = None,
        modelo: str | None = None,
        timeout: float | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        settings = get_settings()
        self._base_url = (base_url or settings.llm_base_url).rstrip("/")
        self._modelo = modelo or settings.llm_modelo
        self._timeout = timeout or settings.llm_timeout_segundos
        # Inyectable para poder testear sin un Ollama levantado.
        self._client = client

    @property
    def modelo(self) -> str:
        return self._modelo

    def completar(self, prompt_sistema: str, contenido: str) -> str:
        carga = {
            "model": self._modelo,
            "system": prompt_sistema,
            "prompt": contenido,
            # Una sola respuesta, no un flujo: aquí no hay nadie mirando cómo se escribe.
            "stream": False,
            # Le pide a Ollama que fuerce salida JSON. Es una ayuda, NO una garantía: la
            # validación contra el esquema sigue siendo la que decide (ADR 0002).
            "format": "json",
            "options": {
                # Determinismo dentro de lo posible: una extracción de hechos no debe variar
                # entre ejecuciones sobre el mismo documento, o deja de ser reproducible.
                "temperature": 0,
                "seed": 1,
            },
        }

        cliente = self._client or httpx.Client(timeout=self._timeout)
        try:
            respuesta = cliente.post(f"{self._base_url}/api/generate", json=carga)
            respuesta.raise_for_status()
            cuerpo = respuesta.json()
        except httpx.ConnectError as exc:
            raise LLMError(
                f"No hay ningún Ollama escuchando en {self._base_url}. "
                "Arráncalo con `ollama serve` y descarga el modelo con "
                f"`ollama pull {self._modelo}`."
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"Error hablando con Ollama: {exc}") from exc
        except ValueError as exc:
            raise LLMError(f"Ollama devolvió algo que no es JSON: {exc}") from exc
        finally:
            if self._client is None:
                cliente.close()

        texto = cuerpo.get("response")
        if not isinstance(texto, str):
            raise LLMError("la respuesta de Ollama no trae el campo 'response'")
        return texto
