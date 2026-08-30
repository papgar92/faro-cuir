"""Del XML del boletín al texto sobre el que trabaja el pipeline.

Módulo **puro**: recibe un árbol ya parseado por `security/xml_safe.py` (6.1) y devuelve texto.
No parsea nada por su cuenta, mismo criterio que `pipeline/referencias.py`.

Vivía como `_texto_plano` dentro de `services/extraccion.py` y se había duplicado en
`scripts/medir_fase2.py`. Se saca aquí por dos motivos, y el segundo es el importante:

1. Con el ADR 0015 lo necesitan tres llamantes (el extractor, el prefiltro de la fase 2 y la
   medición), y una derivación copiada tres veces son tres derivaciones distintas en cuanto
   alguien toque una.
2. **Es la normalización de facto del proyecto y no tenía nombre ni versión.** Toda la
   evidencia que el sistema llegue a citar se apoya en el texto que sale de aquí; si esta
   función cambia y nadie lo registra, las extracciones de antes y las de después dejan de ser
   comparables sin que nada avise. `VERSION_TEXTO_PLANO` es lo que hace que ese cambio sea
   visible.

**Esto no es todavía la normalización de 7.5** — la que fija offsets estables para citar
evidencia. Esa es la tarea del ADR 0013 y exige decidir qué se hace con espacios, guiones de
línea y entidades. Lo de aquí es el paso previo y honesto: un texto legible, versionado, y
derivado del archivado de forma reproducible.
"""

from __future__ import annotations

import html
import re
from xml.etree.ElementTree import Element

# Espacio de nombres de Akoma Ntoso (estándar OASIS de documentos legales), que es lo que
# publica el DOGC (ADR 0019).
_AKN = "{http://docs.oasis-open.org/legaldocml/ns/akn/3.0}"

# Marcado HTML dentro del atributo `period`. Ver `_texto_akoma_ntoso`.
_ETIQUETA = re.compile(r"<[^>]+>")
_ESPACIOS = re.compile(r"\s+")

# Sube cuando cambie la forma de derivar el texto. Se guarda junto a lo que se derive de él,
# igual que `VERSION_VOCABULARIO` en el prefiltro: sin esto, "esta norma se evaluó así" deja de
# ser comprobable en cuanto la derivación cambie.
VERSION_TEXTO_PLANO = "2026.08.16"


