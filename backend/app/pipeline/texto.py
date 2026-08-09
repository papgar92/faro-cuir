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

from xml.etree.ElementTree import Element

# Sube cuando cambie la forma de derivar el texto. Se guarda junto a lo que se derive de él,
# igual que `VERSION_VOCABULARIO` en el prefiltro: sin esto, "esta norma se evaluó así" deja de
# ser comprobable en cuanto la derivación cambie.
VERSION_TEXTO_PLANO = "2026.08.09"


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
    cuerpo = raiz.find("./texto")
    objetivo = cuerpo if cuerpo is not None else raiz
    fragmentos = (fragmento.strip() for fragmento in objetivo.itertext())
    return " ".join(f for f in fragmentos if f)
