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
                # **Tope de generación. Sin esto la generación es ILIMITADA**, y eso fue lo que
                # dejó al extractor cinco días quemando tres núcleos para tirar el 100 % de los
                # resultados: el modelo no terminaba el JSON dentro del timeout, la petición se
                # cortaba, la norma volvía a la cola y vuelta a empezar. Un fallo que no rompe
                # nada visiblemente es el peor de todos (6.9.6).
                #
                # **Dimensionado con las 22 extracciones que sí se completaron**, no a ojo: su
                # JSON mide 430 caracteres de mediana, 939 en el p90 y **2.086 el mayor**, o sea
                # unos 835 tokens en el peor caso observado. 1536 deja casi el doble de margen.
                #
                # El riesgo de quedarse corto está acotado y es ruidoso: un JSON truncado no
                # valida contra el esquema Pydantic y la extracción se descarta (6.9.3), que es
                # exactamente lo que debe pasar. Si algún día se ve descartar por esquema
                # documentos con muchos artículos, este número es el primer sitio donde mirar.
                #
                # **Y NO SE PUEDE SUBIR LIBREMENTE: este tope y `llm_timeout_segundos` están
                # atados.** El tiempo de una extracción lo manda lo que el modelo GENERA, no el
                # documento de entrada: medido el 2026-08-28 en esta máquina (i5-10310U, CPU),
                # unos **3,2 tokens/s**. Con eso, 1536 tokens son ~480 s y caben en el timeout de
                # 600 s; **2048 serían ~640 s y volverían a caducar todas las peticiones**, que es
                # justo el bucle que este parámetro vino a romper. Al tocar uno de los dos hay que
                # recalcular el otro: num_predict / tokens_por_segundo < timeout.
                "num_predict": 1536,
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
