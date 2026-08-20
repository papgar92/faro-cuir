# ADR 0023 — El verbo tiene que ir pegado a la norma vigilada

- **Fecha**: 2026-08-20
- **Estado**: aceptado
- **Contexto de tarea**: el gold set encontró un falso positivo del clasificador al ampliar el
  corpus con normas que modifican la watchlist (entrada de ESTADO del 2026-08-19/20).
- **Números libres**: el siguiente libre tras este es el **0024**.

## Contexto

R-SUP-001 es **la única regla del catálogo que afirma un signo** (`retroceso`, severidad 4). Su
condición era:

```python
if supresion and vigiladas:   # hay una supresión en el texto Y se toca una norma vigilada
```

Las dos cosas se comprobaban **por separado y sobre ámbitos distintos**: la supresión, en
cualquier punto del cuerpo; la norma vigilada, en el `<analisis>`. Nada exigía que la supresión
fuera *de esa norma*. Mientras el corpus fueron tres días de BOE eso no se notó, porque las dos
únicas normas que disparaban la regla eran las dos reformas madrileñas, donde ambas cosas
coinciden de verdad.

Al ampliar el corpus con normas que modifican la watchlist —buscadas a propósito con
`scripts/quien_modifica.py`— apareció el patrón que rompe el supuesto: **la ley extensa**, donde
una modificación de la norma vigilada convive con supresiones que no tienen nada que ver, a
cientos de miles de caracteres de distancia.

| norma | qué le hace a la vigilada | qué supresión encontró la regla | veredicto |
|---|---|---|---|
| `BOE-A-2021-1859`, ley de medidas fiscales valenciana | modifica el art. 8.5 de la ley LGTBI | «Se suprimen las tasas… del Centro de Investigación» | `retroceso` |
| `BOE-A-2026-8073`, **nueva ley LGBTI catalana** | deroga la Ley 11/2014 y la sustituye | «Se suprime el apartado 7 del art. 92 de la Ley de finanzas públicas» | `retroceso` |

**2 falsos positivos de 4**, o sea la mitad de la única regla que afirma un signo. Y el segundo
es el peor error posible en este sistema: una ley cuyo título es *«de los derechos de las
personas LGBTI y la erradicación de la LGBTI-fobia»* clasificada como **retroceso**, con
severidad 4, por una cláusula sobre finanzas públicas.

## Decisión 1 — R-SUP-001 exige que la **referencia** declare la supresión

Lo que separa los verdaderos positivos de los falsos ya estaba delante y no se estaba leyendo:
**la propia referencia lo dice**.

    verdadero positivo   «el título, el preámbulo y determinados preceptos; y SUPRIME los
    (BOE-A-2024-10767)    arts. 7, 24 y 45, 48 y los títulos X y XIV de la Ley 2/2016»

    falso positivo       «el art. 8.5 y la disposición final 2 de la Ley 23/2018»
    (BOE-A-2021-1859)

Así que `_suprimidas()` filtra las normas vigiladas quedándose con aquellas **cuya referencia
declara una supresión**, y R-SUP-001 pasa a exigir `supresion and suprimidas`. La evidencia del
veredicto (`normas_vigiladas`, que es lo que lee el gate humano) pasa a nombrar esas y no
cualquier vigilada que el documento toque de paso.

Vale para las dos fuentes de referencia del ADR 0022: el `<analisis>` del BOE lo escribe en su
idioma («y SUPRIME los arts. 7…») y una referencia sacada del texto trae la cláusula pegada a la
cita («Se suprime el apartado 2 del artículo 8 de la Ley 2/2016»). Por eso el patrón
`_SUPRESION_DECLARADA` reconoce las dos formas, y **se aplica solo al texto de la referencia**:
aplicarlo al cuerpo devolvería el problema entero.

**El coste en recall está acotado y es el correcto**: una norma que suprima preceptos de una
vigilada sin que la referencia lo declare **no sale de la cola de revisión** — cae a R-MOD-001 o
R-DER-001, que son `indeterminado` con su evidencia. Lo que se pierde es el **signo**, no la
vigilancia. Afirmar un signo que no se puede sostener es justo lo que prohíbe la regla de oro 2.

