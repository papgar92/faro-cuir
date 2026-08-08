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

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    # --- Etiquetado del prefiltro (CLAUDE.md 7.8) -----------------------------------------
    #
    # **Este es el formato definitivo y hay que etiquetar con él.** Cerrarlo ANTES del
    # etiquetado masivo es el motivo de que la tarea 0.b fuera antes que el gold set: volver a
    # etiquetar 200 documentos es el peor uso posible del recurso más caro del proyecto, que
    # es el tiempo humano de anotación.
    #
    # `es_relevante` (bool) era el formato viejo, de cuando el prefiltro tenía dos resultados
    # y evaluaba títulos. Se mantiene por compatibilidad de los casos ya escritos y **queda
    # derivado**: no se etiqueta a mano, sale de `prefiltro_esperado`.
    es_relevante: bool | None = None

    # Cuál de los cuatro estados de 7.2 debería producir el prefiltro. Se etiqueta sobre el
    # **texto íntegro**, no sobre el título: es lo que decide 7.1.
    #
    # Guía para quien etiqueta, y conviene leerla entera antes de la primera tanda:
    #   relevante  → el documento regula sobre el ámbito, o modifica una norma de la watchlist.
    #   sospecha   → lo menciona pero no se ve que regule; no hay con qué descartarlo.
    #                **Ante la duda, sospecha.** Nunca `descartada` por si acaso: sospecha
    #                cuesta un puesto en la cola, descartada cuesta perder la norma.
    #   descartada → no tiene nada que ver, leído el texto completo.
    #   pendiente  → NO se usa al etiquetar. Es un estado del pipeline (falta el documento),
    #                no un juicio humano.
    prefiltro_esperado: Literal["sospecha", "relevante", "descartada"] | None = None

    # Qué ejes deberían dispararse (7.3). Permite medir el recall **por eje** y contestar la
    # pregunta que justifica el eje referencial: ¿aporta casos que el léxico no ve, o solo
    # duplica? Un número agregado no la contesta.
    # Lista vacía = no debería disparar ninguno, que es lo coherente con `descartada`.
    ejes_esperados: list[Literal["lexico", "referencial"]] = Field(default_factory=list)
    # Etapa 3, todavía sin construir. NULL a propósito: poner un valor ahora sería adivinar
    # qué diría un clasificador que no existe (regla de oro 8: nunca inventar).
    clasificacion_esperada: Literal["avance", "retroceso", "neutro", "indeterminado"] | None = None
    # Por qué este caso importa (positivo conocido, negativo difícil, caso histórico citado
    # en el TFM...). Sin esto, dentro de seis meses nadie sabe por qué se eligió justo este
    # documento y no otro cualquiera del mismo boletín.
    notas: str = Field(min_length=1)

    @model_validator(mode="after")
    def _coherencia(self) -> CasoGoldSet:
        """Deriva `es_relevante` y comprueba que la etiqueta no se contradiga a sí misma.

        Un caso que dijera `descartada` con `ejes_esperados: ["lexico"]` no rompería nada: se
        cargaría, y el día que se midiera el recall daría un número que nadie sabría interpretar
        porque el propio caso es incoherente. Un gold set con un caso mal etiquetado es peor que
        uno con un caso menos: el primero miente, el segundo solo mide poco.
        """
        if self.prefiltro_esperado is None:
            if self.es_relevante is None:
                raise ValueError(
                    "hace falta 'prefiltro_esperado' (formato de 7.8). "
                    "'es_relevante' solo se acepta en casos anteriores al formato nuevo."
                )
            return self

        entra_en_la_cola = self.prefiltro_esperado in ("relevante", "sospecha")

        if entra_en_la_cola and not self.ejes_esperados:
            raise ValueError(
                f"{self.identificador_oficial}: si pasa el filtro tiene que decirse por qué eje"
            )
        if not entra_en_la_cola and self.ejes_esperados:
            raise ValueError(
                f"{self.identificador_oficial}: se espera descartarla pero se declara que "
                f"dispara {self.ejes_esperados}"
            )
        if self.es_relevante is not None and self.es_relevante != entra_en_la_cola:
            raise ValueError(
                f"{self.identificador_oficial}: 'es_relevante'={self.es_relevante} contradice "
                f"'prefiltro_esperado'={self.prefiltro_esperado!r}"
            )

        # Derivado, no etiquetado: "relevante" en el formato viejo significaba "no se descarta".
        object.__setattr__(self, "es_relevante", entra_en_la_cola)
        return self


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
