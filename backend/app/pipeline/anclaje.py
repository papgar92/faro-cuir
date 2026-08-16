"""Anclar lo que dice el modelo al texto archivado. Regla de oro 9, CLAUDE.md 7.5, ADR 0013.

Módulo **puro**: recibe dos cadenas y devuelve coordenadas. Ni base de datos, ni red, ni LLM.

## Qué problema resuelve

El extractor devuelve texto que *afirma* haber leído en el documento. Sin comprobarlo, una
alucinación es indistinguible de una cita: las dos son una cadena en un JSON. Este módulo
convierte cada afirmación en un **rango de caracteres del texto archivado** o la descarta. Con
eso, la revisión humana pasa de ser confianza a ser verificación —el revisor mira el archivo, no
la palabra del modelo— y una alucinación se detecta sola, sin que nadie tenga que sospecharla.

## Los offsets los calculamos nosotros, no los pide el modelo

7.5 se escribió suponiendo que cada hecho llegaría del LLM **con** sus offsets y que aquí solo se
comprobarían. Se implementa al revés y conviene entender por qué, porque es más fuerte y no
menos:

1. Un modelo de 3B parámetros contando caracteres es una fuente de error nueva. Un fallo de
   aritmética descartaría una cita correcta, y eso es un falso negativo introducido por el
   propio control.
2. Aunque los diera, habría que buscarlos igualmente en el texto para validarlos. La búsqueda
   es el control; el offset del modelo sería, en el mejor de los casos, redundante.
3. **Pedir menos al modelo reduce la superficie de inyección.** Un campo más en el esquema es un
   campo más que un documento hostil puede intentar dirigir.

Lo que 7.5 exige de verdad —que ningún hecho publicado carezca de un rango verificable del
archivo, y que lo no verificable se descarte— se cumple igual. La diferencia está escrita en el
ADR 0013.

## Sobre qué texto se ancla

Sobre el mismo que usan las reglas: el que deriva `pipeline/texto.texto_plano`, versionado con
`VERSION_TEXTO_PLANO`. **No hay una segunda normalización**, y es deliberado: dos derivaciones
del mismo documento archivado son dos sistemas de coordenadas, y entonces un span del
clasificador y un offset de la extracción no se pueden contrastar entre sí ni sobre el mismo
texto. Un archivo con dos reglas distintas para medir no sirve para lo que este proyecto lo usa.
"""

from __future__ import annotations

from dataclasses import dataclass

# Sube cuando cambie la forma de anclar (qué se considera coincidencia). Viaja en
# `extraccion_json` junto a `version_texto_plano`, porque un offset sin saber cómo se obtuvo no
# es reproducible.
VERSION_ANCLAJE = "2026.08.16"


@dataclass(frozen=True)
class Ancla:
    """Dónde está, en el texto archivado, lo que el modelo dijo haber leído.

    `fragmento` es **el recorte real del archivo**, no lo que devolvió el modelo. La distinción
    es todo el control: lo que se guarda y se enseña es el documento, y la cadena del modelo se
    usa solo para localizarlo y luego se tira.
    """

    inicio: int
    fin: int
    fragmento: str

    def verifica(self, texto: str) -> bool:
        """Mismo control que `reglas.Evidencia.verifica`, aplicado a la otra mitad del sistema."""
        return texto[self.inicio : self.fin] == self.fragmento


def _proyeccion(texto: str) -> tuple[str, list[int]]:
    """Texto con espacios colapsados + a qué posición del original corresponde cada carácter.

    Hace falta porque el modelo reproduce una cita con los espacios que le parecen: un salto de
    línea donde el archivo tiene dos, un espacio donde el archivo tiene una tabulación. Exigir
    igualdad byte a byte descartaría citas correctas —falso negativo introducido por el control—
    y aceptar cualquier parecido dejaría pasar una paráfrasis, que es exactamente lo que hay que
    detectar. Colapsar espacios es la única licencia que se toma.
    """
    salida: list[str] = []
    indices: list[int] = []
    espacio_pendiente = False
    for posicion, caracter in enumerate(texto):
        if caracter.isspace():
            espacio_pendiente = bool(salida)
            continue
        if espacio_pendiente:
            salida.append(" ")
            indices.append(posicion)
            espacio_pendiente = False
        salida.append(caracter)
        indices.append(posicion)
    return "".join(salida), indices


def anclar(texto: str, afirmado: str, *, desplazamiento: int = 0) -> Ancla | None:
    """Localiza `afirmado` dentro de `texto`. `None` si no está, y eso significa descartar.

    `desplazamiento` es la posición, **en el documento entero**, donde empieza `texto`. Hoy vale
    siempre 0 porque la ventana que se le manda al modelo empieza al principio del documento,
    pero el parámetro existe y está probado a propósito: en cuanto haya ventana deslizante
    (6.9.7), olvidar el desplazamiento produciría offsets que apuntan a otro párrafo del archivo,
    y una alerta que señala al sitio equivocado es peor que una que no señala. Es el error fácil
    de esta etapa y por eso tiene su propio test.

    Devuelve el **primer** sitio donde aparece. Si una cita corta aparece dos veces en el
    documento, esa ambigüedad la resuelve quien revisa mirando el archivo; inventar aquí un
    criterio de desempate sería adivinar.
    """
    if not afirmado or not texto:
        return None

    posicion = texto.find(afirmado)
    if posicion != -1:
        return Ancla(
            inicio=desplazamiento + posicion,
            fin=desplazamiento + posicion + len(afirmado),
            fragmento=afirmado,
        )

    plano_texto, indices = _proyeccion(texto)
    plano_afirmado, _ = _proyeccion(afirmado)
    if not plano_afirmado:
        return None

    posicion = plano_texto.find(plano_afirmado)
    if posicion == -1:
        return None

    inicio = indices[posicion]
    # El final es exclusivo: la posición del último carácter que forma parte de la cita, más uno.
    fin = indices[posicion + len(plano_afirmado) - 1] + 1
    return Ancla(
        inicio=desplazamiento + inicio, fin=desplazamiento + fin, fragmento=texto[inicio:fin]
    )
