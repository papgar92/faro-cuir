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

import datetime

from pydantic import BaseModel, ConfigDict, Field


class CoberturaNivel(BaseModel):
    """Cobertura en un nivel de administración concreto."""

    model_config = ConfigDict(extra="forbid")

    ambito: str
    # Fuentes que sabemos que existen, verificadas en docs/fuentes.md.
    conocidas: int
    # De esas, cuántas se están ingiriendo de verdad (`activa`). Hoy, fuera del BOE, cero.
    vigiladas: int


class LeyVigente(BaseModel):
    """Una ley autonómica en vigor de la watchlist. Auditada una a una contra boe.es."""

    model_config = ConfigDict(extra="forbid")

    identificador: str
    titulo: str
    # "trans" (ley específica de identidad/expresión de género) o "lgtbi" (ley LGTBI integral).
    # **No se deduce del título con una expresión regular**: "transgénero" aparece dentro de casi
    # todas las integrales y un regex las cruzaría. Se escribe a mano en la watchlist leyendo el
    # título oficial.
    tipo: str


class CoberturaCcaa(BaseModel):
    """Desglose de una comunidad, que es la unidad con la que trabaja el mapa."""

    model_config = ConfigDict(extra="forbid")

    ccaa_codigo: str
    ccaa: str
    niveles: list[CoberturaNivel]
    conocidas: int
    vigiladas: int
    # --- Hasta cuándo llega lo que sabemos de aquí --------------------------------------------
    # La fecha del boletín MÁS RECIENTE archivado de esta comunidad. `None` = no hay ninguno.
    #
    # Sin este campo, «vigilada, sin alertas aprobadas» no es una medición: es una promesa. Dice
    # que aquí se mira, y no dice desde cuándo — así que un lector no puede distinguir «lo miramos
    # ayer y no había nada» de «lo miramos en marzo y desde entonces nadie ha vuelto». Las dos
    # cosas se pintan hoy con la misma trama y significan cosas muy distintas.
    #
    # Es la fecha de PUBLICACIÓN del boletín y no el sello de nuestra ingesta, a propósito: el
    # sello dice cuándo corrió el worker, que puede ser esta mañana aunque el último boletín que
    # tengamos sea de hace un mes. Lo que necesita saber quien lee es hasta dónde llega el
    # archivo, no cuándo trabajamos nosotros.
    ultima_publicacion: datetime.date | None = None
    # --- Cobertura real, no declarada (ADR 0020) ------------------------------------------
    # `vigiladas` cuenta **fuentes activas**, y una fuente activa puede estar entregando
    # documentos que el pipeline no consigue leer. Pasó con el DOGC: 172 de sus 264 normas
    # llegaron como la página de error del portal, así que Catalunya figuraba como "1 de 1
    # vigilada" con dos tercios de esa fuente sin analizar por nadie.
    #
    # Estas dos cifras son la diferencia entre "estamos suscritos a este boletín" y "lo estamos
    # leyendo". Van juntas y ninguna se omite, por el mismo motivo que `conocidas` y `vigiladas`:
    # `ilegibles` a solas no dice si son 172 de 264 o de 20.000.
    normas: int
    ilegibles: int
    # --- Si aquí hay marco que vigilar, o no lo hay --------------------------------------------
    # Motivo verificado por el que esta comunidad **no tiene ley autonómica LGTBI**, o `None` si
    # sí la tiene. Sale de `_sin_ley_autonomica` de `config/watchlist.json`.
    #
    # Existe porque el mapa pintaba igual dos cosas opuestas, y la que sale perdiendo es la que
    # este proyecto existe para enseñar: Aragón sin alertas significa «hay dos leyes vigiladas y
    # nadie las ha tocado», y Castilla y León sin alertas significa «no hay ninguna ley que
    # tocar». Con el mismo relleno blanco, la segunda se lee como tranquilidad.
    #
    # Es el **retroceso por ausencia** del ADR 0027 —el que no deja rastro referencial porque no
    # hay norma a la que referirse— y es el único de esa familia del que el proyecto tiene dato
    # verificado. No publicarlo cuando se tiene sería el mismo silencio que la sección 7.2 no
    # permite en el embudo.
    sin_ley_autonomica: str | None = None
    # --- Línea base: qué marco protector EXISTE hoy aquí ---------------------------------------
    # Las leyes autonómicas **vigentes** de esta comunidad, de la watchlist. Es la línea base
    # sobre la que las alertas son el delta.
    #
    # Existe porque el mapa solo sabía pintar *cambios*, y el ADR 0027 midió que eso son ~5 casos
    # al año: quince comunidades en blanco no porque no pase nada, sino porque el mapa no sabía
    # decir qué hay. Con la línea base dice **el estado**, no solo el movimiento — que es el
    # «Rainbow Map por comunidad autónoma» del pitch de la sección 1.
    #
    # **Enseña qué existe; no puntúa.** Que una comunidad tenga ley trans y otra no es un hecho
    # verificable contra un BOE-A; decir cuál está «mejor» sería el juicio propio que prohíbe la
    # regla de oro 2. Por eso viaja la lista de leyes con su identificador, y no una nota.
    #
    # Las **derogadas quedan fuera**: se siguen vigilando para no perder el rastro histórico,
    # pero no son marco vigente (ver `vigente` en `pipeline/watchlist.py`).
    leyes_vigentes: list[LeyVigente] = Field(default_factory=list)


class Cobertura(BaseModel):
    """Respuesta completa: el total y el desglose por comunidad.

    El total incluye el BOE, que no pertenece a ninguna comunidad. Por eso va aparte y no como
    la suma de `por_ccaa`: sumar las comunidades y presentarlo como total del sistema dejaría
    fuera la única fuente que hoy está viva.
    """

    model_config = ConfigDict(extra="forbid")

    conocidas: int
    vigiladas: int
    # Ídem, para el sistema entero. Ver `CoberturaCcaa`: sin esto, el único endpoint que existe
    # para declarar los huecos del proyecto sería el único sitio donde este hueco no se ve.
    normas: int
    ilegibles: int
    # Boletines archivados. Va aquí y no en `GET /api/documentos` porque aquel **lista** y por
    # tanto tiene tope (100), y una lista topada contada por su longitud es una cifra falsa: la
    # franja de la portada decía «100 documentos archivados» con 162 en el almacén. Un total es
    # un agregado, y los agregados de este sistema viven en esta ruta.
    documentos: int
    por_ccaa: list[CoberturaCcaa]
