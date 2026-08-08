"""Esquemas del desglose de cobertura por comunidad autónoma (ADR 0014).

Escritos a mano y no generados del modelo, mismo criterio que `schemas/documento.py`: lo que
publica la API es un contrato, y derivarlo del ORM hace que cualquier columna nueva se filtre
sola a la respuesta pública.

**Este endpoint publica un hueco, no un logro.** Su razón de ser es que la interfaz pueda
decir "de las 8 fuentes provinciales de Andalucía, 0 se están vigilando" en vez de callarse.
Por eso los esquemas separan siempre `conocidas` de `vigiladas`: un único número agregado
permitiría leer "8 fuentes" como si fueran ocho fuentes vigiladas.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CoberturaNivel(BaseModel):
    """Cobertura en un nivel de administración concreto."""

    model_config = ConfigDict(extra="forbid")

    ambito: str
    # Fuentes que sabemos que existen, verificadas en docs/fuentes.md.
    conocidas: int
    # De esas, cuántas se están ingiriendo de verdad (`activa`). Hoy, fuera del BOE, cero.
    vigiladas: int


class CoberturaCcaa(BaseModel):
    """Desglose de una comunidad, que es la unidad con la que trabaja el mapa."""

    model_config = ConfigDict(extra="forbid")

    ccaa_codigo: str
    ccaa: str
    niveles: list[CoberturaNivel]
    conocidas: int
    vigiladas: int


class Cobertura(BaseModel):
    """Respuesta completa: el total y el desglose por comunidad.

    El total incluye el BOE, que no pertenece a ninguna comunidad. Por eso va aparte y no como
    la suma de `por_ccaa`: sumar las comunidades y presentarlo como total del sistema dejaría
    fuera la única fuente que hoy está viva.
    """

    model_config = ConfigDict(extra="forbid")

    conocidas: int
    vigiladas: int
    por_ccaa: list[CoberturaCcaa]