def texto_plano(raiz: Element) -> str:
    """Extrae el cuerpo real de la norma, sin el ruido de sus metadatos.

    Verificado contra un documento real de texto íntegro del BOE (`BOE-A-2023-5366`, no
    deducido de documentación): la estructura es `documento > metadatos, metadata-eli,
    analisis, texto`. `analisis` trae referencias a normas relacionadas (a qué modifica, quién
    la modificó después) en decenas de etiquetas `<texto>` cortas propias; concatenar el árbol
    entero sin distinguirlas agota el presupuesto de caracteres en ese ruido antes de llegar al
    articulado real, que vive entero en el único `<texto>` de primer nivel.

    Si ese elemento no existe —una fuente distinta del BOE, o un tipo de documento con otra
    forma que todavía no se ha comprobado— se cae al árbol completo: no es ideal, pero es mejor
    que no enviar nada, y no inventa una estructura que no se ha verificado para ese caso
    (regla de oro 8).

    Ojo con una consecuencia del caso de respaldo: si se cae al árbol completo, el bloque
    `<analisis>` entra en el texto. Para el extractor es ruido caro; para el prefiltro léxico
    es además una **fuente de falsos positivos**, porque los títulos de las normas citadas
    contienen vocabulario del dominio sin que esta norma regule nada. Quien evalúe sobre texto
    íntegro debe saber que ese caso existe.
    """
    akn = _texto_akoma_ntoso(raiz)
    if akn:
        return akn

    cuerpo = raiz.find("./texto")
    if cuerpo is None:
        # Akoma Ntoso (DOGC, ADR 0019): el articulado vive en `<body>`, y el resto del árbol es
        # metadatos ELI/FRBR — el equivalente exacto del ruido de `<analisis>` en el BOE. Se
        # busca con el espacio de nombres del estándar y no por sufijo del tag para no capturar
        # un `<body>` de cualquier otro XML que algún día llegue.
        cuerpo = raiz.find(
            "./{http://docs.oasis-open.org/legaldocml/ns/akn/3.0}act/"
            "{http://docs.oasis-open.org/legaldocml/ns/akn/3.0}body"
        )
    if cuerpo is None:
        # BOA (ADR 0028): la respuesta es `documento > registro > texto`, con el articulado en
        # un nodo de texto normal. Sin esta rama caeria al arbol completo y el texto se llenaria
        # de metadatos del registro —titulo, emisor, seccion—, que para el prefiltro lexico son
        # falsos positivos del mismo tipo que el `<analisis>` del BOE.
        #
        # **`VERSION_TEXTO_PLANO` NO sube por esto, y es deliberado.** Esa version gobierna las
        # colas de reproceso del prefiltro y del clasificador (`!=` en `services/prefiltro.py` y
        # `services/clasificacion.py`): subirla reprocesaria las decenas de miles de normas ya
        # archivadas del BOE y del DOGC, cuya derivacion esta rama no toca porque solo dispara
        # sobre una estructura que ningun documento suyo tiene. Se sube cuando cambie como se
        # deriva algo YA archivado, no cuando se aprenda a leer una forma nueva.
        cuerpo = raiz.find("./registro/texto")
    if cuerpo is None:
        # BOCYL (ADR 0029): `disposicion > contenido > texto`, con el articulado en <p>. El
        # <titulo> es hermano de <texto> dentro de <contenido>, así que apuntar a <contenido>
        # metería el título en el articulado; se apunta a <texto>.
        #
        # `VERSION_TEXTO_PLANO` tampoco sube por esto, por lo mismo que en el caso del BOA.
        cuerpo = raiz.find("./contenido/texto")
    objetivo = cuerpo if cuerpo is not None else raiz
    fragmentos = (fragmento.strip() for fragmento in objetivo.itertext())
    return " ".join(f for f in fragmentos if f)


def _texto_akoma_ntoso(raiz: Element) -> str:
    """El articulado de un documento Akoma Ntoso del DOGC.

    **Tiene truco, y está verificado contra el documento real, no deducido del estándar**
    (`DECRETO LEY 11/2024`, descargado el 2026-08-16): el DOGC publica AKN válido en su
    estructura, pero **el articulado entero no va en nodos de texto, va dentro de un atributo**
    —`<content period="&lt;div&gt;&lt;p&gt;…">`— con el HTML escapado dentro.

    Consecuencia práctica: `itertext()` sobre ese árbol devuelve **cadena vacía**. Un derivador
    escrito contra la lectura del estándar habría archivado cientos de normas con texto vacío,
    el prefiltro las habría descartado todas por no encontrar ningún término y no habría fallado
    nada visiblemente. Es el modo de fallo exacto que este proyecto no se permite, y por eso el
    caso tiene su propio test con XML real recortado.

    Se desescapa el HTML y se quitan las etiquetas con expresiones regulares —sin dependencias
    nuevas (sección 3)— porque aquí solo se deriva **texto para analizar**: nada de esto se
    renderiza. Lo que llegue a una pantalla pasa por el escapado del frontend, que trata este
    contenido como lo que es, no confiable (6.10).
    """
    contenidos = [
        nodo.get("period", "") for nodo in raiz.iterfind(f".//{_AKN}content") if nodo.get("period")
    ]
    if not contenidos:
        return ""
    crudo = html.unescape(" ".join(contenidos))
    # Segunda pasada de desescapado: el atributo trae `&amp;nbsp;` (doblemente escapado) en
    # todos los documentos verificados. Sin ella, el texto se llena de `&nbsp;` literales que
    # el vocabulario del prefiltro tendría que aprender a ignorar.
    sin_etiquetas = _ETIQUETA.sub(" ", html.unescape(crudo))
    return _ESPACIOS.sub(" ", sin_etiquetas).strip()
