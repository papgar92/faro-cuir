"""Esquema y loader de los casos del gold set (CLAUDE.md sección 7).

Cada caso es un fichero JSON en `casos/`, uno por documento, para que añadir un caso sea un
diff de un fichero y no un merge en uno grande compartido — importa cuando etiquetar 150-200
casos lo hace el humano por tandas (CLAUDE.md sección 11). Este módulo solo valida la forma;
qué normas entran y con qué etiqueta lo decide el humano, nunca este código.

Hoy el gold set mide una sola cosa con datos reales: el recall del prefiltro léxico
(`es_relevante`, etapa 1). `clasificacion_esperada` ya está en el esquema para cuando exista
el clasificador por diff (etapa 3, todavía sin construir); se deja opcional y sin usar a
propósito, para no tener que retocar cada caso ya escrito cuando llegue ese momento.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CASOS_DIR = Path(__file__).parent / "casos"


class CasoGoldSet(BaseModel):
    """Un documento histórico etiquetado a mano."""

    model_config = ConfigDict(extra="forbid")

    identificador_oficial: str = Field(min_length=1)
    fuente: Literal["boe", "boletin_autonomico", "parlamento"]
    # Texto y no `date`: el JSON no necesita un parseo especial y el formato AAAA-MM-DD ya es
    # inequívoco para quien etiqueta a mano.
    fecha_publicacion: str
    titulo: str = Field(min_length=1)
    organo_emisor: str | None = None
    # Lo único que se puede medir hoy con datos reales: ¿`pipeline.prefiltro.evaluar` debería
    # marcar este título como relevante?
    es_relevante: bool
    # Etapa 3, todavía sin construir. NULL a propósito: poner un valor ahora sería adivinar
    # qué diría un clasificador que no existe (regla de oro 8: nunca inventar).
    clasificacion_esperada: Literal["avance", "retroceso", "neutro", "indeterminado"] | None = None
    # Por qué este caso importa (positivo conocido, negativo difícil, caso histórico citado
    # en el TFM...). Sin esto, dentro de seis meses nadie sabe por qué se eligió justo este
    # documento y no otro cualquiera del mismo boletín.
    notas: str = Field(min_length=1)


def cargar_casos(directorio: Path = CASOS_DIR) -> list[CasoGoldSet]:
    """Lee y valida todos los casos.

    Un fichero que no valide rompe la carga entera, no se descarta en silencio: mismo
    criterio que la extracción del LLM (CLAUDE.md 6.7) — mejor un test que no arranca que un
    gold set que promete un caso que en realidad está corrupto.
    """
    if not directorio.exists():
        return []
    ficheros = sorted(directorio.glob("*.json"))
    return [
        CasoGoldSet.model_validate(json.loads(fichero.read_text(encoding="utf-8")))
        for fichero in ficheros
    ]
