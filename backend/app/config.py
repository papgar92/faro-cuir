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

    # --- Almacén remoto de objetos, compatible con S3 (ADR 0032) --------------------------
    # Vacío = archivo en disco, que es lo que corre en local y en los tests. Con bucket, el
    # archivo pasa a vivir en el almacén de objetos y `almacen_root` deja de usarse: no es una
    # caché ni una réplica, es el mismo archivo de la 6.5 en otro sitio. Se configura entero o
    # no se configura — `services/almacen_remoto.py` falla cerrado si falta una pieza, porque
    # caer al disco sin avisar en un runner efímero sería escribir el archivo en la basura.
    almacen_s3_bucket: str | None = None
    almacen_s3_endpoint: str | None = None
    almacen_s3_access_key: str | None = None
    almacen_s3_secret_key: str | None = None
    # "auto" vale para Backblaze B2 y para Cloudflare R2, que ignoran la región; un S3 de AWS
    # de verdad querría la suya. No hay razón para adivinarla desde el endpoint.
    almacen_s3_region: str = "auto"
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

    # --- Versionado: el texto anterior desde el consolidado (ADR 0018) -------------------
    # Los mismos dos frenos de la 6.2, con números distintos porque el tráfico es distinto: un
    # consolidado es un documento grande (la Ley 2/2016 de Madrid son 277 KB; el Estatuto de los
    # Trabajadores, 1,5 MB) y las candidatas son poquísimas — solo normas que tocan la watchlist,
    # del orden de una entre cientos en el corpus medido. Por eso la pausa es larga y el tope
    # pequeño: no hay ninguna prisa y sí una fuente pública que no conviene castigar.
    versionado_pausa_segundos: float = 1.0
    # Tope por ejecución, no cuota: lo que no entra hoy sigue en cola y entra mañana, porque la
    # cola es una consulta (¿hay ya filas de `version_norma` para esta pareja?) y no un estado.
    versionado_max_por_ejecucion: int = 20

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
    # **Recalibrado el 2026-08-28 de 180 a 600 con datos de una tanda real, y el 180 era un
    # error de calibración, no una elección conservadora.** La extracción medida son 133,9 s de
    # media (ADR 0011), así que un timeout de 180 s deja fuera cualquier documento por encima de
    # la media: en la primera tanda larga del extractor, **22 de 43 extracciones (el 51 %) se
    # descartaron con «Error hablando con Ollama: timed out»**.
    #
    # Lo peor de ese fallo es que **no rompe nada visiblemente**: sin fila, la norma vuelve sola
    # a la cola (6.9.3), así que el worker parecía avanzar mientras reintentaba en bucle las
    # mismas normas. Un margen del 34 % sobre una media medida no es margen; 600 s son 4,5 veces
    # la media y absorben la cola larga de documentos grandes.
    llm_timeout_segundos: float = 600.0

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

    @field_validator("almacen_s3_endpoint")
    @classmethod
    def _endpoint_del_almacen(cls, valor: str | None) -> str | None:
        """Mismo control de arranque que `_ollama_es_local`, y por el mismo motivo.

        El endpoint del almacén es la **segunda excepción declarada** a la allowlist de
        `url_guard` (6.2; la primera es Ollama, ADR 0006). Esa excepción solo es legítima
        mientras el destino sea fijo y de configuración, así que se comprueba que lo parece
        antes de que salga la primera petición, y no en mitad de una ingesta.

        Aquí, al contrario que con Ollama, **se exige HTTPS**: por ahí viaja el archivo íntegro
        de la 6.5 hacia una red que no es la nuestra, con una credencial en cada petición.
        Tampoco se admiten credenciales en la URL —van en su propia variable, para que no
        acaben en un log de despliegue— ni ruta, que es lo que convertiría el endpoint en algo
        componible.
        """
        if valor is None:
            return None
        partes = urlsplit(valor)
        if partes.scheme != "https":
            raise ValueError(
                f"ALMACEN_S3_ENDPOINT tiene que ser https, no {partes.scheme!r}: por ahí sale "
                "el archivo íntegro y la credencial que lo firma."
            )
        if not partes.hostname:
            raise ValueError(f"ALMACEN_S3_ENDPOINT sin host: {valor!r}")
        if partes.username or partes.password:
            raise ValueError(
                "ALMACEN_S3_ENDPOINT no admite credenciales en la URL; usa "
                "ALMACEN_S3_ACCESS_KEY y ALMACEN_S3_SECRET_KEY."
            )
        if partes.path.rstrip("/"):
            raise ValueError(f"ALMACEN_S3_ENDPOINT no admite ruta: {partes.path!r}")
        return valor


@lru_cache
def get_settings() -> Settings:
    return Settings()
