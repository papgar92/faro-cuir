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


@lru_cache
def get_settings() -> Settings:
    return Settings()
