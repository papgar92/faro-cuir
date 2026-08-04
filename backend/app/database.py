"""Engine y base declarativa de SQLAlchemy. Sincrono a propósito: tanto la API como el
worker de ingesta son procesos simples de bajo volumen (ver CLAUDE.md, "NO Celery"); un
engine sincrono evita mantener dos rutas (async para la API, sync para el worker) sin
necesidad real de concurrencia alta."""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass
