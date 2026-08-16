"""Ingesta del DOGC (Diari Oficial de la Generalitat de Catalunya). ADR 0019.

**Segunda fuente del proyecto y primera autonómica**, y eso importa más de lo que parece: el BOE
republica las *leyes* autonómicas pero no sus decretos, órdenes ni instrucciones —medido sobre
1.193 normas ingeridas: 31 ítems de órganos autonómicos, todos anuncios y correcciones—, y el
retroceso silencioso de rango bajo que define este proyecto (sección 1) vive justo ahí. De las
31.094 normas que publica esta fuente, **20.889 son órdenes y 9.061 decretos**.

## De dónde sale cada cosa, verificado extremo a extremo el 2026-08-16

- **El sumario de un día** sale del portal de datos abiertos de la Generalitat, en JSON, con
  filtro por fecha exacta. Trae, por norma, el título en catalán y en castellano, el rango y las
  URL de todos sus formatos.
- **El texto íntegro** sale del Portal Jurídic en **XML Akoma Ntoso** (estándar OASIS de
  documentos legales), con el articulado en `<body>`. No es un PDF ni un HTML recortado: es el
  articulado estructurado.

## Tres decisiones que hay que conocer antes de tocar esto

1. **Se ingiere la versión en castellano.** El vocabulario del prefiltro (7.3) es castellano:
   sobre el texto catalán no dispararía casi nada y el eje léxico quedaría apagado en silencio,
   que es el modo de fallo que este proyecto no se permite. **La versión oficial es la catalana**
   y la castellana es su traducción oficial; queda dicho aquí y en el ADR 0019 porque una alerta
   se sostiene sobre una cita literal, y la cita sale de la traducción.
2. **El sumario no vive en un dominio del diario** sino en el portal de datos abiertos, que
   corre sobre un proveedor externo. Es la fuente oficial de datos abiertos de la Generalitat,
   pero no es `gencat.cat`, así que entra en la allowlist de `url_guard` como una decisión
   explícita y no de tapadillo (ADR 0019).
3. **El texto íntegro llega por redirección entre hosts** (`portaljuridic` → `portaldogc`).
   `url_guard` revalida cada salto contra la allowlist (ADR 0006), así que los dos dominios
   tienen que estar dentro; con uno solo, la descarga fallaría por control de seguridad y
   parecería un problema de la fuente.

## Lo que esta fuente NO trae, y hay que decirlo

El conjunto de datos son **disposiciones generales**: leyes, decretos legislativos, decretos ley,
decretos y órdenes. **Las resoluciones e instrucciones no están**, y son un vector de retroceso
real. Cubrir eso exige el sumario completo del diario, que hoy no se ha verificado que sea
obtenible por programa. Está escrito en `docs/fuentes.md` como limitación de la fuente, no como
hueco de la auditoría.
"""

from __future__ import annotations

import datetime
import json
import logging
import re
from urllib.parse import quote

import httpx

from app.ingest.boe import ItemSumario, Sumario, SumarioInvalido, SumarioNoDisponible
from app.security import url_guard

# Portal de datos abiertos de la Generalitat. El identificador del conjunto (`n6hn-rmy7`) es el
# de "Normativa del DOGC", verificado el 2026-08-16: 31.094 filas, de 1977-12-05 a hoy.
URL_SUMARIO = "https://analisi.transparenciacatalunya.cat/resource/n6hn-rmy7.json"

# Tope de disposiciones por día. Un día normal trae menos de diez; el tope existe porque el
# número de filas lo decide la fuente y no nosotros, y sin él una respuesta anómala se
# convertiría en miles de descargas de texto íntegro (6.2).
MAX_ITEMS_POR_DIA = 200

CABECERAS = {"Accept": "application/json"}

logger = logging.getLogger(__name__)

# El número de control es el identificador estable de cada disposición en el DOGC. Ocho dígitos
# en todo lo verificado; se valida antes de componer nada con él porque viene de una fuente
# externa (6.10).
_PATRON_CONTROL = re.compile(r"^\d{6,10}$")


def url_sumario(fecha: datetime.date) -> str:
    """Consulta del día. El filtro por fecha lo hace la fuente, no nosotros.

    Se filtra en el servidor y no descargando el conjunto entero por lo obvio —31.094 filas— y
    por lo menos obvio: así la petición es idempotente y reproducible, y dos ejecuciones del
    mismo día piden literalmente lo mismo.
    """
    filtro = f"data_de_publicaci_del_diari='{fecha.isoformat()}T00:00:00.000'"
    return (
        f"{URL_SUMARIO}?$where={quote(filtro)}&$limit={MAX_ITEMS_POR_DIA}&$order=n_mero_de_control"
    )


def descargar_sumario(fecha: datetime.date, *, client: httpx.Client | None = None) -> bytes:
    """Los bytes crudos del sumario, sin tocar (6.5: el hash prueba lo que envió el servidor)."""
    return url_guard.fetch(url_sumario(fecha), headers=CABECERAS, client=client)


def _texto(fila: dict[str, object], *claves: str) -> str:
    for clave in claves:
        valor = fila.get(clave)
        if isinstance(valor, str) and valor.strip():
            return valor.strip()
    return ""


def _url_xml_castellano(fila: dict[str, object]) -> str:
    """La URL del XML en castellano. Ver decisión 1 de la cabecera.

    Si la fuente no la trae, la fila se descarta en vez de caer al catalán: una norma cuyo texto
    no se puede evaluar con el vocabulario del proyecto entraría en el archivo aparentando
    vigilancia y sin recibirla.
    """
    valor = fila.get("url_es_format_xml")
    if isinstance(valor, dict):
        valor = valor.get("url")
    return valor.strip() if isinstance(valor, str) else ""


def parsear_sumario(contenido: bytes, fecha: datetime.date) -> Sumario:
    """Del JSON del portal a la misma forma que produce el ingestor del BOE.

    Devolver `Sumario`/`ItemSumario` y no un tipo propio es deliberado: el servicio de ingesta,
    el archivo y el prefiltro no tienen por qué saber de qué boletín viene una norma. El día que
    haya cinco fuentes, cinco formas distintas de decir «una disposición publicada» serían cinco
    caminos que mantener.

    Una fila sin identificador válido o sin XML en castellano **se descarta y no rompe el día**:
    el resto del boletín sí se puede vigilar, y abortar por una fila anómala dejaría sin mirar
    todas las demás.
    """
    try:
        filas = json.loads(contenido)
    except json.JSONDecodeError as exc:
        raise SumarioInvalido(f"El sumario del DOGC del {fecha} no es JSON: {exc}") from exc
    if not isinstance(filas, list):
        raise SumarioInvalido(f"El sumario del DOGC del {fecha} no es una lista de disposiciones")
    if not filas:
        # Días sin diario (domingos, festivos) y días sin disposiciones generales. Se trata igual
        # que un 404 del BOE: es una respuesta válida del mundo, no un fallo del sistema.
        raise SumarioNoDisponible(f"El DOGC no publicó disposiciones generales el {fecha}")

    items: list[ItemSumario] = []
    numero_diario = ""
    descartadas = 0
    for fila in filas[:MAX_ITEMS_POR_DIA]:
        if not isinstance(fila, dict):
            continue
        control = _texto(fila, "n_mero_de_control")
        url_xml = _url_xml_castellano(fila)
        if not _PATRON_CONTROL.match(control) or not url_xml:
            # **Se dice cuál y por qué.** Una fila descartada en silencio es una norma que el
            # sistema no vigila y de la que nadie se entera — el falso negativo invisible de la
            # sección 1. Ocurre de verdad: en el sumario del 2024-12-19, una de las cuatro
            # disposiciones no publica versión castellana.
            logger.warning(
                "Fila del sumario del DOGC del %s descartada (control=%r, con XML castellano=%s): "
                "esa disposición NO se vigila.",
                fecha,
                control or "sin número de control",
                bool(url_xml),
            )
            descartadas += 1
            continue
        numero_diario = numero_diario or _texto(fila, "n_mero_de_diari")
        items.append(
            ItemSumario(
                # Prefijo propio y número de control de la fuente. No se usa jamás para componer
                # una ruta de fichero (6.3: las rutas salen del sha256).
                identificador=f"DOGC-{control}",
                # Título en castellano, con el catalán como respaldo: sin título no hay nada que
                # enseñar ni que prefiltrar en fase 1.
                titulo=_texto(fila, "t_tol_de_la_norma_es", "t_tol_de_la_norma"),
                url_xml=url_xml,
                url_pdf=None,
                # El DOGC no divide en secciones como el BOE. Se rellena con el rango, que es lo
                # que de verdad clasifica una disposición aquí, en vez de inventar una sección.
                seccion_codigo="",
                seccion_nombre=_texto(fila, "rang_de_norma"),
                departamento=_texto(fila, "diari_oficial") or "DOGC",
                epigrafe=None,
            )
        )

    if not items:
        raise SumarioInvalido(
            f"El sumario del DOGC del {fecha} trae {len(filas)} filas y ninguna utilizable "
            "(sin número de control válido o sin XML en castellano)."
        )

    if descartadas:
        logger.warning(
            "Sumario del DOGC del %s: %s de %s disposiciones quedan fuera de la vigilancia.",
            fecha,
            descartadas,
            len(filas),
        )

    return Sumario(
        identificador=f"DOGC-S-{fecha.isoformat()}",
        fecha_publicacion=fecha,
        numero_diario=numero_diario,
        items=tuple(items),
    )
