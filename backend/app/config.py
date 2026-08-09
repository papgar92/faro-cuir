"""Configuración de la aplicación, siempre vía variables de entorno (nunca secretos
hardcodeados). Ver `.env.example` para las variables soportadas."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


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


@lru_cache
def get_settings() -> Settings:
    return Settings()
