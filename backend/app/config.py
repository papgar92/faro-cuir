"""Configuración de la aplicación, siempre vía variables de entorno (nunca secretos
hardcodeados). Ver `.env.example` para las variables soportadas."""

from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Hosts admisibles para Ollama (CLAUDE.md 6.9.2). Cerrada a propósito: la URL de Ollama es la
# **única excepción declarada** a la allowlist de `url_guard` (ADR 0006), y esa excepción solo
# es legítima mientras el destino sea local y fijo. `host.docker.internal` es el mismo host
# visto desde dentro de un contenedor, vía `extra_hosts` del compose.
_HOSTS_OLLAMA = frozenset({"127.0.0.1", "localhost", "::1", "host.docker.internal"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str
    # Raíz del archivo de documentos crudos (CLAUDE.md 6.5). Es configuración de despliegue,
    # por eso en `documento.ruta_almacen` se guarda la ruta relativa y no la absoluta: así
    # una fila no queda atada a la máquina donde se ingirió.
    almacen_root: Path = Path("data")
    # Secreto para hashear emails de suscriptores (CLAUDE.md 6.4). Sin valor por defecto a
    # propósito: `security/hashing.hash_email` falla cerrado si no está, en vez de guardar un
    # hash sin sal que sería reversible con un diccionario de direcciones.
    suscriptor_pepper: str | None = None

    # --- Fase 2 de la ingesta: descarga del texto íntegro (ADR 0011 y 0015) ---------------
    # Los dos frenos que exige la 6.2, y ninguno es decorativo: la fase 2 pide un documento
    # por norma, y un sumario del BOE trae del orden de 250.
    #
    # La pausa es la misma con la que se hizo la medición del ADR 0011 (436 normas, 0 errores
    # contra el BOE): no se baja sin volver a medir. Es cortesía con una fuente pública y freno
    # propio a la vez — sin ella, un bucle sobre el día entero es indistinguible de un ataque.
    fase2_pausa_segundos: float = 0.3
    # Tope por ejecución. Con 250 normas/día y este tope, un día normal cabe entero y el
    # atasco acumulado se drena en varias pasadas en vez de en una ráfaga de miles de
    # peticiones. **Es un tope, no una cuota**: lo que no entra hoy sigue en cola y entra
    # mañana, porque la cola es una consulta (`documento_texto_id IS NULL`) y no un estado que
    # haya que reponer.
    fase2_max_por_ejecucion: int = 500

    # --- Panel de revisión: el gate humano (ADR 0017) -----------------------------------
    # Sin valor por defecto y sin degradación posible: `security/panel.py` lanza si falta, con
    # el mismo criterio que `suscriptor_pepper`. Un panel que se abre solo porque nadie
    # configuró la contraseña es peor que un panel caído — es el único camino por el que una
    # detección se convierte en alerta publicable (regla de oro 4).
    panel_password_hash: str | None = None
    # Una hora. Es una sesión de trabajo de revisión, no una sesión de red social: caducar
    # pronto cuesta un login más y ahorra una sesión abierta en un portátil olvidado.
    panel_sesion_ttl_segundos: int = 3600
    # Techo de intentos de login por minuto, **global y sin IP** (6.4). Ver `CadenciaIntentos`.
    panel_intentos_por_minuto: int = 10

    # --- LLM (ADR 0008) -----------------------------------------------------------------
    # Ollama en local por defecto: sin clave, sin coste y sin cuota. La URL es nuestra, no
    # viene de ninguna fuente externa; ver la nota sobre url_guard en `llm/ollama.py`.
    llm_base_url: str = "http://127.0.0.1:11434"
    # Configurable a propósito: el modelo se elige según la máquina donde corra, y cambiarlo
    # no debe tocar código. Un modelo pequeño basta porque el esquema Pydantic descarta lo
    # que no cumpla el contrato (ADR 0002); la calidad se medirá con el gold set, no a ojo.
    llm_modelo: str = "qwen2.5:3b-instruct"
    # Generoso: en CPU sin GPU dedicada una extracción tarda bastante más que contra una API.
    llm_timeout_segundos: float = 180.0

    @field_validator("llm_base_url")
    @classmethod
    def _ollama_es_local(cls, valor: str) -> str:
        """La validación de arranque que exige 6.9.2, y que faltaba.

        6.9.2 dice literalmente que la URL de Ollama «es un destino local y fijo de
        configuración, no una URL que venga de una fuente. **Por eso mismo se valida al
        arrancar** (host de la config, esquema y puerto esperados)». La primera mitad estaba
        (`ollama.py` no la compone con nada dinámico); esta era la que faltaba.

        Sin ella, `LLM_BASE_URL` era una variable de entorno sin comprobar, y el compose la
        dejaba sobreescribible. Quien pudiera escribir el entorno —un `.env`, una variable de
        CI, un `docker run -e`— redirigía **toda** la salida del LLM a un host arbitrario: por
        ahí salen el prompt de sistema y el texto íntegro del boletín, y lo que respondiera ese
        host es lo que se valida contra Pydantic y acaba en `extraccion_json`. Es la única
        salida HTTP del proyecto sin allowlist, sin pin de IP y —al ser `http://`— sin TLS.

        **Falla al arrancar y no en la primera llamada**: un fallo de configuración que solo
        aparece cuando el worker lleva media hora ingiriendo es un fallo que se descubre en
        producción. Y falla cerrado: no hay degradación a "pues lo intento igual".

        Permitir un Ollama remoto **amplía la excepción del ADR 0006** y necesita su propio
        ADR, no un valor distinto en el entorno.
        """
        partes = urlsplit(valor)
        if partes.scheme not in ("http", "https"):
            raise ValueError(f"LLM_BASE_URL con esquema no admitido: {partes.scheme!r}")
        # `hostname` y no `netloc`: normaliza a minúsculas y descarta credenciales y puerto,
        # así que `http://evil.com@127.0.0.1:11434` no cuela por comparar la cadena entera.
        if partes.hostname not in _HOSTS_OLLAMA:
            raise ValueError(
                f"LLM_BASE_URL apunta a un host no local: {partes.hostname!r}. "
                f"Admitidos: {sorted(_HOSTS_OLLAMA)}. Un Ollama remoto amplía la excepción "
                "del ADR 0006 a la allowlist de url_guard y necesita su propio ADR."
            )
        if partes.username or partes.password:
            raise ValueError("LLM_BASE_URL no admite credenciales en la URL")
        if partes.path.rstrip("/"):
            raise ValueError(f"LLM_BASE_URL no admite ruta: {partes.path!r}")
        return valor


@lru_cache
def get_settings() -> Settings:
    return Settings()