## Decisión 2 — «Se deroga» a secas vuelve, con un criterio posicional

El mismo caso catalán destapó lo contrario, un **falso negativo**. Su disposición derogatoria
dice:

> «Disposición derogatoria. **Se deroga la Ley 11/2014, de 10 de octubre**, para garantizar los
> derechos de lesbianas, gais, bisexuales, transgéneros e intersexuales…»

Es la derogación de una norma vigilada por su ley sucesora, o sea el caso para el que se escribió
R-DER-001. La regla no la veía, porque `_DEROGACION` excluía `se deroga` sin «expresamente». Con
la Decisión 1 aplicada, esa norma caía a **R-SUP-002, severidad 2**, con la supresión de la ley
de finanzas como evidencia: el sistema habría enseñado a quien revisa una cláusula sobre
presupuestos cuando lo que había pasado es que la ley LGBTI catalana fue derogada y sustituida.

La exclusión venía de tres formas de ruido observadas en el corpus, y al mirarlas juntas se ve
que **lo que las separa no es «expresamente», es la posición**:

| | |
|---|---|
| operativa | «Disposición derogatoria. **Se deroga** la Ley 11/2014…» — abre frase |
| ruido: título citado | «…Reglamento (UE) 2016/679 y por el que **se deroga** la Directiva 95/46/CE» — incrustado |
| ruido: preámbulo | «Mediante la disposición derogatoria única **se deroga** la Ley 3/2007…» — incrustado |
| ruido: arrastre | «**Se derogan** las disposiciones de igual o inferior rango…» — abre frase, pero no nombra ninguna norma con número |

El patrón pasa a aceptar `se deroga(n)` **solo al principio de frase**, y la tercera forma la
sigue rechazando `_NORMA_CITADA`, que ya exigía el número. El ejemplo del preámbulo es real y del
caso insignia: sin el criterio posicional, la Ley 4/2023 emitiría **dos** evidencias para una
sola derogación y una sería el preámbulo hablando de derogar — justo la distinción que da nombre
a ese bloque, «las que derogan, no las que hablan de derogar».

## Consecuencias, medidas sobre el corpus

Reclasificadas las 56 normas en cola sobre 5.229 ingeridas:

| | antes | después |
|---|---|---|
| `R-SUP-001` → **retroceso** | 4 (2 falsos) | **2**, las dos reformas madrileñas |
| `R-DER-001` → indeterminado | 1 | **2** (entra la ley catalana) |
| `R-MOD-001` → indeterminado | 2 | 6 |

Las dos leyes que **amplían** derechos —la Ley 4/2023 estatal y la Ley 13/2025 catalana— quedan
las dos en `indeterminado`, con severidad 4 y a la cola de revisión. Es exactamente lo que la
cabecera de `pipeline/reglas.py` lleva escrito desde el ADR 0016: derogar es lo que hace tanto
quien desmonta una ley como quien la sustituye por otra mejor, y decidir cuál de las dos exige
mirar qué ocupa su lugar.

Tres apuntes más:

- **Las tres alertas ya emitidas conservan su veredicto.** El aviso de
  `services/clasificacion.py` («YA TIENE ALERTA EMITIDA y el catálogo reescribe su evidencia»)
  saltó como debía en las tres, y las tres siguen siendo las mismas reglas con el mismo signo.
- **`VERSION_REGLAS` lleva sufijo numérico desde hoy** (`2026.08.20.2`) por un tropiezo propio:
  dos cambios del catálogo el mismo día con la misma cadena hacen que el segundo **no reevalúe
  nada** y no falle nada visiblemente. Queda escrito en la constante.
- Lo que este ADR **no** arregla: R-SUP-001 sigue teniendo su modo de fallo simétrico conocido
  —suprimir un precepto *restrictivo* de una norma vigilada sería un avance y la regla lo
  llamaría retroceso—, que sigue sin aparecer en el corpus y sigue dependiendo del gate humano.
